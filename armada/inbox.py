"""Agent-to-agent delegation — an inbox per agent.

An agent can ask a teammate to do something. The ask lands in the recipient's inbox; the recipient
acts on it on its own cadence, in its own dedicated thread, with all of its own context. That's the
point: Steve knows how the daily price-check job is built, so "add the Fitbit Air to it" belongs
with Steve rather than being explained to someone else.

Three things this module exists to make safe.

**Cost.** Checking an inbox is a plain file read — no engine, no tokens. The agent is only invoked
when a message is actually waiting. So a one-minute cadence means "act within a minute of being
asked", not "wake an agent 1,440 times a day to find nothing".

**Loops.** Two agents politely answering each other is an unbounded bill. Every message carries the
chain it came from and how many hops it's taken; chains die at _MAX_HOPS, identical asks collapse,
and each agent has a ceiling on how many delegated tasks it will run per hour.

**Exactly once.** Claiming a message is an atomic rename before the agent runs, so a scheduler
restart mid-task can't replay it.

Delegated work is never more privileged than self-directed work: the receiving agent runs with its
normal permissions, so anything that changes the realm (editing a job, installing a capability)
still goes through the owner's approval gate exactly as it would otherwise.
"""
from __future__ import annotations
import datetime as _dt
import hashlib
import json
import os
import re
import time
from pathlib import Path

from . import util
import logging
from .util import swallowed
log = logging.getLogger(__name__)

PENDING, RUNNING, DONE = "pending", "running", "done"

_MAX_HOPS = 3           # A asks B asks C — then the chain stops
_MAX_PER_HOUR = 12      # per recipient; a runaway delegation stalls instead of billing
_MAX_PER_RUN = 3        # messages handled in one dispatch pass, so one agent can't hog a tick
_DEDUPE_WINDOW_H = 6    # identical ask from the same sender inside this window is dropped

# Cadence options, in minutes. "off" means this agent never acts on its inbox.
CADENCES = {"minute": 1, "hour": 60, "day": 1440, "off": 0}
DEFAULT_CADENCE = "hour"

# Who may assign work to an agent. "nobody" is still honoured — realms configured before the
# on/off switch existed may have it saved, and a hand-edited realm.json can still say it — but it
# is no longer offered: it says exactly what the switch says, and two controls for one decision is
# how you end up with a UI where the switch reads "on" and nothing works. Reading a stored
# "nobody" therefore reports the switch as off (see agent_enabled / enabled).
ACCEPTS = {"anyone": "Anyone in the realm", "coordinator": "The coordinator only", "nobody": "Nobody"}
ACCEPTS_CHOICES = {k: v for k, v in ACCEPTS.items() if k != "nobody"}   # what the UI offers
DEFAULT_ACCEPTS = "anyone"

INBOX_THREAD = "inbox"   # delegated work gets its own thread, away from the owner's conversations
REPLY_PREFIX = "reply-"  # a reply's id is REPLY_PREFIX + the id of the task it answers


def parent_id(msg: dict) -> str:
    """The task a reply answers, or "" for an ordinary message.

    Prefers the stored `parent`; falls back to the id convention so replies written before that
    field existed still pair up.
    """
    if not msg.get("reply"):
        return ""
    p = str(msg.get("parent") or "")
    if p:
        return p
    mid = str(msg.get("id") or "")
    return mid[len(REPLY_PREFIX):] if mid.startswith(REPLY_PREFIX) else ""


def threaded(items: list) -> list:
    """Order a flat list so each reply sits directly under the message it answers.

    Returns [(message, depth)] with depth 1 for replies. A reply whose original isn't in this list
    — filtered out, deleted, or older than the section — stays at top level rather than vanishing.
    """
    replies: dict = {}
    for m in items:
        pid = parent_id(m)
        if pid:
            replies.setdefault(pid, []).append(m)
    ids = {str(m.get("id")) for m in items if not parent_id(m)}
    out = []
    for m in items:
        if parent_id(m):
            if parent_id(m) in ids:
                continue                      # emitted under its parent below
            out.append((m, 0))                # orphan: show it rather than lose it
            continue
        out.append((m, 0))
        for r in replies.get(str(m.get("id")), []):
            out.append((r, 1))
    return out


# ---- paths ------------------------------------------------------------------------------------

def _agent_dir(realm_root, agent_id: str) -> Path:
    return Path(realm_root) / "agents" / util.safe_seg(agent_id, "agent")


def _box(realm_root, agent_id: str, state: str = PENDING) -> Path:
    return _agent_dir(realm_root, agent_id) / "inbox" / state


