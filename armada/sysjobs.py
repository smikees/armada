"""System jobs — the recurring work ARMADA does to keep itself current.

Some of what the app needs doing is on a clock rather than on demand: asking Anthropic which models
exist so new ones appear and retired ones are marked, checking whether capabilities have updates,
trimming history so it can't grow forever. Until now these were scattered — the model refresh ran on
a background thread at every server start (so fifteen times during a busy session, and never if the
app stayed shut), and the update scan only happened if someone pressed a button.

Shape, mirroring system skills: the DEFINITION ships in this package, so it can't be edited or
deleted and it improves when ARMADA updates. Only the STATE — last run, outcome, whether you've
switched it off — lives in the realm.

Two things are deliberate.

**Cost is declared, not implied.** A job is either `free` (deterministic local work) or `quota` (it
invokes agents and spends the selected provider’s quota). The UI shows which, because "system job" must
never quietly become "thing that spends money".

**Silence is the enemy.** Background work that fails invisibly is the failure mode that bit this
app twice in one day. Every run records its outcome, and failures land in the notification feed.
"""
from __future__ import annotations
import os
import datetime as _dt
import json
import time
import uuid
from pathlib import Path

from . import clock as _clock
from . import util
import logging
from .util import swallowed
log = logging.getLogger(__name__)

_STATE = "system_jobs.json"

FREE = "free"          # deterministic, local, costs nothing
QUOTA = "quota"        # invokes agents — spends the selected provider’s quota

# Consecutive execution failures before a job interrupts the owner. These jobs run on a
# schedule, so one miss is invisible and usually self-healing — a token mid-rotation, a flaky
# minute of network. The original note here said "silence is the enemy", and it is; but a bell that
# rings for things that fix themselves is silence by another route, because you stop reading it.
_NOTIFY_AFTER_FAILS = 3


# ---- the jobs themselves ---------------------------------------------------------------------

# Why a catalogue refresh came back empty, in the owner's terms. Only the last of these is a fault
# on Anthropic's side; the rest are ARMADA choosing not to ask, or waiting for something that fixes
# itself. `False` means "not a failure" — the cached catalogue is intact and nothing is broken.
_MODEL_SYNC_REASONS = {
    "off":                 (False, "model sync is switched off on this machine"),
    "signed-out":          (False, "waiting for a Claude sign-in"),
    "token-expired":       (False, "sign-in is refreshing — will retry"),
    "empty-response":      (True,  "Anthropic returned an empty model list"),
    "unexpected-response": (True,  "Anthropic's model list was in an unexpected shape"),
}


def _job_model_catalog(realm_root) -> dict:
    from . import models
    r = models.refresh(realm_root) or {}
    if not r.get("ok", True):
        why = str(r.get("reason") or "unavailable")
        bad, text = _MODEL_SYNC_REASONS.get(why, (True, ""))
        if not text:
            text = (f"Anthropic's model list wasn't reachable ({why})" if why.startswith("unreach")
                    else f"Anthropic's model list refused the request ({why})"
                    if why.startswith("http-") else f"couldn't refresh: {why}")
        return {"ok": False, "status": "error" if bad else "skipped", "reason": why, "detail": text}
    added, retired = r.get("added") or [], r.get("retired") or []
    bits = []
    if added:
        bits.append(f"{len(added)} new ({', '.join(added[:3])})")
    if retired:
        bits.append(f"{len(retired)} retired")
    return {"ok": True, "detail": " · ".join(bits) or "no changes"}


def _job_capability_updates(realm_root) -> dict:
    from . import capscan, notify
    r = capscan.scan(realm_root) or {}
    if not r.get("ok"):
        return {"ok": False, "detail": str(r.get("error") or "scan failed")[:160]}
    n = int(r.get("updates") or 0)
    if n:
        notify.emit(realm_root, "update_available",
                    f"{n} capability update{'s' if n != 1 else ''} available",
                    "Review and apply them on the Capabilities page.", "/skills")
    return {"ok": True, "detail": f"{n} update(s) available" if n else "everything up to date"}


