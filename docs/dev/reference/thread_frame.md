# `armada/thread_frame.py`

Windows resize and soft shadow for the shaped, detached conversation window.

The shadow is a non-activating, click-through, per-pixel-alpha owned window.
Its centre is transparent, so it can follow the owner's z-order without tinting
the conversation. All native resources and event handlers belong to that window.

### `_api()`

—

### `begin_resize(window)`

Enter Windows' bottom-right sizing loop, including capture and minimum size.

### `attach(window)`

Install once, on the form's UI thread; a decorative failure never breaks chat.

### class `_Shadow`

—

- `_Shadow.__init__(self, native)` — —
- `_Shadow._path(self, width, height, scale, spread=0, offset=0)` — —
- `_Shadow._draw(self, width, height, scale)` — —
- `_Shadow.refresh(self)` — —
- `_Shadow._upload(self, bitmap, left, top)` — —
- `_Shadow.close(self, *_)` — —
