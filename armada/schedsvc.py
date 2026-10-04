"""Scheduler lifecycle for the Armada desktop app.

The GUI starts the windowless scheduler so jobs run while Armada is visible or in the tray.
The child carries its GUI owner's PID and stops when that owner exits. A cooperative stop
marker lets a normal quit release leases before process exit. Older unowned schedulers are
retired on full quit. CLI users can still explicitly run ``armada schedule``.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from . import appconfig, util
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
        if exe.name.lower() == "armada.exe":
            return str(exe)  # the branded host is windowless and can run the scheduler too
        w = exe.with_name("pythonw.exe")
        if w.exists():
            return str(w)
    return str(exe)


_last_spawn = 0.0
_SPAWN_GRACE = 20.0   # seconds a just-started scheduler gets to claim its lock before we'd start another


def _stop_marker(pid: int) -> Path:
    return util.data_dir() / f"scheduler-stop-{pid}"


def start() -> dict:
    """Start `armada schedule` with this app process as its lifetime owner. Never raises.

    A second click (or the window launching while the owner also clicks Start) within a few seconds
    doesn't spawn a second process: a new scheduler takes a moment to claim its lock, and until it
    does the realm still reads as not running. `run_daemon` would refuse the duplicate anyway —
    this just avoids the pointless process."""
    global _last_spawn
    import time
    if time.monotonic() - _last_spawn < _SPAWN_GRACE:
        return {"ok": True, "starting": True}
    _stop_marker(os.getpid()).unlink(missing_ok=True)
    from .updater import launch_arguments
    cmd = [_python_for_background(), *launch_arguments("schedule", "--engine", "auto",
                                                       "--app-owner", str(os.getpid()))]
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


def stop_for_app_exit() -> None:
    """Stop all schedulers attached to this app, including pre-tray legacy daemons."""
    import time
    from . import activerealm, scheduler
    marker = _stop_marker(os.getpid())
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("stop", encoding="ascii")
    holders = {}
    for root in activerealm.every():
        holder = scheduler.lock_holder(root)
        if holder and holder.get("pid") != os.getpid():
            holders[holder["pid"]] = root
    if not holders:
        return
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if all(not scheduler.lock_holder(root) for root in holders.values()):
            return
        time.sleep(0.2)
    # A scheduler from an older Armada version cannot read the new stop marker.
    # The owner chose a full quit, so it must not continue firing jobs in the background.
    for pid, root in holders.items():
        if not scheduler.lock_holder(root) or not util.pid_alive(pid):
            continue
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                               capture_output=True, timeout=5, check=False, creationflags=0x08000000)
            else:
                import signal
                os.kill(pid, signal.SIGTERM)
        except (OSError, subprocess.SubprocessError):
            swallowed(log, "stop_for_app_exit: could not stop old scheduler")


def ensure_running(realm_root) -> dict:
    """What the app window calls on launch: start the scheduler unless one is already running for
    this realm, or the owner switched autostart off."""
    from . import setupflow
    if setupflow.needs_setup(realm_root):
        return {"ok": True, "skipped": "setup in progress"}
    st = status(realm_root)
    if st["running"]:
        return {"ok": True, "already": True, **st}
    if not autostart_enabled():
        return {"ok": True, "skipped": "autostart off", **st}
    return start()