def _job_inbox_dispatch(realm_root) -> dict:
    """Deliver agent-to-agent tasks. Declared QUOTA because it *can* invoke agents — but only where
    a message is actually waiting; an empty pass is a handful of directory listings and costs
    nothing."""
    from . import runner
    r = runner.dispatch_inboxes(realm_root) or {}
    if r.get("skipped") == "disabled":
        return {"ok": False, "status": "skipped", "reason": "disabled",
                "detail": "agent-to-agent tasks are off for this realm"}
    n, bad = int(r.get("handled") or 0), int(r.get("failed") or 0)
    blocked = r.get("blocked") or []
    detail = f"{n} task(s) handled" + (f", {bad} failed" if bad else "")
    if blocked:
        detail += "; " + "; ".join(f"{b['agent']}: {b['detail']}" for b in blocked)
    if bad or any(b.get("status") == "error" for b in blocked):
        return {"ok": False, "reason": "task-failed" if bad else "auth-unavailable", "detail": detail}
    if blocked:
        return {"ok": False, "status": "skipped", "reason": "signed-out", "detail": detail}
    return {"ok": True, "detail": detail if n else "no tasks due"}


def _job_telegram_inbox(realm_root) -> dict:
    """Answer prompts sent from Telegram. QUOTA because a message becomes an agent run — but the
    check itself is one HTTPS call and costs nothing, so an idle pass is free."""
    from . import telegram as _tg
    if not _tg.ready():
        return {"ok": False, "status": "skipped", "reason": "not-connected", "detail": "Telegram isn't connected"}
    if _tg.listener_alive(realm_root):
        # The scheduler is holding a long poll open and answering within a second or two. Polling
        # from here as well would race it for the same cursor — Telegram hands each update to
        # whoever asks first, so the two would take turns dropping messages.
        return {"ok": False, "status": "skipped", "reason": "listener-active", "detail": "listener is handling messages"}
    r = _tg.dispatch(realm_root) or {}
    if r.get("handled"):
        try:
            _tg.register_commands(realm_root)      # keep /agent autocomplete in step with the realm
        except Exception:  # noqa
            swallowed(log, '_job_telegram_inbox: failed; ignored')
    return r


def _job_usage_keepalive(realm_root) -> dict:
    """Keep Claude Code's sign-in fresh, so the usage bars don't go dark between agent runs.

    ARMADA reads the Claude usage figures using the OAuth token Claude Code stores locally. That
    token lives ~12-18 hours and ARMADA never refreshes it itself — holding another app's refresh
    token is how you break its sign-in (see usage_api). So instead we ask Claude Code to do the
    smallest possible piece of work, and it renews its own token as a side effect.

    Measured on 2026-09-18: a 5-second call moved expiry from 04:34 to 22:20 — nearly 18 hours from
    a handful of tokens. At this cadence that is three calls a day, which is why it is listed as a
    quota job rather than a free one: it is not free, it is just very cheap, and the owner can
    switch it off.
    """
    import json as _json
    from .engine.process import supervise_command
    import time as _time
    from .engine.claude import ClaudeEngine
    creds = Path.home() / ".claude" / ".credentials.json"

    def _expiry() -> int:
        try:
            return int(_json.loads(creds.read_text("utf-8"))["claudeAiOauth"]["expiresAt"])
        except Exception:  # noqa
            log.debug('_expiry: failed; returning a fallback', exc_info=True)
            return 0

    before = _expiry()
    if before and before > int(_time.time() * 1000) + 6 * 3600_000:
        return {"ok": True, "detail": "sign-in still fresh — nothing to do"}
    try:
        launcher = ClaudeEngine()._launcher()
    except Exception as e:  # noqa
        swallowed(log, '_job_usage_keepalive: failed; error returned to the caller')
        return {"ok": False, "detail": f"couldn't resolve the Claude Code launcher: {e}"}
    if not launcher:
        return {"ok": False, "detail": "Claude Code isn't on PATH"}
    try:
        r = supervise_command(launcher + ["-p", "Reply with exactly: ok", "--max-turns", "1",
                                             "--output-format", "json"], timeout=35)
    except Exception as e:  # noqa
        swallowed(log, '_job_usage_keepalive: failed; error returned to the caller')
        return {"ok": False, "detail": f"keepalive call failed: {str(e)[:100]}"}
    _record_keepalive(realm_root, r.stdout, r.returncode == 0 and not r.error)
    if r.returncode != 0 or r.error:
        return {"ok": False, "detail": (r.error or r.stderr or "non-zero exit").strip()[:140]}
    after = _expiry()
    if after > before:
        hrs = (after - before) / 3600_000
        # Now that the token is good, take a real usage reading and bank it for the header.
        try:
            from . import usage_api
            usage_api.fetch(realm_root, force=True)
        except Exception:  # noqa
            swallowed(log, '_job_usage_keepalive: failed; ignored')
        return {"ok": True, "detail": f"sign-in renewed (+{hrs:.0f}h)"}
    return {"ok": True, "detail": "call succeeded but the token didn't move — already fresh"}


