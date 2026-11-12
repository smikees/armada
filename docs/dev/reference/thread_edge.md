# `armada/thread_edge.py`

Antialiased WebView perimeter on a click-through, per-pixel-alpha window.

Only a three-pixel logical band is cached. The interactive WebView stays live;
preview bytes never leave memory. A failed/stale capture keeps the original clip.

### `perimeter(preview, scale)`

—

### class `Edge`

—

- `Edge.__init__(self, native)` — —
- `Edge.dimensions(self)` — —
- `Edge.current(self)` — —
- `Edge.request(self)` — —
- `Edge.position(self)` — —
- `Edge._clip(self, spread)` — —
- `Edge._capture(self, *_)` — —
- `Edge._apply(self, stream, size)` — —
- `Edge.close(self, *_)` — —
