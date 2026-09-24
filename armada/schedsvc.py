"""Is the scheduler running, and starting it if not (launch plan 5.5).

Scheduled jobs run from a separate, windowless process (`armada schedule`), on purpose: a realm's jobs
don't pause because the window is closed. The cost of that design was a failure nobody could see —
after a reboot, or if the process died, nothing ran, and nothing on screen said so. "My jobs
stopped" with no explanation is the worst kind of bug report because it's true and unhelpful.

So: the app window starts the scheduler if it isn't already running for the realm it opens; every
page shows a bar when it isn't running, with a button to start it; and whether it's running is
answered by the same per-realm lock the scheduler already holds (2.9) — a live pid in
`scheduler.lock.json` means a scheduler is ticking that realm. Nothing here can start a second one:
`run_daemon` refuses to start over a realm another live process owns.

Starting at logon (surviving a reboot) is the installer's job (5.2): it's a Windows setting, and
it's the installer that knows where it put things.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from . import appconfig
from .util import swallowed

log = logging.getLogger(__name__)

AUTOSTART_KEY = "scheduler_autostart"          # appconfig; default on
_REPO = Path(__file__).resolve().parents[1]


def scheduled_jobs(realm_root) -> int:
    """How many switched-on jobs in the realm have a schedule (i.e. need the scheduler to fire).
    A realm with none has nothing to warn about — a bar nagging about a scheduler nothing needs is
    noise, and noise teaches people to ignore bars."""
    from . import scheduler
    n = 0
    try:
        for _a, _j, job in scheduler.iter_jobs(Path(realm_root)):
            if job.get("enabled") is False:
                continue
            sched = job.get("cron") or job.get("schedule") or ""
            if isinstance(sched, str) and (scheduler.is_cron(sched) or scheduler.parse_schedule(sched)):
                n += 1
    except OSError:
        swallowed(log, "scheduled_jobs: could not list jobs")
    return n


def status(realm_root) -> dict:
    """{"running", "pid", "started", "scheduled"} for the realm's scheduler. `scheduled` is the
    count of jobs that depend on it running."""
    from . import scheduler
    h = scheduler.lock_holder(realm_root)
    return {"running": bool(h), "pid": (h or {}).get("pid"), "started": (h or {}).get("started"),
            "scheduled": scheduled_jobs(realm_root)}


def autostart_enabled() -> bool:
    return appconfig.get(AUTOSTART_KEY, True) is not False


def _python_for_background() -> str:
    """pythonw.exe beside the running interpreter on Windows (no console window), else python."""
    exe = Path(sys.executable)
    if os.name == "nt":
        w = exe.with_name("pythonw.exe")
        if w.exists():
            return str(w)
    return str(exe)


_last_spawn = 0.0
_SPAWN_GRACE = 20.0   # seconds a just-started scheduler gets to claim its lock before we'd start another


def start() -> dict:
    """Start `armada schedule` detached from this process, so it outlives the window. Never raises.

    A second click (or the window launching while the owner also clicks Start) within a few seconds
    doesn't spawn a second process: a new scheduler takes a moment to claim its lock, and until it
    does the realm still reads as not running. `run_daemon` would refuse the duplicate anyway —
    this just avoids the pointless process."""
    global _last_spawn
    import time
    if time.monotonic() - _last_spawn < _SPAWN_GRACE:
        return {"ok": True, "starting": True}
    cmd =[_python_for_background(), "-m", "armada", "schedule", "--engine", "claude"]
    flags = 0
    if os.name == "nt":
        DETACHED_PROCESS, CREATE_NEW_PROCESS_GROUP, CREATE_NO_WINDOW = 0x8, 0x200, 0x08000000
        flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
    try:
        p = subprocess.Popen(cmd, cwd=str(_REPO), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, close_fds=True, creationflags=flags,
                             start_new_session=(os.name != "nt"))
    except Exception as e:  # noqa — reported to the caller, who shows it
        swallowed(log, "start: could not launch the scheduler")
        return {"ok": False, "error": f"Couldn't start the scheduler: {e}"[:200]}
    _last_spawn = time.monotonic()
    log.info("started the scheduler (pid %s)", p.pid)
    return {"ok": True, "starting": True, "pid": p.pid}


def ensure_running(realm_root) -> dict:
    """What the app window calls on launch: start the scheduler unless one is already running for
    this realm, or the owner switched autostart off."""
    st = status(realm_root)
    if st["running"]:
        return {"ok": True, "already": True, **st}
    if not autostart_enabled():
        return {"ok": True, "skipped": "autostart off", **st}
    return start()