def _record_keepalive(realm_root, stdout: str, ok: bool) -> None:
    """Count the keep-alive's few tokens as System usage (sysusage), from the CLI's JSON result."""
    try:
        from . import sysusage
        from .engine.claude import _usage_from_event, _concrete_model
        ev = json.loads((stdout or "").strip() or "{}")
        if not isinstance(ev, dict):
            return
        u = _usage_from_event(ev)
        model = _concrete_model(ev.get("model"), ev.get("modelUsage"))
        sysusage.record(realm_root, "system:usage-keepalive", model, u.as_dict(), ok)
    except Exception:  # noqa — accounting never fails the job
        swallowed(log, '_record_keepalive: failed; ignored')


def _job_prune_history(realm_root) -> dict:
    from . import notify
    removed = notify.prune(realm_root)
    return {"ok": True, "detail": f"{removed} old notification(s) pruned" if removed else "nothing to prune"}


def _job_environment_context(realm_root) -> dict:
    """Re-probe the machine and rebuild the system memory ("Environment, realm and owner context").

    Nothing the user wrote is at risk here. The system memory is generated from sources — the
    machine probe, realm.json (including the owner facts you set in User settings), the agent
    files and the goals module — so a refresh can only restate those. Facts we can't re-probe
    (GPU) are carried forward from the previous digest rather than dropped, anything the user
    wrote lives in their own realm memories, which this never touches, and the previous version
    is snapshotted before a rewrite."""
    from . import memory
    r = memory.refresh_system_memory(realm_root, trigger="weekly") or {}
    if not r.get("changed"):
        return {"ok": True, "detail": "no change — machine and realm look the same"}
    return {"ok": True, "detail": "environment context updated"}


