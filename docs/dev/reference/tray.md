# `armada/tray.py`

Windows notification-area icon for a hidden Armada window.

Uses the WinForms runtime already shipped with pywebview; no second tray package or
background helper process is needed. The WinForms message loop lives on its own STA thread.

### class `Tray`

—

- `Tray.__init__(self, show, quit_app)` — —
- `Tray.start(self)` — —
- `Tray.stop(self)` — —
