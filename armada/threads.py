"""Threads + compaction (SPEC §5).

An agent has a **main** thread (default) and optional **sub-threads** for scoped context
(e.g. a `taxes` thread that carries tax history but not options-trading). A thread is an
append-only `messages.jsonl` plus an optional `summary.md` of older, compacted turns.

Compaction: when a thread's rendered history exceeds a threshold, the oldest turns are
summarized (via the engine) into `summary.md` and dropped from the live log — while the
agent's always-on core (memory.py) is re-injected fresh every run and never compacted.
Sub-threads inherit the core but NOT each other's history — that's the scoping lever.
"""
from __future__ import annotations
import json, datetime, uuid
from pathlib import Path
from .util import file_lock


class Thread:
    def __init__(self, agent_dir, name: str = "main"):
        self.name = name
        self.dir = Path(agent_dir) / "threads" / name
        self.msgs = self.dir / "messages.jsonl"
        self.summary_f = self.dir / "summary.md"

    def _messages(self) -> list[dict]:
        out = []
        if self.msgs.exists():
            for ln in self.msgs.read_text(encoding="utf-8-sig").splitlines():
                ln = ln.strip()
                if ln:
                    try:
                        out.append(json.loads(ln))
                    except json.JSONDecodeError:
                        pass
        return out

    def summary(self) -> str:
        return self.summary_f.read_text(encoding="utf-8-sig").strip() if self.summary_f.exists() else ""

    @staticmethod
    def _who(role: str) -> str:
        return "You" if role == "assistant" else "Owner"

    @staticmethod
    def _is_turn(m: dict) -> bool:
        """A conversational turn (goes to the model), as opposed to a UI 'event' entry."""
        return m.get("role") in ("user", "assistant") and m.get("kind") != "event"

    def render(self) -> str:
        parts = []
        s = self.summary()
        if s:
            parts.append("## Earlier in this thread (summary)\n" + s)
        msgs = [m for m in self._messages() if self._is_turn(m)]
        if msgs:
            parts.append("## Recent turns\n"
                         + "\n".join(f"{self._who(m.get('role',''))}: {str(m.get('content','')).strip()}"
                                     for m in msgs))
        return "\n\n".join(parts)

    def _write(self, *records) -> None:
        # lock so a scheduled job running in this thread can't interleave with a live chat turn
        self.dir.mkdir(parents=True, exist_ok=True)
        with file_lock(self.msgs):
            with self.msgs.open("a", encoding="utf-8") as f:
                for r in records:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def append(self, user: str, assistant: str, attachments=None, outputs=None, caps=None):
        """Write a complete turn — both halves at once. For a live chat use begin_turn /
        complete_turn instead, so the owner's message survives them walking away."""
        ts = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        urec = {"role": "user", "ts": ts, "content": user}
        if attachments:
            urec["attachments"] = attachments      # [{"kind":"image"|"file","name":..,"file":..}]  (owner INPUT)
        arec = {"role": "assistant", "ts": ts, "content": assistant}
        if outputs:
            arec["outputs"] = outputs              # [{"kind":"output","name":..,"path":abs}]  (agent OUTPUT artifacts)
        if caps:
            arec["caps_used"] = caps               # [{"type":..,"id":..,"name":..}]  capabilities actually exercised
        self._write(urec, arec)

    def begin_turn(self, user: str, attachments=None) -> str:
        """Record what the owner said, now, before the agent has said anything back.

        The turn used to be written in one piece when the reply landed, which meant the owner's
        own message existed nowhere but the open browser tab until then. Navigating away during a
        long turn lost it from the transcript — the agent was still working, the status dot still
        pulsed, but the thread you came back to had no record of what you had asked. A run that
        failed lost it permanently.

        Returns a turn id the reply carries back, so the two halves can be matched by something
        better than "the last user line".
        """
        ts = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        tid = f"{ts}-{uuid.uuid4().hex[:8]}"
        rec = {"role": "user", "ts": ts, "content": user, "turn": tid}
        if attachments:
            rec["attachments"] = attachments
        self._write(rec)
        return tid

    def complete_turn(self, turn: str, assistant: str, outputs=None, caps=None,
                      status: str = "ok") -> None:
        """Close a turn opened by begin_turn. `status` is 'ok', 'error' or 'stopped'.

        A turn is always closed, including when the run failed, because an owner message with
        nothing after it reads as the app having lost the message rather than as the agent having
        had a problem.
        """
        ts = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        rec = {"role": "assistant", "ts": ts, "content": assistant, "turn": turn}
        if status != "ok":
            rec["status"] = status
        if outputs:
            rec["outputs"] = outputs
        if caps:
            rec["caps_used"] = caps
        self._write(rec)

    def open_turn(self) -> dict | None:
        """The last owner message with no reply after it, or None.

        What the UI needs to decide between "still working" and "this one never got an answer".
        """
        msgs = [m for m in self._messages() if self._is_turn(m)]
        if msgs and msgs[-1].get("role") == "user":
            return msgs[-1]
        return None

    def append_event(self, type: str, title: str = "", subtitle: str = "",
                     icon: str = "", status: str = "", href: str = "",
                     pct=None, meta: dict | None = None) -> dict:
        """Append a non-message 'event' entry (rendered as an inline card in the UI, e.g.
        'Created scheduled task …' or a compaction progress bar). Events are UI chrome — they
        are skipped when assembling the model context and preserved across compaction."""
        self.dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        ev = {"role": "event", "kind": "event", "type": type, "ts": ts}
        for k, v in (("title", title), ("subtitle", subtitle), ("icon", icon),
                     ("status", status), ("href", href)):
            if v:
                ev[k] = v
        if pct is not None:
            ev["pct"] = pct
        if meta:
            ev["meta"] = meta
        with file_lock(self.msgs):
            with self.msgs.open("a", encoding="utf-8") as f:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        return ev

    def compact_if_needed(self, engine, threshold_chars: int = 600000, keep_recent_pairs: int = 3) -> bool:
        """Summarize older turns when history grows past the threshold. Returns True if compacted.
        Only conversational turns are summarized/dropped; 'event' entries are always preserved."""
        all_msgs = self._messages()
        turns = [m for m in all_msgs if self._is_turn(m)]
        if len(self.render()) <= threshold_chars or len(turns) <= keep_recent_pairs * 2:
            return False
        keep = keep_recent_pairs * 2
        older, recent = turns[:-keep], turns[-keep:]
        recent_ids = {id(m) for m in recent}
        transcript = "\n".join(f"{self._who(m.get('role',''))}: {m.get('content','')}" for m in older)
        prev = self.summary()
        prompt = ("Compress the conversation below into 4–7 tight bullet points that preserve decisions, "
                  "concrete facts/numbers, and open items. No preamble.\n\n"
                  + (f"Existing summary to fold in:\n{prev}\n\n" if prev else "") + transcript)
        res = engine.run(system="You are a precise note-taker. Output only the bullet summary.",
                         prompt=prompt, allow_tools=False)
        new_summary = ((prev + "\n" + res.output).strip() if prev else res.output.strip()) or prev
        # keep every event entry + the recent conversational turns; drop the older, summarized turns
        kept = [m for m in all_msgs if not self._is_turn(m) or id(m) in recent_ids]
        with file_lock(self.msgs):
            self.summary_f.write_text(new_summary, encoding="utf-8")
            with self.msgs.open("w", encoding="utf-8") as f:
                for m in kept:
                    f.write(json.dumps(m, ensure_ascii=False) + "\n")
        return True

    @staticmethod
    def list_threads(agent_dir) -> list[str]:
        base = Path(agent_dir) / "threads"
        return sorted(p.name for p in base.iterdir() if p.is_dir()) if base.is_dir() else []