def _job_catalogue_refresh(realm_root) -> dict:
    """Re-read what could be added: the plugin marketplaces on this machine and Anthropic's public
    skills repository.

    Metadata only, and deliberately so. This job never installs, updates or changes a capability
    you already have — it refreshes the list you browse when you go looking for a new one. The MCP
    registry isn't pulled here at all: it holds tens of thousands of self-published servers and is
    searched live instead of mirrored.

    Machine-level, not per realm, so running it in one realm freshens the catalogue for all of
    them. It costs nothing but a git-clone read and one HTTPS call.
    """
    from . import catalogue
    r = catalogue.refresh()
    # Counting the registry means paging it (~130 requests) — the API caps its page size, has no
    # stats endpoint and reports no total. That is exactly the kind of work a daily job exists
    # for, and exactly what a page load must never do; the answer is remembered on the index and
    # shown beside the source until tomorrow.
    cnt = catalogue.refresh_registry_count()
    bad = [s for s, m in (r.get("sources") or {}).items() if not m.get("ok")]
    if not cnt.get("ok"):
        bad.append("mcp-registry")
    if bad:
        # Each source keeps its last good data, so this is "out of date", not "broken".
        return {"ok": False, "detail": f"{r.get('total', 0)} listed · couldn't reach: " + ", ".join(sorted(set(bad)))}
    # Now that the list is current, give the realm's discovered capabilities their real names.
    # A connector Claude set up arrives as `claude_ai_Interactive_Brokers_IBKR` with no publisher;
    # the catalogue knows it as Interactive Brokers (IBKR), from the MCP registry. Matching them
    # up needs a fresh catalogue, which is exactly what just happened, so it belongs here.
    took = catalogue.adopt(realm_root)
    named = len(took.get("changed") or [])
    n = cnt.get("count", 0)
    tail = f" · named {named} capabilit{'y' if named == 1 else 'ies'}" if named else ""
    return {"ok": True,
            "detail": f"{r.get('total', 0)} listed · registry holds {n:,} servers{tail}"}


def _job_app_update(realm_root) -> dict:
    """Keep ARMADA itself up to date (5.4). Machine-wide, though it's listed in every realm: the
    updater keeps its own clock, so a second realm's pass inside the same 12 hours just reports the
    last answer instead of asking GitHub again."""
    from . import updater, notify
    if not updater.installed():
        return {"ok": True, "detail": "development copy — updates come from git"}
    if updater.check_due():
        r = updater.check(download=True)
    else:
        st = updater.state()
        r = {"ok": st.get("status") not in ("error", "rejected"), "detail": st.get("detail") or
             {"current": f"up to date (v{updater.__version__})", "staged": f"v{st.get('latest')} is ready to install",
              "needs-installer": f"v{st.get('latest')} needs the new installer"}.get(st.get("status"), "checked recently")}
    v = updater.staged_version()
    if v and updater.state().get("notified") != v:
        updater._save(notified=v)
        notify.emit(realm_root, "update_available", f"ARMADA v{v} is ready",
                    "It was downloaded and checked, and installs the next time ARMADA restarts "
                    "— or now, from the bar at the top of the window.", "/settings")
    return {"ok": bool(r.get("ok", True)), "detail": str(r.get("detail") or "")[:200]}


