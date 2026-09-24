"""Agent lifecycle — retire, reinstate, delete.

An agent is a folder: `agents/<id>/` holding its agent.json, mandate, soul, tenets, jobs, threads,
memory, run history and capability grants. Every part of ARMADA that asks "who is in this realm"
answers by listing that directory — the reader, the scheduler, the capability scan, the inbox
sweep, the delegation roster the system prompt is built from.

So retiring moves the folder to `retired/<id>/` and that is the whole mechanism. The alternative —
a `retired: true` flag in agent.json plus a filter at every site that iterates agents — is a filter
you can forget in one place, and the place you forget is the scheduler, which then runs a retired
agent's jobs at 3am. A folder the scheduler cannot see cannot be run by it. "Jobs turned off" comes
out of the move rather than out of editing seven job files and hoping to put them back correctly.

Nothing is edited on the way out except a timestamp. That is what makes reinstating exact: the
jobs, their schedules and their on/off states, the threads, the memories, the grants and the run
history all travel together and come back as they were. The two stamps we do write — `retired` and
`reinstated` — exist because the week strip needs them: a job with a 09:00 cron that spent a
fortnight retired should not come back showing fourteen missed days. It wasn't missed. It wasn't
due.

What stays behind, deliberately:

* **Goal membership.** A goal's `agents:` list keeps the retired id, so reinstating restores the
  goal without anyone re-adding them. `goals_for_agent` is only ever called for agents that exist,
  so a retired id sitting in that list costs nothing while they are gone.
* **Realm capability catalogue.** Grants live in the agent's own toolkit and travel with it; the
  "Available to" list on a realm capability is computed from the live agents at render time, so a
  retired agent drops off it and comes back on by itself.
* **Other agents' inboxes.** A message from a retired agent keeps its sender name. It is a record
  of something that happened, not a live link.

What is genuinely lost while an agent is retired is its share of the usage charts, which read the
live agents. That is visible and reversible rather than silent: the tokens come back when they do.
"""
from __future__ import annotations

import datetime as _dt
import json
import shutil
from pathlib import Path

from . import util
from .realmops import _recycle
import logging
from .util import swallowed
log = logging.getLogger(__name__)

RETIRED_DIR = "retired"


def _now() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _read_json(p: Path) -> dict:
    try:
        d = json.loads(p.read_text(encoding="utf-8-sig"))
        return d if isinstance(d, dict) else {}
    except Exception:  # noqa — an unreadable agent.json must not break the listing
        swallowed(log, '_read_json: failed; returning a fallback')
        return {}


def live_dir(realm_root, agent_id: str) -> Path:
    return Path(realm_root) / "agents" / util.safe_seg(agent_id, "agent")


def retired_dir(realm_root, agent_id: str = "") -> Path:
    base = Path(realm_root) / RETIRED_DIR
    return base / util.safe_seg(agent_id, "agent") if agent_id else base


def list_retired(realm_root) -> list[dict]:
    """Retired agents, newest first — enough of each to fill the Reinstate form.

    Newest first because the one you want back is usually the one you just let go.
    """
    base = retired_dir(realm_root)
    out = []
    for d in (sorted(p for p in base.iterdir() if p.is_dir()) if base.is_dir() else []):
        c = _read_json(d / "agent.json")
        if not c:
            continue
        out.append({
            "id": c.get("id") or d.name,
            "display": c.get("display") or d.name.title(),
            "role": c.get("role") or "",
            "leader": c.get("leader") or "",
            "color": c.get("color") or "",
            "autonomy": c.get("autonomy") or "manual",
            "model": c.get("model") or "",
            "effort": c.get("effort") or "",
            "coordinator": bool(c.get("coordinator")),
            "retired": str(c.get("retired") or ""),
            "appointed": str(c.get("appointed") or c.get("created") or ""),
            "jobs": len(list((d / "jobs").glob("*.json"))) if (d / "jobs").is_dir() else 0,
            "threads": len(list((d / "threads").glob("*.md"))) if (d / "threads").is_dir() else 0,
        })
    return sorted(out, key=lambda a: a["retired"], reverse=True)


def is_retired(realm_root, agent_id: str) -> bool:
    return retired_dir(realm_root, agent_id).is_dir()


def reinstated_at(realm_root, agent_id: str) -> str:
    """When this agent last came back, or ''. What the week strip uses so a job isn't marked as
    having missed fire times that fell while its owner was retired."""
    return str(_read_json(live_dir(realm_root, agent_id) / "agent.json").get("reinstated") or "")


def _live_agents(realm_root) -> list[Path]:
    base = Path(realm_root) / "agents"
    return sorted(p for p in base.iterdir() if p.is_dir()) if base.is_dir() else []


