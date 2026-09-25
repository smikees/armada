"""Remedies: the fixed list of app actions Alexander may propose (ADR-012, docs/dev/ALEXANDER.md).

He names one and its arguments in a ```remedy block; `card()` validates that against this list and
the realm on disk and returns what the page shows — a sentence saying exactly what will happen,
one button, and the app endpoint the button posts to. The endpoint is the same one the app's own
button uses, so a remedy does nothing the owner couldn't do by hand, and each endpoint keeps its
own checks. Anything that doesn't validate returns None, and the page shows nothing.

Adding a remedy is a code change and a release. He can't invent one.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Optional

from ..util import UnsafeSegment, safe_seg

# Pages he may send the owner to. Paths only — never a URL he makes up.
PAGES = {
    "overview": ("/", "Overview"),
    "agents": ("/ministers", "Agents"),
    "jobs": ("/jobs", "Jobs"),
    "goals": ("/goals", "Goals"),
    "memory": ("/memory", "Memory"),
    "capabilities": ("/skills", "Capabilities"),
    "artefacts": ("/artefacts", "Artefacts"),
    "inbox": ("/inbox", "Inbox"),
    "settings-realm": ("/settings?tab=realm", "Settings → Realm"),
    "settings-user": ("/settings?tab=user", "Settings → User"),
    "settings-app": ("/settings?tab=app", "Settings → App"),
    "help": ("/docs", "Help"),
}


def _job_file(realm_root, agent: str, job: str) -> Optional[Path]:
    try:
        p = Path(realm_root) / "agents" / safe_seg(agent, "agent") / "jobs" / f"{safe_seg(job, 'job')}.json"
    except UnsafeSegment:                 # a malformed or traversing name is simply not a job
        return None
    return p if p.is_file() else None


def _job_name(p: Path, fallback: str) -> str:
    try:
        return str(json.loads(p.read_text(encoding="utf-8-sig")).get("name") or fallback)
    except (OSError, json.JSONDecodeError):
        return fallback


def _agent_name(realm_root, agent: str) -> str:
    try:
        a = json.loads((Path(realm_root) / "agents" / safe_seg(agent, "agent") / "agent.json")
                       .read_text(encoding="utf-8-sig"))
        return str(a.get("display") or agent.title())
    except (UnsafeSegment, OSError, json.JSONDecodeError, AttributeError):
        return agent


def _run_job(realm_root, args: dict) -> Optional[dict]:
    agent, job = str(args.get("agent") or ""), str(args.get("job") or "")
    p = _job_file(realm_root, agent, job) if agent and job else None
    if not p:
        return None
    name, who = _job_name(p, job), _agent_name(realm_root, agent)
    return {"what": f"Run “{name}” for {who} now, once. It uses your Claude plan like any run.",
            "button": "Run it now", "endpoint": "/api/run",
            "body": {"agent": agent, "job": job, "engine": "claude"}}


def _set_job(on: bool) -> Callable[[object, dict], Optional[dict]]:
    def build(realm_root, args: dict) -> Optional[dict]:
        agent, job = str(args.get("agent") or ""), str(args.get("job") or "")
        p = _job_file(realm_root, agent, job) if agent and job else None
        if not p:
            return None
        name, who = _job_name(p, job), _agent_name(realm_root, agent)
        what = (f"Switch “{name}” ({who}) on, so the scheduler runs it again." if on else
                f"Switch “{name}” ({who}) off. It won't run until you switch it back on.")
        return {"what": what, "button": "Switch on" if on else "Switch off",
                "endpoint": "/api/job-enable", "body": {"agent": agent, "job": job, "enabled": on}}
    return build


def _start_scheduler(realm_root, args: dict) -> dict:
    return {"what": "Start the scheduler, the background process that runs your jobs on time.",
            "button": "Start the scheduler", "endpoint": "/api/scheduler-start", "body": {}}


def _refresh_environment(realm_root, args: dict) -> dict:
    return {"what": "Rebuild the realm's system memory from what's on disk now, so every agent "
                    "sees the current team, jobs and tools.",
            "button": "Refresh it", "endpoint": "/api/refresh-system", "body": {}}


def _check_updates(realm_root, args: dict) -> dict:
    return {"what": "Check for a newer ARMADA and, if there is one, get it ready to install.",
            "button": "Check now", "endpoint": "/api/check-update", "method": "GET", "body": {}}


def _open_page(realm_root, args: dict) -> Optional[dict]:
    key = str(args.get("page") or "")
    if key not in PAGES:
        return None
    path, label = PAGES[key]
    return {"what": f"Open {label}.", "button": f"Open {label}", "href": path}


# name -> (argument names, one line for his context, builder)
REMEDIES: dict[str, tuple[tuple[str, ...], str, Callable]] = {
    "start_scheduler": ((), "start the background scheduler when it isn't running", _start_scheduler),
    "run_job": (("agent", "job"), "run one job now, once (agent id, job id)", _run_job),
    "enable_job": (("agent", "job"), "switch a job on (agent id, job id)", _set_job(True)),
    "disable_job": (("agent", "job"), "switch a job off (agent id, job id)", _set_job(False)),
    "refresh_environment": ((), "rebuild the realm's system memory from disk", _refresh_environment),
    "check_updates": ((), "check for a newer ARMADA", _check_updates),
    "open_page": (("page",), "take the owner to a page; page is one of: " + ", ".join(PAGES), _open_page),
}


def card(realm_root, proposal) -> Optional[dict]:
    """The card for one ```remedy proposal, or None when it doesn't validate."""
    if not isinstance(proposal, dict):
        return None
    name = proposal.get("name")
    args = proposal.get("args") or {}
    if name not in REMEDIES or not isinstance(args, dict):
        return None
    wanted, _line, build = REMEDIES[name]
    if set(args) - set(wanted) or any(not isinstance(args.get(k), str) or not args.get(k) for k in wanted):
        return None
    out = build(realm_root, args)
    if not out:
        return None
    why = proposal.get("why")
    return {"name": name, **out, "why": str(why)[:300] if isinstance(why, str) else ""}


def context() -> str:
    """The `<remedies>` section of his context: names, arguments, one line each."""
    lines = []
    for name, (wanted, line, _b) in REMEDIES.items():
        sig = ", ".join(wanted)
        lines.append(f"- {name}({sig}): {line}")
    return "\n".join(lines)