# Definitions live here, in the package — not in the realm — so they can't be edited away.
JOBS = [
    {"id": "model-catalog", "name": "Refresh the model catalogue",
     "description": "Ask Anthropic which models exist, so new ones show up and retired ones are "
                    "marked instead of silently disappearing.",
     "every_hours": 24, "cost": FREE, "run": _job_model_catalog},
    {"id": "capability-updates", "name": "Check capabilities for updates",
     "description": "Compare installed capability versions against what's available, and tell you "
                    "in the bell when something can be updated.",
     "every_hours": 24, "cost": FREE, "run": _job_capability_updates},
    {"id": "inbox-dispatch", "name": "Deliver agent-to-agent tasks",
     "description": "Check each agent's inbox and let them act on what teammates have asked for. "
                    "Checking is free — an agent is only woken when a task is actually waiting, "
                    "and then only as often as its own inbox cadence allows.",
     "every_minutes": 1, "cost": QUOTA, "run": _job_inbox_dispatch},
    {"id": "telegram-inbox", "name": "Answer Telegram messages",
     "description": "Check the linked Telegram chat and let agents answer what you've asked from "
                    "your phone. Checking is free — an agent only runs when there's a message "
                    "waiting, and only from the one chat you linked.",
     "every_minutes": 1, "cost": QUOTA, "run": _job_telegram_inbox},
    {"id": "usage-keepalive", "name": "Keep the usage figures live",
     "description": "Claude's usage bars are read with the sign-in Claude Code keeps on this "
                    "machine, and that sign-in lapses after about half a day. This asks Claude for "
                    "one word every few hours so it renews itself, which keeps the bars up to date "
                    "whether or not you've run an agent. It costs a few tokens a day; turn it off "
                    "and the figures still show, just labelled with how old they are.",
     "every_hours": 8, "cost": QUOTA, "provider": "claude", "run": _job_usage_keepalive},
    {"id": "prune-history", "name": "Prune old history",
     "description": "Drop notifications older than a week — they're stale long before that — so "
                    "the feed stays useful and bounded.",
     "every_hours": 24, "cost": FREE, "run": _job_prune_history},
    {"id": "environment-context", "name": "Refresh environment context",
     "description": "Re-check the machine specs and OS version and rebuild the "
                    "“Environment, realm and owner context” memory every agent reads. It is "
                    "generated from your settings, agents and goals, so it never overrides what you "
                    "wrote — your own memories and owner details are left exactly as they are.",
     "every_hours": 168, "cost": FREE, "run": _job_environment_context},
    {"id": "catalogue-refresh", "name": "Refresh the capability catalogue",
     "description": "Re-read the Claude plugin marketplaces set up on this computer and "
                    "Anthropic\u2019s public skills repository, so the Catalogue shows what is "
                    "actually on offer. Metadata only \u2014 it never installs anything or touches "
                    "a capability you already have. The MCP registry is searched live rather than "
                    "copied here, so it is always current.",
     "every_hours": 24, "cost": FREE, "run": _job_catalogue_refresh},
    {"id": "app-update", "name": "Keep ARMADA up to date",
     "description": "Check for a new version of ARMADA twice a day. A new version is downloaded, "
                    "checked against ARMADA's release signature, and put in place the next time "
                    "ARMADA restarts — or straight away when the window is closed and nothing is "
                    "running. Your realms and settings are never touched. This switch is for the "
                    "whole computer, not just this realm (the same one as Settings → App → Advanced).",
     "every_hours": 12, "cost": FREE, "run": _job_app_update, "machine": "auto_update"},
]
_BY_ID = {j["id"]: j for j in JOBS}


# ---- state (in the realm) --------------------------------------------------------------------

def _state_path(realm_root) -> Path:
    return Path(realm_root) / _STATE


def state(realm_root) -> dict:
    try:
        d = util.read_json_state(_state_path(realm_root), default=dict)
        _validate_state(d)
        return d
    except Exception:  # noqa — missing/corrupt state just means "never run"
        log.debug('state: failed; returning a fallback', exc_info=True)
        return {}


def _save(realm_root, st: dict) -> None:
    with util.file_lock(_state_path(realm_root)):
        util.write_json_atomic(_state_path(realm_root), st)


def _validate_state(st):
    for key, value in st.items():
        if key == "schema_version":
            continue
        if not isinstance(value, dict):
            raise util.StateError("Invalid system_jobs.json entry; restore valid state before running jobs.")
        if "runs" in value and not isinstance(value["runs"], list):
            raise util.StateError("Invalid system_jobs.json history; restore valid state before running jobs.")
        if "attempt" in value:
            attempt = value["attempt"]
            if (not isinstance(attempt, dict) or attempt.get("state") not in ("claimed", "finished")
                    or not all(isinstance(attempt.get(k), str) and attempt[k] for k in ("attempt_id", "started"))):
                raise util.StateError("Invalid system job attempt; restore valid state before running jobs.")
        if "interrupted_attempts" in value and not isinstance(value["interrupted_attempts"], list):
            raise util.StateError("Invalid interrupted system job attempts.")


def set_enabled(realm_root, jid: str, on: bool) -> dict:
    if jid not in _BY_ID:
        return {"ok": False, "error": "unknown system job"}
    if _BY_ID[jid].get("machine"):           # a per-computer switch, kept in appconfig
        from . import appconfig
        appconfig.save({_BY_ID[jid]["machine"]: bool(on)})
        return {"ok": True, "enabled": bool(on)}
    try:
        util.mutate_json(_state_path(realm_root),
                         lambda st: st.setdefault(jid, {}).update(enabled=bool(on)),
                         default=dict, validate=_validate_state)
    except (OSError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True, "enabled": bool(on)}


