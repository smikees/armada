"""Is this realm actually able to run *here*?

A realm carries its team, memory, goals and jobs, but not the machine they were built around. Move
one to a new computer and the parts that don't travel are invisible until something fails quietly
at 03:00: the workspace folder is somewhere else, the engine isn't signed in, Telegram was never
linked so the failure notice goes nowhere either.

So a realm is checked when it arrives, and a realm that can't work is *held* rather than left to
fail nightly. A held realm is loud on arrival, which is the one moment the owner is looking at it.

Two severities, and the distinction is the whole design:

* **blocking** — every agent run would fail. No engine, no workspace. Holding the scheduler here
  prevents a week of identical failures nobody reads.
* **warning** — something is degraded but work still happens. Telegram unlinked means notifications
  don't reach a phone; the jobs still run and the bell still fills.

Never blocking: anything cosmetic, and anything about the *content* of jobs. A realm whose prompts
are wrong is not ARMADA's business.

One exception, about trust rather than correctness: a realm **adopted** from another folder holds
until its owner has seen what it will run (THREAT_MODEL T5). Its command jobs are shell commands on a
schedule and its agent jobs run with tools — someone else's realm is someone else's code. The hold
lifts when the owner allows it from the Jobs page, not when a check starts passing.
"""
from __future__ import annotations

import json
from pathlib import Path
import logging
from .util import swallowed
log = logging.getLogger(__name__)

BLOCK, WARN, OK = "blocking", "warning", "ok"


def _check(id_, label, ok, detail, severity=BLOCK, fix="", action=""):
    return {"id": id_, "label": label, "ok": bool(ok), "detail": str(detail or "")[:300],
            "severity": OK if ok else severity, "fix": fix, "action": action}


def engine_check(engine: str = "claude") -> dict:
    from .engine import get_engine
    try:
        ok, detail = get_engine(engine).doctor()
    except Exception as e:  # noqa — an unknown engine name shouldn't crash the report
        swallowed(log, 'engine_check: failed; recorded as an error')
        ok, detail = False, f"{type(e).__name__}: {e}"
    return _check("engine", f"Engine ({engine})", ok, detail, BLOCK,
                  fix="Install Claude Code and run `claude login`.")


def approot_check(realm_root) -> dict:
    """Is this realm inside ARMADA's root folder?

    Blocking, because a realm outside the root is a realm no boundary applies to. It is also the
    one failure a person can't discover by using the app — everything looks normal right up until
    it matters.
    """
    from . import approot
    if not approot.configured():
        return _check("approot", "App root", False,
                      "ARMADA has no root folder set on this machine.", BLOCK,
                      fix="Set the root folder in Settings.", action="set-approot")
    if not approot.exists():
        return _check("approot", "App root", False,
                      f"{approot.root()} doesn't exist on this machine.", BLOCK,
                      fix="Point ARMADA at the folder as it is named here.", action="set-approot")
    if not approot.contains(realm_root):
        return _check("approot", "App root", False,
                      f"This realm sits outside the root ({approot.root()}).", BLOCK,
                      fix="Move the realm inside the root folder, then add it again.",
                      action="set-approot")
    return _check("approot", "App root", True, approot.root())


def workspace_check(realm_root) -> dict:
    from . import workspace as ws
    root = ws.root(realm_root)
    if not root:
        # Only a problem if something actually refers to it. A realm whose jobs never mention a
        # path doesn't need a workspace, and demanding one would be ceremony.
        guess = ws.detect_root(realm_root)
        if guess:
            return _check("workspace", "Workspace folder", False,
                          f"Jobs in this realm refer to {guess}, but no workspace root is set.",
                          BLOCK, fix=f"Set the workspace root (it was {guess} on the old machine).",
                          action="set-workspace")
        return _check("workspace", "Workspace folder", True, "Not needed — no job refers to one.")
    if not ws.exists(realm_root):
        return _check("workspace", "Workspace folder", False,
                      f"{root} does not exist on this machine.", BLOCK,
                      fix="Point the realm at the folder as it is named here.",
                      action="set-workspace")
    return _check("workspace", "Workspace folder", True, root)