def _read(p: Path) -> dict | None:
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
        return d if isinstance(d, dict) else None
    except Exception:  # noqa
        log.debug('_read: failed; returning a fallback', exc_info=True)
        return None


def _list(realm_root, agent_id: str, state: str) -> list:
    d = _box(realm_root, agent_id, state)
    if not d.is_dir():
        return []
    out = []
    for f in sorted(d.glob("*.json")):
        m = _read(f)
        if m:
            m["_file"] = str(f)
            out.append(m)
    return out


# ---- settings ---------------------------------------------------------------------------------

def _realm_cfg(realm_root) -> dict:
    try:
        js = json.loads((Path(realm_root) / "realm.json").read_text(encoding="utf-8-sig"))
        return (js.get("inbox") or {}) if isinstance(js, dict) else {}
    except Exception:  # noqa
        swallowed(log, '_realm_cfg: failed; returning a fallback')
        return {}


def _agent_cfg(realm_root, agent_id: str) -> dict:
    try:
        js = json.loads((_agent_dir(realm_root, agent_id) / "agent.json").read_text(encoding="utf-8-sig"))
        return (js.get("inbox") or {}) if isinstance(js, dict) else {}
    except Exception:  # noqa
        swallowed(log, '_agent_cfg: failed; returning a fallback')
        return {}


def enabled(realm_root) -> bool:
    """Realm-wide switch. Delegation changes what the realm does while nobody's watching, so it
    can be turned off wholesale without unpicking every agent's cadence."""
    cfg = _realm_cfg(realm_root)
    if cfg.get("accepts") == "nobody":
        return False                     # the old way of saying the same thing
    return bool(cfg.get("enabled", True))


def agent_enabled(realm_root, agent_id: str) -> bool:
    """Per-agent switch, on by default. Distinct from a cadence of 'off': that says "I'll get to my
    inbox never", this says "don't involve me in agent-to-agent work at all", which also means
    nobody can queue anything for this agent in the first place."""
    cfg = _agent_cfg(realm_root, agent_id)
    if cfg.get("accepts") == "nobody":
        return False                     # the old way of saying the same thing
    return bool(cfg.get("enabled", True))


def cadence(realm_root, agent_id: str) -> str:
    """Per-agent, falling back to the realm default — the same pattern as model and effort."""
    if not agent_enabled(realm_root, agent_id):
        return "off"
    a = _agent_cfg(realm_root, agent_id).get("cadence")
    if a in CADENCES:
        return a
    r = _realm_cfg(realm_root).get("cadence")
    return r if r in CADENCES else DEFAULT_CADENCE


def accepts_from(realm_root, agent_id: str) -> str:
    if not agent_enabled(realm_root, agent_id):
        return "nobody"
    a = _agent_cfg(realm_root, agent_id).get("accepts")
    if a in ACCEPTS:
        return a
    r = _realm_cfg(realm_root).get("accepts")
    return r if r in ACCEPTS else DEFAULT_ACCEPTS


def _is_coordinator(realm_root, agent_id: str) -> bool:
    try:
        js = json.loads((_agent_dir(realm_root, agent_id) / "agent.json").read_text(encoding="utf-8-sig"))
        return bool(js.get("is_coordinator") or js.get("coordinator"))
    except Exception:  # noqa
        swallowed(log, '_is_coordinator: failed; returning a fallback')
        return False


# ---- sending ----------------------------------------------------------------------------------

def _fingerprint(frm: str, ask: str) -> str:
    norm = re.sub(r"\s+", " ", str(ask or "")).strip().lower()
    return hashlib.sha1(f"{frm}|{norm}".encode("utf-8")).hexdigest()[:16]


def _recent_fingerprints(realm_root, agent_id: str) -> set:
    cutoff = time.time() - _DEDUPE_WINDOW_H * 3600
    seen = set()
    for state in (PENDING, RUNNING, DONE):
        for m in _list(realm_root, agent_id, state):
            try:
                if _dt.datetime.fromisoformat(m.get("created", "")).timestamp() >= cutoff:
                    seen.add(m.get("fingerprint", ""))
            except Exception:  # noqa
                log.debug('_recent_fingerprints: failed; skipping this one', exc_info=True)
                continue
    return seen


def _ran_last_hour(realm_root, agent_id: str) -> int:
    cutoff = time.time() - 3600
    n = 0
    for m in _list(realm_root, agent_id, DONE):
        try:
            if _dt.datetime.fromisoformat(m.get("started", "") or m.get("created", "")).timestamp() >= cutoff:
                n += 1
        except Exception:  # noqa
            log.debug('_ran_last_hour: failed; skipping this one', exc_info=True)
            continue
    return n