def is_enabled(realm_root, jid: str) -> bool:
    from . import realmops
    if realmops.archived(realm_root):
        return False
    j = _BY_ID.get(jid) or {}
    # A retired realm may turn off its copy of a machine-wide upkeep job without
    # switching off that upkeep for every other realm on this computer.
    if state(realm_root).get(jid, {}).get("enabled") is False:
        return False
    if j.get("machine"):
        from . import appconfig
        return appconfig.get(j["machine"], True) is not False
    return bool(state(realm_root).get(jid, {}).get("enabled", True))


# How many runs to keep per job. These jobs are the frequent ones — inbox delivery ticks every few
# minutes — so this is a few days rather than a few months, which is exactly the window the Jobs
# list draws. Bounded on write so the state file can't grow without anyone deciding it should.
_HISTORY_MAX = 80


def _record_run(entry: dict, ts: str, status: str) -> None:
    """Bounded history for the week strip: skips must not paint a false success or failure."""
    runs = entry.get("runs")
    if not isinstance(runs, list):
        runs = []
    runs.append({"ts": ts, "status": status})
    entry["runs"] = runs[-_HISTORY_MAX:]


def _parse(ts: str):
    try:
        return _dt.datetime.fromisoformat(ts)
    except Exception:  # noqa
        log.debug('_parse: failed; returning a fallback', exc_info=True)
        return None


def interval_minutes(j: dict) -> int:
    """A job declares either every_hours or every_minutes — inbox delivery needs to run far more
    often than housekeeping, and checking costs nothing when there's nothing to do."""
    if j.get("every_minutes"):
        return int(j["every_minutes"])
    return int(j.get("every_hours") or 24) * 60


def due(realm_root, jid: str, now=None) -> bool:
    """Interval-based, not cron: these are 'every so often', not 'at 07:00'."""
    j = _BY_ID.get(jid)
    if not j or not is_enabled(realm_root, jid):
        return False
    entry = state(realm_root).get(jid, {})
    return entry.get("attempt", {}).get("state") != "claimed" and _entry_due(j, entry, now or _clock.now())


def _entry_due(job, entry, now):
    last = _parse(str(entry.get("last_run") or ""))
    if last is None:
        return True
    if last.tzinfo is None:
        last = last.astimezone()
    return (now - last).total_seconds() >= interval_minutes(job) * 60


def status(realm_root) -> list:
    """Everything the System tab needs: definition + live state, newest-relevant first."""
    st = state(realm_root)
    out = []
    for j in JOBS:
        s = st.get(j["id"], {})
        last = _parse(str(s.get("last_run") or ""))
        mins = interval_minutes(j)
        uncertain = s.get("attempt", {}).get("state") == "claimed"
        nxt = None
        if last is not None and not uncertain:
            nxt = (last + _dt.timedelta(minutes=mins)).isoformat(timespec="seconds")
        out.append({
            "id": j["id"], "name": j["name"], "description": j["description"],
            "cost": j["cost"], "every_minutes": mins,
            "enabled": bool(s.get("enabled", True)),
            "last_run": s.get("last_run") or "", "status": "held" if uncertain else s.get("status") or "",
            "detail": "Attempt in progress or interrupted; inspect before retrying." if uncertain else s.get("detail") or "", "next_due": nxt or "",
            "due_now": due(realm_root, j["id"]), "reason": s.get("reason") or "",
            # What the Jobs list draws its week strip from. A job that ran before this build has
            # no history and shows an empty week rather than a guessed one.
            "runs": [r for r in (s.get("runs") or []) if isinstance(r, dict)],
        })
    return out


# ---- running -----------------------------------------------------------------------------------

