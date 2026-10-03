# `armada/startup_splash.py`

Loading artwork inside the main window, including while WebView2 starts.

### `_dark()`

—

### class `LoadingPanel`

A child control, never a second top-level window or helper process.

- `LoadingPanel.__init__(self, window)` — —
- `LoadingPanel.mount(self)` — —
- `LoadingPanel.paint(self, sender, event)` — —
- `LoadingPanel.tick(self, sender, event)` — —
- `LoadingPanel.closed(self, sender, event)` — —
- `LoadingPanel.ready(self)` — Reveal the painted dashboard in the same window, on its UI thread.
- `LoadingPanel.dispose(self)` — —