def send(realm_root, frm: str, to: str, ask: str, context: str = "",
         origin: str = "", hops: int = 0) -> dict:
    """Queue a task for another agent. Returns {ok, id} or {ok:False, error, reason}."""
    ask = str(ask or "").strip()
    if not ask:
        return {"ok": False, "error": "An inbox message needs an ask.", "reason": "empty"}
    if not enabled(realm_root):
        return {"ok": False, "error": "Agent-to-agent tasks are switched off for this realm.",
                "reason": "disabled"}
    to = util.safe_seg(to, "agent")
    frm = util.safe_seg(frm, "agent")
    if to == frm:
        return {"ok": False, "error": "An agent can't assign work to itself.", "reason": "self"}
    if not _agent_dir(realm_root, to).is_dir():
        return {"ok": False, "error": f"There's no agent '{to}' in this realm.", "reason": "unknown"}
    # The per-agent switch takes both directions: "off" means this agent is out of the delegation
    # network, not merely deaf to it. Checked before accepts-from so the message names the real cause.
    if not agent_enabled(realm_root, to):
        return {"ok": False, "error": f"{to} has agent-to-agent communication switched off.",
                "reason": "refused"}
    if not agent_enabled(realm_root, frm):
        return {"ok": False, "error": f"{frm} has agent-to-agent communication switched off.",
                "reason": "refused"}
    if hops >= _MAX_HOPS:
        # The chain has gone far enough — stop rather than let a misunderstanding ping-pong.
        return {"ok": False, "error": "Delegation chain too long; stopping here.", "reason": "hops"}
    acc = accepts_from(realm_root, to)
    if acc == "nobody":
        return {"ok": False, "error": f"{to} doesn't accept tasks from other agents.", "reason": "refused"}
    if acc == "coordinator" and not _is_coordinator(realm_root, frm):
        return {"ok": False, "error": f"{to} only accepts tasks from the coordinator.", "reason": "refused"}
    fp = _fingerprint(frm, ask)
    if fp in _recent_fingerprints(realm_root, to):
        return {"ok": False, "error": "That exact task was already sent recently.", "reason": "duplicate"}
    now = _dt.datetime.now().astimezone()
    mid = f"{now.strftime('%Y%m%d-%H%M%S')}-{fp[:6]}"
    msg = {"id": mid, "from": frm, "to": to, "ask": ask[:4000], "context": str(context or "")[:4000],
           "created": now.isoformat(timespec="seconds"), "state": PENDING,
           "hops": int(hops), "origin": origin or frm, "fingerprint": fp}
    d = _box(realm_root, to, PENDING)
    d.mkdir(parents=True, exist_ok=True)
    util.write_json_atomic(d / f"{mid}.json", msg)
    return {"ok": True, "id": mid, "to": to}


# ---- dispatch ---------------------------------------------------------------------------------

def has_mail(realm_root, agent_id: str) -> bool:
    """The cheap check — a directory listing, no engine, no tokens."""
    d = _box(realm_root, agent_id, PENDING)
    try:
        return any(d.glob("*.json"))
    except Exception:  # noqa
        swallowed(log, 'has_mail: failed; returning a fallback')
        return False


def due(realm_root, agent_id: str, now=None) -> bool:
    """Has this agent's cadence elapsed since it last looked? Cadence is a latency promise, not a
    poll rate — with no mail waiting, being 'due' costs nothing."""
    cad = cadence(realm_root, agent_id)
    mins = CADENCES.get(cad, 0)
    if not mins:
        return False
    marker = _agent_dir(realm_root, agent_id) / "inbox" / ".last"
    try:
        last = _dt.datetime.fromisoformat(marker.read_text(encoding="utf-8").strip())
    except Exception:  # noqa
        log.debug('due: failed; returning a fallback', exc_info=True)
        return True
    now = now or _dt.datetime.now().astimezone()
    if last.tzinfo is None:
        last = last.astimezone()
    return (now - last).total_seconds() >= mins * 60


def mark_checked(realm_root, agent_id: str) -> None:
    m = _agent_dir(realm_root, agent_id) / "inbox" / ".last"
    try:
        m.parent.mkdir(parents=True, exist_ok=True)
        m.write_text(_dt.datetime.now().astimezone().isoformat(timespec="seconds"), encoding="utf-8")
    except Exception:  # noqa
        swallowed(log, 'mark_checked: failed; ignored')