def _outcome(jid, status, reason, detail):
    return {"id": jid, "ok": status == "ok", "status": status,
            "reason": reason, "detail": detail, "skipped": status in ("skipped", "held"),
            "error": detail if status == "error" else ""}


def _normalize(jid, result):
    if not isinstance(result, dict) or not isinstance(result.get("ok"), bool):
        return _outcome(jid, "error", "invalid-result", "Job returned no valid outcome.")
    status = result.get("status") or ("skipped" if result.get("skipped") else
                                     "ok" if result["ok"] else "error")
    if status not in ("ok", "skipped", "error") or result["ok"] != (status == "ok"):
        return _outcome(jid, "error", "invalid-result", "Job returned a contradictory outcome.")
    return _outcome(jid, status, str(result.get("reason") or
                    {"ok": "completed", "skipped": "unavailable", "error": "job-failed"}[status]),
                    str(result.get("detail") or result.get("error") or
                        {"ok": "Completed.", "skipped": "No work performed.", "error": "Job failed."}[status]))


def run_one(realm_root, jid: str, manual: bool = False, urgent: bool = False) -> dict:
    """Exclusively claim a due system job; manual=True explicitly permits an operator retry.

    The per-job OS lock covers execution. The durable claim survives process death, so a
    scheduled caller cannot replay an uncertain attempt after the OS releases that lock.
    """
    if jid not in _BY_ID:
        return _outcome(jid, "error", "unknown-job", "unknown system job")
    try:
        util.assert_realm_writable(_state_path(realm_root))
        with util.file_lock(Path(realm_root) / ".scheduler" / "system" / f"{jid}.json", timeout=.05):
            return _run_locked(realm_root, jid, manual, urgent)
    except util.FileLockTimeout:
        return _outcome(jid, "skipped", "already-running", "This system job is already running.")
    except Exception as exc:
        swallowed(log, 'run_one: could not admit system job')
        return _outcome(jid, "error", "state-error", str(exc))


