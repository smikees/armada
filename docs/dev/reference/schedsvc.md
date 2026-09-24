# `armada/schedsvc.py`

Is the scheduler running, and starting it if not (launch plan 5.5).

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

### `scheduled_jobs(realm_root)`

How many switched-on jobs in the realm have a schedule (i.e. need the scheduler to fire). A realm with none has nothing to warn about — a bar nagging about a scheduler nothing needs is noise, and noise teaches people to ignore bars.

### `status(realm_root)`

{"running", "pid", "started", "scheduled"} for the realm's scheduler. `scheduled` is the count of jobs that depend on it running.

### `autostart_enabled()`

—

### `_python_for_background()`

pythonw.exe beside the running interpreter on Windows (no console window), else python.

### `start()`

Start `armada schedule` detached from this process, so it outlives the window. Never raises.

### `ensure_running(realm_root)`

What the app window calls on launch: start the scheduler unless one is already running for this realm, or the owner switched autostart off.