def claim(realm_root, agent_id: str, msg: dict) -> dict | None:
    """Move a message from pending to running. The rename is the lock: if it fails, someone else
    got there first, so a restart mid-dispatch can't run the same ask twice."""
    src = Path(msg.get("_file", ""))
    if not src.is_file():
        return None
    dst_dir = _box(realm_root, agent_id, RUNNING)
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    try:
        os.replace(src, dst)          # atomic; raises if src vanished
    except Exception:  # noqa
        log.debug('claim: failed; returning a fallback', exc_info=True)
        return None
    m = _read(dst) or dict(msg)
    m["_file"] = str(dst)
    m["state"] = RUNNING
    m["started"] = _dt.datetime.now().astimezone().isoformat(timespec="seconds")
    try:
        util.write_json_atomic(dst, {k: v for k, v in m.items() if not k.startswith("_")})
    except Exception:  # noqa
        swallowed(log, 'claim: failed; ignored')
    return m


def complete(realm_root, agent_id: str, msg: dict, ok: bool, detail: str = "") -> None:
    """File the message as done and tell the sender how it went — without a reply, a failed
    delegation is invisible to whoever asked for it."""
    src = Path(msg.get("_file", ""))
    dst_dir = _box(realm_root, agent_id, DONE)
    dst_dir.mkdir(parents=True, exist_ok=True)
    rec = {k: v for k, v in msg.items() if not k.startswith("_")}
    rec.update({"state": DONE, "ok": bool(ok), "detail": str(detail or "")[:2000],
                "finished": _dt.datetime.now().astimezone().isoformat(timespec="seconds")})
    try:
        util.write_json_atomic(dst_dir / (src.name or f"{msg.get('id','x')}.json"), rec)
        if src.is_file():
            src.unlink()
    except Exception:  # noqa
        swallowed(log, 'complete: failed; ignored')
    # Reply to the sender as a plain note, NOT a new task: a reply must not start another chain.
    try:
        note = (f"{agent_id} {'completed' if ok else 'could not complete'} your request: "
                f"\"{str(msg.get('ask',''))[:160]}\"" + (f" — {detail[:300]}" if detail else ""))
        d = _box(realm_root, msg.get("from", ""), DONE)
        d.mkdir(parents=True, exist_ok=True)
        rid = f"{REPLY_PREFIX}{msg.get('id','x')}"
        util.write_json_atomic(d / f"{rid}.json", {
            "id": rid, "from": agent_id, "to": msg.get("from", ""), "ask": note, "reply": True,
            # the task this answers, stored outright — the UI pairs them to show a reply under the
            # message it belongs to, and that shouldn't depend on parsing an id
            "parent": msg.get("id", ""),
            "created": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "state": DONE, "ok": bool(ok), "hops": int(msg.get("hops", 0)),
            "origin": msg.get("origin", "")})
    except Exception:  # noqa
        swallowed(log, 'complete: failed; ignored')


def screen(realm_root, agent_id: str, msg: dict) -> tuple:
    """Enforce the rules at PICKUP, not just at send.

    Agents write inbox files directly with their Write tool (the same contract they use to propose
    jobs), so send() isn't the only way a message can appear. Checking here means the hop limit,
    the accepts-from setting and the hourly ceiling hold no matter how a message got there —
    including one an agent wrote by hand or copied.

    Returns (ok, reason). A rejected message is filed, not run: no engine, no tokens.
    """
    if msg.get("reply"):
        return False, "replies are notes, not tasks"
    ask = str(msg.get("ask", "")).strip()
    if not ask:
        return False, "no ask"
    frm = str(msg.get("from", "")).strip()
    if not frm:
        return False, "no sender"
    if frm == agent_id:
        return False, "an agent can't assign work to itself"
    try:
        hops = int(msg.get("hops", 1) or 1)
    except Exception:  # noqa
        log.debug('screen: failed; using a default', exc_info=True)
        hops = 1
    if hops > _MAX_HOPS:
        return False, f"delegation chain too long ({hops} hops)"
    if not agent_enabled(realm_root, agent_id):
        return False, "this agent has agent-to-agent communication switched off"
    acc = accepts_from(realm_root, agent_id)
    if acc == "nobody":
        return False, "this agent doesn't accept tasks from other agents"
    if acc == "coordinator" and not _is_coordinator(realm_root, frm):
        return False, "this agent only accepts tasks from the coordinator"
    if _ran_last_hour(realm_root, agent_id) >= _MAX_PER_HOUR:
        return False, "hourly limit for delegated tasks reached"
    return True, ""


def next_batch(realm_root, agent_id: str) -> list:
    """Messages to act on right now, honouring the per-agent hourly ceiling."""
    room = max(0, _MAX_PER_HOUR - _ran_last_hour(realm_root, agent_id))
    if room <= 0:
        return []
    return _list(realm_root, agent_id, PENDING)[:min(_MAX_PER_RUN, room)]