def _run_locked(realm_root, jid, manual, urgent=False):
    j = _BY_ID[jid]
    _validate_state(util.read_json_state(_state_path(realm_root), default=dict))
    # Off means off, including from Run now. It used to mean "off on a schedule, but still runnable
    # by hand", which put a live Run button next to a switch saying the job does not run — two
    # controls contradicting each other, with no way to tell which one governed tonight. Switching
    # it back on is one click, and then the button does what it says.
    if not is_enabled(realm_root, jid):
        return _outcome(jid, "skipped", "disabled", "This job is switched off. Switch it on to run it.")
    # Re-read enabled/cadence and reserve the attempt under the state lock. UI changes during
    # execution still merge at completion; no state lock is held while external work runs.
    attempt = {"attempt_id": uuid.uuid4().hex, "state": "claimed", "owner_pid": os.getpid(),
               "started": _clock.now().isoformat(timespec="seconds")}
    from . import realmops, updater
    with updater.admission_lock(), realmops.lifecycle_lock(realm_root), util.file_lock(_state_path(realm_root)):
        if updater.installed() and updater.admission_paused():
            return _outcome(jid, 'skipped', 'update-pending', 'ARMADA is restarting to update.')
        realmops.assert_active(realm_root)
        st = util.read_json_state(_state_path(realm_root), default=dict)
        _validate_state(st)
        entry = st.setdefault(jid, {})
        if (not j.get("machine") and entry.get("enabled", True) is False) or not is_enabled(realm_root, jid):
            return _outcome(jid, "skipped", "disabled", "This job is switched off.")
        previous = entry.get("attempt", {})
        if previous.get("state") == "claimed":
            if not manual:
                return _outcome(jid, "held", "uncertain-attempt",
                                "Previous attempt has no recorded outcome; inspect before using Run now.")
            # Keep evidence of the uncertain run when the owner explicitly asks to retry.
            entry["interrupted_attempts"] = [*entry.get("interrupted_attempts", []), previous][-_HISTORY_MAX:]
            attempt["retry_of"] = previous["attempt_id"]
        elif not manual and not (urgent and jid == 'usage-keepalive') and not _entry_due(j, entry, _clock.now()):
            return _outcome(jid, "skipped", "not-due", "This job is not due yet.")
        entry["attempt"] = attempt
        util.write_json_atomic(_state_path(realm_root), st)
    started = time.monotonic()
    try:
        # Only explicitly provider-specific jobs have a fixed admission requirement.
        # Dispatch jobs check their actual recipients, after finding pending work.
        from .engine.authentication import provider_access
        access = provider_access(j["provider"]) if j.get("provider") else {"ok": True}
        res = _normalize(jid, j["run"](realm_root) if access["ok"] else access)
    except Exception as e:  # a failing job is data, not a crash
        swallowed(log, 'run_one: failed; recorded as an error')
        res = _outcome(jid, "error", "job-exception", f"{type(e).__name__}: {e}"[:200])
    outcome, detail = res["status"], res["detail"]
    # Through the clock seam, like due() which reads it back: a run recorded in real time but
    # compared against a frozen clock made the Jobs golden show "next run: tomorrow" relative to
    # whatever day the suite ran (UI_AUDIT L7). Identical to datetime.now() when not frozen.
    now_iso = _clock.now().isoformat(timespec="seconds")
    def record(st):
        entry = st.setdefault(jid, {})
        current = entry.get("attempt", {})
        if current.get("attempt_id") != attempt["attempt_id"] or current.get("state") != "claimed":
            raise util.StateError("System-job attempt ownership changed; result was not recorded.")
        current.update(state="finished", finished=now_iso, status=outcome, reason=res["reason"])
        fails = (int(entry.get("fails") or 0) + 1 if outcome == "error" else
                 0 if outcome == "ok" else int(entry.get("fails") or 0))
        entry.update({"last_run": now_iso, "status": outcome, "reason": res["reason"],
                      "detail": detail[:300], "fails": fails,
                      "took_ms": int((time.monotonic() - started) * 1000)})
        _record_run(entry, now_iso, outcome)
    try:
        st = util.mutate_json(_state_path(realm_root), record, default=dict, validate=_validate_state)
    except (OSError, ValueError) as exc:
        return _outcome(jid, "error", "record-failed",
                        f"Job ran but its result could not be recorded; automatic retry is held: {exc}")
    fails = st[jid]["fails"]
    # Only shout once it's a pattern. These jobs refresh cached data on a schedule: a single miss
    # changes nothing the owner can see or act on, and the next pass usually fixes it. Notifying on
    # the first one taught the owner to ignore the bell, which costs more than the miss did.
    if outcome == "error" and fails >= _NOTIFY_AFTER_FAILS:
        try:
            from . import notify
            # Same shape as an agent job's failure notification, so both read alike wherever they
            # land — see runner._job_note.
            body = "\n".join(r for r in (
                f"Job: {j['name']}",
                "Agent: ARMADA (system job)",
                f"Why: {detail or 'no reason reported'}",
                f"Failed: {fails} times in a row",
                f"Took: {int((time.monotonic() - started))}s") if r)
            notify.emit(realm_root, "system_job_failed", "Job failed · ARMADA", body, "/jobs")
        except Exception:  # noqa
            swallowed(log, 'run_one: failed; ignored')
    return {**res, "fails": fails}


def run_due(realm_root) -> list:
    """Every enabled job whose interval has elapsed. Called once per scheduler tick."""
    out = []
    for j in JOBS:
        try:
            if due(realm_root, j["id"]):
                out.append(run_one(realm_root, j["id"]))
        except Exception as exc:  # one bad job must not stop the others
            swallowed(log, 'run_due: failed; recorded as an error')
            out.append(_outcome(j["id"], "error", "dispatch-error", str(exc)))
    return out