def telegram_check() -> dict:
    try:
        from . import telegram as tg
        if tg.ready():
            return _check("telegram", "Telegram", True, "linked")
        return _check("telegram", "Telegram", False,
                      "Not linked on this machine — notifications stay in the app.", WARN,
                      fix="Link it in Settings if you want alerts on your phone.",
                      action="open-telegram-settings")
    except Exception as e:  # noqa
        swallowed(log, 'telegram_check: failed; error returned to the caller')
        return _check("telegram", "Telegram", False, f"{type(e).__name__}: {e}", WARN)


def realm_check(realm_root) -> list:
    """The realm's own files parse and hold what a realm needs."""
    rr = Path(realm_root)
    out = []
    has = (rr / "realm.json").exists() or (rr / "agents").is_dir()
    out.append(_check("realm", "Realm folder", has, str(rr) if has else f"{rr} — no realm.json or agents/",
                      BLOCK, fix="Point ARMADA at the extracted realm folder."))
    if not has:
        return out

    agents, bad = 0, []
    for ap in sorted((rr / "agents").glob("*")) if (rr / "agents").is_dir() else []:
        aj = ap / "agent.json"
        if not aj.exists():
            continue
        try:
            json.loads(aj.read_text(encoding="utf-8-sig"))
            agents += 1
        except Exception as e:  # noqa
            swallowed(log, 'realm_check: failed; falling back')
            bad.append(f"{ap.name}: {type(e).__name__}")
    out.append(_check("agents", "Agents", not bad and agents > 0,
                      f"{agents} readable" + (f"; unreadable: {', '.join(bad)}" if bad else ""),
                      BLOCK if bad else WARN,
                      fix="Restore the realm from a good export." if bad else "Appoint an agent."))

    jobs, badj = 0, []
    for ap in sorted((rr / "agents").glob("*")):
        jd = ap / "jobs"
        for f in sorted(jd.glob("*.json")) if jd.is_dir() else []:
            try:
                json.loads(f.read_text(encoding="utf-8-sig"))
                jobs += 1
            except Exception as e:  # noqa
                swallowed(log, 'realm_check: failed; falling back')
                badj.append(f"{ap.name}/{f.name}: {type(e).__name__}")
    out.append(_check("jobs", "Jobs", not badj, f"{jobs} readable"
                      + (f"; unreadable: {', '.join(badj[:4])}" if badj else ""),
                      BLOCK, fix="Fix or remove the unreadable job files."))
    return out


# --------------------------------------------------------------------------- adopted realms (5.8c)

_REVIEW_KEY = "adopt_review"


