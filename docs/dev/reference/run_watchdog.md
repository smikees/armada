# `armada/run_watchdog.py`

Inactivity supervision for unattended agent turns; time spent queued is excluded.

### class `Watchdog`

—

- `Watchdog.__init__(self, root, agent, thread, settings, stop, *, scheduled=False, clock=time.monotonic)` — —
- `Watchdog.event(self, event)` — —
- `Watchdog.check(self)` — —
- `Watchdog.href(self)` — —
- `Watchdog._watch(self)` — —
- `Watchdog.__enter__(self)` — —
- `Watchdog.__exit__(self, *args)` — —
