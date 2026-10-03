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
from .util import file_lock, write_json_atomic
from .thread_store import HistoryStore, entries


class Thread:
    def __init__(self, agent_dir, name: str = "main"):
        self.name = name
        self.dir = Path(agent_dir) / "threads" / name
        self.msgs = self.dir / "messages.jsonl"
        self.summary_f = self.dir / "summary.md"
        self._store = HistoryStore(self.dir)

    def snapshot(self) -> tuple[str, list[dict]]:
        """A coherent summary and live log, including recovery of interrupted compaction."""
        state = self._store.read()
        return state.summary.lstrip("\ufeff").strip(), [m for _, m in entries(state.messages, strict=False) if m is not None]

    def _messages(self) -> list[dict]:
        return self.snapshot()[1]

    def display_snapshot(self) -> tuple[str, list[dict]]:
        """Hide historical job turns without changing chat-action indexes or stored data."""
        from .job_history import legacy_turns
        summary, messages = self.snapshot()
        hidden = legacy_turns(self.dir.parent.parent, self.name, messages)
        return summary, [dict(m, kind="job") if i in hidden else m
                         for i, m in enumerate(messages)]

    def summary(self) -> str:
        return self.snapshot()[0]

    @staticmethod
    def _who(role: str) -> str:
        return "You" if role == "assistant" else "Owner"

    @staticmethod
    def _is_turn(m: dict) -> bool:
        """A conversational turn (goes to the model), as opposed to a UI 'event' entry."""
        return m.get("role") in ("user", "assistant") and m.get("kind") != "event"

    def render(self) -> str:
        summary, messages = self.snapshot()
        return self._render(summary, messages)

    @classmethod
    def _render(cls, summary, messages):
        parts = []
        if summary:
            parts.append("## Earlier in this thread (summary)\n" + summary)
        msgs = [m for m in messages if cls._is_turn(m)]
        if msgs:
            parts.append("## Recent turns\n"
                         + "\n".join(f"{cls._who(m.get('role',''))}: {str(m.get('content','')).strip()}"
                                     for m in msgs))
        return "\n\n".join(parts)

    def _write(self, *records) -> None:
        self._store.append(records)

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
        with file_lock(self._progress_path(turn)):
            self._progress_path(turn).unlink(missing_ok=True)

    def _progress_path(self, turn: str) -> Path:
        import hashlib
        return self.dir / (".progress-" + hashlib.sha256(turn.encode()).hexdigest()[:20] + ".json")

    def save_progress(self, turn: str, text: str, activity: str = "Working on it…",
                      events: list[dict] | None = None) -> None:
        """Checkpoint visible output before emitting it, so navigation cannot lose it.

        Kept outside the conversation log: an unfinished reply must not become model history
        or be mistaken for a completed answer. Each turn owns its checkpoint.
        """
        path = self._progress_path(turn)
        with file_lock(path):
            write_json_atomic(path, {"turn": turn, "content": text, "activity": activity,
                                     "events": events or []})

    def progress(self, turn: str) -> dict:
        try:
            return json.loads(self._progress_path(turn).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def open_turn(self, messages: list[dict] | None = None) -> dict | None:
        """The last owner message without its matching reply, including overlapping turns.

        What the UI needs to decide between "still working" and "this one never got an answer".
        """
        msgs = self._messages() if messages is None else messages
        _, pending = self._turn_groups(msgs)
        return next((msgs[i] for i in sorted(pending, reverse=True) if msgs[i].get("role") == "user"), None)

    @classmethod
    def _turn_groups(cls, messages):
        """Pair explicit IDs or adjacent legacy exchanges; ambiguous/orphan records stay live."""
        indices = [i for i, m in enumerate(messages) if cls._is_turn(m)]
        pending, groups, tagged = set(indices), [], {}
        for i in indices:
            tid = messages[i].get("turn")
            if isinstance(tid, str) and tid:
                tagged.setdefault(tid, []).append(i)
        for group in tagged.values():
            if len(group) == 2 and [messages[i].get("role") for i in group] == ["user", "assistant"]:
                groups.append(group)
                pending.difference_update(group)
        for a, b in zip(indices, indices[1:]):
            if (not messages[a].get("turn") and not messages[b].get("turn")
                    and messages[a].get("role") == "user" and messages[b].get("role") == "assistant"):
                groups.append([a, b])
                pending.difference_update((a, b))
        return groups, pending

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
        self._write(ev)
        return ev

    def truncate(self, keep: int) -> int:
        """Keep the first requested records; invalidate any summary currently being generated."""
        return self._store.truncate(keep)

    def compact_if_needed(self, engine, threshold_chars: int = 600000, keep_recent_pairs: int = 3) -> bool:
        """Summarize a validated prefix outside the lock, preserving new appends and pending turns.

        Returns True if committed, False if unnecessary or the provider failed. A concurrent
        rewrite raises CompactionConflict so the caller can retry with fresh history.
        """
        if type(keep_recent_pairs) is not int or keep_recent_pairs < 0:
            raise ValueError("keep_recent_pairs must be a nonnegative integer")
        state = self._store.read()
        lines = entries(state.messages)
        all_msgs = [m or {} for _, m in lines]
        turns = [i for i, m in enumerate(all_msgs) if self._is_turn(m)]
        prev = state.summary.lstrip("\ufeff").strip()
        if len(self._render(prev, all_msgs)) <= threshold_chars or len(turns) <= keep_recent_pairs * 2:
            return False
        keep = keep_recent_pairs * 2
        cutoff = turns[-keep] if keep else len(all_msgs)
        groups, pending = self._turn_groups(all_msgs)
        if pending:
            cutoff = min(cutoff, min(pending))
        # A retained answer must retain its question, even when two turns overlap.
        while True:
            earlier = min([cutoff] + [a for a, b in groups if a < cutoff <= b])
            if earlier == cutoff:
                break
            cutoff = earlier
        older_indices = {i for i in turns if i < cutoff}
        if not older_indices:
            return False
        older = [all_msgs[i] for i in sorted(older_indices)]
        transcript = "\n".join(f"{self._who(m.get('role',''))}: {m.get('content','')}" for m in older)
        prompt = ("Compress the conversation below into 4–7 tight bullet points that preserve decisions, "
                  "concrete facts/numbers, and open items. No preamble.\n\n"
                  + (f"Existing summary to fold in:\n{prev}\n\n" if prev else "") + transcript)
        res = engine.run(system="You are a precise note-taker. Output only the bullet summary.",
                         prompt=prompt, allow_tools=False)
        if not res.ok or not res.output.strip():
            return False  # A provider/auth failure must never discard the unsummarized history.
        # The model already folded in the old summary. Appending it again duplicates old context.
        kept = "".join(line for i, (line, _) in enumerate(lines) if i not in older_indices)
        self._store.compact(state, kept, res.output.strip())
        return True

    @staticmethod
    def list_threads(agent_dir) -> list[str]:
        from .job_history import JOB_PREFIX
        base = Path(agent_dir) / "threads"
        return sorted(p.name for p in base.iterdir() if p.is_dir() and not p.name.startswith(JOB_PREFIX)) if base.is_dir() else []