def _guard(realm_root, agent_id: str, verb: str) -> dict:
    """The two agents you must not remove, whichever way you are removing them."""
    d = live_dir(realm_root, agent_id)
    if not d.is_dir():
        return {"ok": False, "error": f"There's no agent called {agent_id} in this realm."}
    c = _read_json(d / "agent.json")
    if c.get("coordinator"):
        return {"ok": False, "error": (
            f"{c.get('display') or agent_id} is this realm's coordinator, and a realm needs one — "
            f"every agent's briefing names it, and goals are assigned through it. Appoint another "
            f"coordinator first, then {verb} this one.")}
    others = [p for p in _live_agents(realm_root) if p.name != d.name]
    if not others:
        return {"ok": False, "error": (
            f"{c.get('display') or agent_id} is the only agent left. A realm with nobody in it "
            f"can't do anything — appoint someone else first.")}
    return {"ok": True, "config": c}


def retire(realm_root, agent_id: str) -> dict:
    """Move an agent out of the realm without touching what is inside it.

    Reversible by construction: nothing is deleted, nothing is rewritten except the stamp, so
    reinstating is the same move in the other direction.
    """
    g = _guard(realm_root, agent_id, "retire")
    if not g["ok"]:
        return g
    src = live_dir(realm_root, agent_id)
    dst = retired_dir(realm_root, agent_id)
    if dst.exists():
        return {"ok": False, "error": (
            f"There's already a retired agent in {dst.name}. Reinstate or delete that one first.")}
    cfg = dict(g["config"])
    cfg["retired"] = _now()
    cfg.pop("reinstated", None)
    try:
        util.write_json_atomic(src / "agent.json", cfg)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
    except Exception as e:  # noqa
        swallowed(log, 'retire: failed; error returned to the caller')
        return {"ok": False, "error": f"Couldn't retire {agent_id}: {str(e)[:160]}"}
    return {"ok": True, "id": agent_id, "display": cfg.get("display") or agent_id,
            "retired": cfg["retired"], "path": str(dst)}


def reinstate(realm_root, agent_id: str, overrides: dict | None = None) -> dict:
    """Bring a retired agent back, optionally with edits made on the way in.

    `overrides` carries whatever the Reinstate form changed — a new name, a different model. The
    rest of agent.json is left exactly as it was, which is the point: you are bringing back an
    agent, not filling in a new one that happens to share a name.
    """
    src = retired_dir(realm_root, agent_id)
    if not src.is_dir():
        return {"ok": False, "error": f"There's no retired agent called {agent_id}."}
    dst = live_dir(realm_root, agent_id)
    if dst.exists():
        return {"ok": False, "error": (
            f"An agent called {agent_id} is already in this realm. Rename or remove it first.")}
    cfg = _read_json(src / "agent.json")
    for k, v in (overrides or {}).items():
        v = v.strip() if isinstance(v, str) else v
        if v not in ("", None):
            cfg[k] = v
    cfg.pop("retired", None)
    # The week strip reads this: a job cannot have missed a fire time that fell while its owner was
    # out of the realm. Without it, an agent back from a fortnight away arrives wearing a fortnight
    # of red — two true statements ("the cron says 09:00", "nothing ran") adding up to a false one.
    cfg["reinstated"] = _now()
    try:
        util.write_json_atomic(src / "agent.json", cfg)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
    except Exception as e:  # noqa
        swallowed(log, 'reinstate: failed; error returned to the caller')
        return {"ok": False, "error": f"Couldn't reinstate {agent_id}: {str(e)[:160]}"}
    return {"ok": True, "id": agent_id, "display": cfg.get("display") or agent_id,
            "reinstated": cfg["reinstated"], "path": str(dst)}


def delete(realm_root, agent_id: str, permanent: bool = False) -> dict:
    """Delete an agent's folder — live or retired.

    Recycle Bin by default, and never silently escalated to an unrecoverable wipe because the safe
    path failed: an agent folder is threads, memories and months of run history, and "delete" in an
    app means the thing you can get back.
    """
    live, ret = live_dir(realm_root, agent_id), retired_dir(realm_root, agent_id)
    if live.is_dir():
        g = _guard(realm_root, agent_id, "delete")
        if not g["ok"]:
            return g
        src, was = live, "live"
    elif ret.is_dir():
        src, was = ret, "retired"
    else:
        return {"ok": False, "error": f"There's no agent called {agent_id} in this realm."}
    if not permanent:
        r = _recycle(src.resolve())
        if r.get("ok"):
            return {"ok": True, "recycled": True, "id": agent_id, "was": was}
        if r.get("error") != "no-recycle-bin":
            return {"ok": False, "error": f"Couldn't move it to the Recycle Bin: {r.get('error')}"}
    try:
        shutil.rmtree(src)
    except Exception as e:  # noqa
        swallowed(log, 'delete: failed; error returned to the caller')
        return {"ok": False, "error": str(e)[:200]}
    return {"ok": True, "recycled": False, "id": agent_id, "was": was}
