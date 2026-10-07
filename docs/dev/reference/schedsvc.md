# `armada/schedsvc.py`

Scheduler lifecycle for the Armada desktop app.

The GUI starts the windowless scheduler so jobs run while Armada is visible or in the tray.
The child carries its GUI owner's PID and stops when that owner exits. A cooperative stop
marker lets a normal quit release leases before process exit. Older unowned schedulers are
retired on full quit. CLI users can still explicitly run ``armada schedule``.

### `scheduled_jobs(realm_root)`

How many switched-on jobs in the realm have a schedule (i.e. need the scheduler to fire). A realm with none has nothing to warn about — a bar nagging about a scheduler nothing needs is noise, and noise teaches people to ignore bars.

### `status(realm_root)`

{"running", "pid", "started", "scheduled"} for the realm's scheduler. `scheduled` is the count of jobs that depend on it running.

### `autostart_enabled()`

—

### `_python_for_background()`

pythonw.exe beside the running interpreter on Windows (no console window), else python.

### `_stop_marker(pid: int)`

—

### `start()`

Start `armada schedule` with this app process as its lifetime owner. Never raises.

### `_start_locked()`

—

### `stop_for_app_exit()`

Stop all schedulers attached to this app, including pre-tray legacy daemons.

### `ensure_running(realm_root)`

What the app window calls on launch: start the scheduler unless one is already running for this realm, or the owner switched autostart off.

### `eligible_realms(initial='')`

Ready, unarchived realms, independent of which realm the window displays.

### `ready()`

Update health requires a real scheduler lease in every eligible realm.

### class `Supervisor`

Bounded, window-independent recovery; lease acquisition proves readiness, not Popen.

- `Supervisor.__init__(self, initial='')` — —
- `Supervisor.snapshot(self, root)` — —
- `Supervisor.retry(self)` — —
- `Supervisor.step(self)` — —
- `Supervisor.failure_reason(root)` — —
- `Supervisor.run(self)` — —

### `watch(initial='')`

One background supervisor for the desktop lifetime, including time spent in the tray.

### `retry_start()`

—
