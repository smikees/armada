# `armada/desktop_recovery.py`

Recover Windows presentation independently of execution and server ownership.

Native UI callbacks own the controller. No recovery action replays a POST or starts
an engine/scheduler. The same Form/HWND remains; failed WebView controls are disposed.

### `recovery_route(value, base)`

—

### `bound_route(route, realm)`

Keep a recovered view bound to its last observed realm; never switch realms.

### `initial_route(value, base)`

Retain the intended display route before the first page heartbeat.

### class `RecoveryBudget`

—

- `RecoveryBudget.__init__(self, *, limit=2, period=120)` — —
- `RecoveryBudget.allow(self, now)` — —

### class `Presentation`

One bounded recovery owner per native Form, including detached windows.

- `Presentation.__init__(self, backend, base_url, quitting)` — —
- `Presentation.post(self, callback)` — —
- `Presentation.start_script(self, script)` — —
- `Presentation.bind(self, backend, args)` — —
- `Presentation.unbind(self)` — —
- `Presentation.remember_draft(self, message)` — Two bounded unsent composer values, in memory only; never arbitrary fields.
- `Presentation.draft_script(self)` — —
- `Presentation.process_failed(self, kind)` — —
- `Presentation.show_panel(self, message, *, retry=False)` — —
- `Presentation.hide_panel(self)` — —
- `Presentation.failed(self, message)` — —
- `Presentation.recover(self, reason, *, manual=False)` — —
- `Presentation.tick(self, *_)` — —
- `Presentation.closed(self, *_)` — —

### `install(base_url, quitting)`

Install once, before any EdgeChrome control is constructed.
