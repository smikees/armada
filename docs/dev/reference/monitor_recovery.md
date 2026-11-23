# `armada/monitor_recovery.py`

Keep native windows reachable after display topology changes, in physical pixels.

### `ensure(window)`

—

### `reachable(bounds, areas)`

—

### `fit(bounds, area, offset=0)`

—

### `fit_size(size, area)`

Keep a saved size, or scale it to 80% of the working area without distortion.

### `recover_native(native, *, here=False, offset=0)`

—

### class `MonitorRecovery`

—

- `MonitorRecovery.__init__(self, windows)` — —
- `MonitorRecovery.start(self, main)` — —
- `MonitorRecovery.tick(self, *_)` — —
- `MonitorRecovery.bring_here(self)` — —
- `MonitorRecovery.stop(self)` — —