def prompt_for(msg: dict) -> str:
    """A self-contained prompt. The inbox thread is long-lived and carries unrelated asks, so an
    instruction must never depend on what else happens to be in that thread's history."""
    lines = [f"{msg.get('from','another agent')} has asked you to do this:",
             "", str(msg.get("ask", "")).strip(), ""]
    ctx = str(msg.get("context", "")).strip()
    if ctx:
        lines += ["Context they gave you:", ctx, ""]
    lines += ["Act on it now using your own knowledge and capabilities. If it needs a change that "
              "requires the owner's approval (editing a scheduled job, installing a capability), "
              "propose it the usual way and say so. If you can't do it, say plainly why — your "
              "answer is sent back to them."]
    return "\n".join(lines)


def all_messages(realm_root, recent_hours: int = 24) -> dict:
    """Everything across every agent, split the way the page shows it: what's still waiting, what
    was handled recently, and the older pile that belongs in the archive."""
    waiting, recent, archive = [], [], []
    adir = Path(realm_root) / "agents"
    if not adir.is_dir():
        return {"waiting": [], "recent": [], "archive": []}
    cutoff = time.time() - recent_hours * 3600
    for d in sorted(p for p in adir.iterdir() if p.is_dir()):
        aid = d.name
        for state in (PENDING, RUNNING, DONE):
            for m in _list(realm_root, aid, state):
                m["agent"] = aid
                m["state"] = state
                if state in (PENDING, RUNNING):
                    waiting.append(m)
                    continue
                stamp = m.get("finished") or m.get("started") or m.get("created") or ""
                try:
                    fresh = _dt.datetime.fromisoformat(stamp).timestamp() >= cutoff
                except Exception:  # noqa — undateable entries belong in the archive
                    log.debug('all_messages: failed; using a default', exc_info=True)
                    fresh = False
                (recent if fresh else archive).append(m)

    def key(m):
        return m.get("finished") or m.get("started") or m.get("created") or ""
    waiting.sort(key=key, reverse=True)
    recent.sort(key=key, reverse=True)
    archive.sort(key=key, reverse=True)
    return {"waiting": waiting, "recent": recent, "archive": archive}


def _find(realm_root, agent_id: str, msg_id: str) -> tuple:
    for state in (PENDING, RUNNING, DONE):
        for m in _list(realm_root, agent_id, state):
            if m.get("id") == msg_id:
                return m, state
    return None, ""


def requeue(realm_root, agent_id: str, msg_id: str) -> dict:
    """Mark a handled message unread — it goes back to pending and is acted on again next pass.

    The outcome fields are cleared so it reads as genuinely unhandled, and the hop count is left
    alone: re-running a task must not become a way around the chain limit.
    """
    m, state = _find(realm_root, agent_id, msg_id)
    if not m:
        return {"ok": False, "error": "That message is no longer here."}
    if state == PENDING:
        return {"ok": False, "error": "That message is already waiting."}
    if m.get("reply"):
        return {"ok": False, "error": "Replies are notes, not tasks — there's nothing to re-run."}
    rec = {k: v for k, v in m.items() if not k.startswith("_")}
    for gone in ("ok", "detail", "finished", "started"):
        rec.pop(gone, None)
    rec["state"] = PENDING
    rec["requeued"] = _dt.datetime.now().astimezone().isoformat(timespec="seconds")
    dst = _box(realm_root, agent_id, PENDING)
    dst.mkdir(parents=True, exist_ok=True)
    try:
        util.write_json_atomic(dst / f"{msg_id}.json", rec)
        old = Path(m.get("_file", ""))
        if old.is_file() and old.parent != dst:
            old.unlink()
        return {"ok": True}
    except Exception as e:  # noqa
        swallowed(log, 'requeue: failed; error returned to the caller')
        return {"ok": False, "error": str(e)[:200]}


def delete(realm_root, agent_id: str, msg_id: str) -> dict:
    m, _state = _find(realm_root, agent_id, msg_id)
    if not m:
        return {"ok": False, "error": "That message is no longer here."}
    try:
        Path(m["_file"]).unlink()
        return {"ok": True}
    except Exception as e:  # noqa
        swallowed(log, 'delete: failed; error returned to the caller')
        return {"ok": False, "error": str(e)[:200]}


def counts(realm_root, agent_id: str) -> dict:
    return {"pending": len(_list(realm_root, agent_id, PENDING)),
            "running": len(_list(realm_root, agent_id, RUNNING)),
            "done": len(_list(realm_root, agent_id, DONE))}
