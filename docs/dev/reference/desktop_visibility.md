# `armada/desktop_visibility.py`

Nonblocking close-to-tray/restore transitions, with the newest request winning.

WinForms close callbacks run on its UI thread. Tray callbacks run on a different
STA thread. Neither may wait for the other's message loop or a WebView2 result.

### class `DesktopVisibility`

—

- `DesktopVisibility.__init__(self, window, save_state, *, post=None, apply=None, save_timeout=0.4)` — —
- `DesktopVisibility.show(self)` — —
- `DesktopVisibility.hide(self, *, save=True)` — —
- `DesktopVisibility.hide_if_minimized(self)` — —
- `DesktopVisibility.stop(self)` — —
- `DesktopVisibility._request(self, visible, save)` — —
- `DesktopVisibility._save_then_hide(self, generation)` — —
- `DesktopVisibility._queue(self, visible, generation)` — —
- `DesktopVisibility._native_post(self, callback)` — —
- `DesktopVisibility._native_apply(self, visible)` — —