def job_inventory(realm_root) -> dict:
    """What this realm would run: every command job verbatim, and how many agent jobs."""
    cmd, n_agent = [], 0
    adir = Path(realm_root) / "agents"
    for jf in sorted(adir.glob("*/jobs/*.json")) if adir.is_dir() else []:
        try:
            j = json.loads(jf.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            log.debug("job_inventory: unreadable %s", jf, exc_info=True)
            continue
        if not isinstance(j, dict):
            continue
        kind = j.get("kind") or ("command" if (j.get("run") or j.get("command")) else "agent")
        if kind == "command":
            cmd.append({"agent": jf.parent.parent.name, "job": j.get("id") or jf.stem,
                        "name": str(j.get("name") or jf.stem)[:120],
                        "run": str(j.get("run") or j.get("command") or "")[:2000]})
        else:
            n_agent += 1
    return {"command_jobs": cmd, "agent_jobs": n_agent}


def adopt_review(realm_root) -> dict:
    """The pending review for an adopted realm, or {} if there isn't one."""
    try:
        cfg = json.loads((Path(realm_root) / "realm.json").read_text(encoding="utf-8-sig"))
        rv = cfg.get(_REVIEW_KEY)
        return rv if isinstance(rv, dict) else {}
    except (OSError, ValueError):
        log.debug("adopt_review: unreadable realm.json", exc_info=True)
        return {}


def begin_adopt_review(realm_root) -> dict:
    """On adopt: if the realm would run anything, record what, which holds its scheduler."""
    from . import clock, util
    inv = job_inventory(realm_root)
    if not inv["command_jobs"] and not inv["agent_jobs"]:
        return inv
    p = Path(realm_root) / "realm.json"
    with util.file_lock(p):
        cfg = json.loads(p.read_text(encoding="utf-8-sig")) if p.exists() else {}
        cfg[_REVIEW_KEY] = {"since": clock.now().isoformat(timespec="seconds"), **inv}
        util.write_json_atomic(p, cfg)
    return inv


def release_adopt_review(realm_root) -> dict:
    """The owner has seen it: drop the review and re-run the checks (which may still hold)."""
    from . import util
    p = Path(realm_root) / "realm.json"
    with util.file_lock(p):
        cfg = json.loads(p.read_text(encoding="utf-8-sig")) if p.exists() else {}
        cfg.pop(_REVIEW_KEY, None)
        util.write_json_atomic(p, cfg)
    return apply_hold(realm_root)


def adopt_review_check(realm_root) -> dict:
    rv = adopt_review(realm_root)
    if not rv:
        return _check("adopted", "Adopted realm reviewed", True, "")
    n_cmd, n_ag = len(rv.get("command_jobs") or []), int(rv.get("agent_jobs") or 0)
    return _check("adopted", "This realm's jobs need your go-ahead", False,
                  f"Adopted from another folder: {n_cmd} command job{'s' if n_cmd != 1 else ''} and "
                  f"{n_ag} agent job{'s' if n_ag != 1 else ''} are paused until you allow them.",
                  BLOCK, fix="Jobs page → Review and allow.", action="adopt-review")


def run(realm_root, engine: str = "claude") -> dict:
    """Everything that decides whether this realm can work on this machine."""
    checks = realm_check(realm_root)
    checks.append(adopt_review_check(realm_root))
    checks.append(approot_check(realm_root))
    checks.append(engine_check(engine))
    checks.append(workspace_check(realm_root))
    checks.append(telegram_check())
    blocking = [c for c in checks if not c["ok"] and c["severity"] == BLOCK]
    warnings = [c for c in checks if not c["ok"] and c["severity"] == WARN]
    return {"ok": not blocking, "checks": checks,
            "blocking": blocking, "warnings": warnings,
            "summary": _summary(blocking, warnings)}


def _summary(blocking, warnings) -> str:
    if blocking:
        n = len(blocking)
        return (f"{n} thing{'s' if n > 1 else ''} must be fixed before this realm can run: "
                + "; ".join(c["label"] for c in blocking))
    if warnings:
        return "Ready, with " + "; ".join(c["label"].lower() + " degraded" for c in warnings)
    return "Ready."


# --------------------------------------------------------------------------- the hold

_HOLD_KEY = "scheduler_hold"


def hold_reason(realm_root) -> str:
    """Why scheduled jobs are being held, or '' if they aren't."""
    try:
        cfg = json.loads((Path(realm_root) / "realm.json").read_text(encoding="utf-8-sig"))
        return str(cfg.get(_HOLD_KEY) or "").strip()
    except Exception:  # noqa
        swallowed(log, 'hold_reason: failed; returning a fallback')
        return ""


def held(realm_root) -> bool:
    return bool(hold_reason(realm_root))


def set_hold(realm_root, reason: str) -> None:
    """Hold (reason) or release (empty) the realm's scheduled jobs."""
    from . import util
    p = Path(realm_root) / "realm.json"
    with util.file_lock(p):          # realm.json read-modify-write (the 2.9 audit missed this one)
        try:
            cfg = json.loads(p.read_text(encoding="utf-8-sig"))
        except Exception:  # noqa
            swallowed(log, 'set_hold: failed; using a default')
            cfg = {}
        reason = str(reason or "").strip()
        if cfg.get(_HOLD_KEY, "") == reason or (not reason and _HOLD_KEY not in cfg):
            return                   # unchanged — don't rewrite realm.json on every check
        if reason:
            cfg[_HOLD_KEY] = reason
        else:
            cfg.pop(_HOLD_KEY, None)
        util.write_json_atomic(p, cfg)


def apply_hold(realm_root, engine: str = "claude") -> dict:
    """Check the realm and hold or release its scheduler accordingly.

    Releasing matters as much as holding: fix the workspace and the realm must start working again
    without anyone remembering there was a switch.
    """
    res = run(realm_root, engine)
    set_hold(realm_root, "" if res["ok"] else res["summary"])
    res["held"] = not res["ok"]
    return res
