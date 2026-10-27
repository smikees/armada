# `armada/view_cache.py`

Bounded, disposable presentation caches. Never used for authorization or execution.

### `file_stamp(path)`

—

### `history_stamp(thread, *, progress=False)`

Observe appends, replacements and interrupted transactions across processes.

### class `ViewCache`

—

- `ViewCache.__init__(self, limit=128, bytes_limit=8 * 1024 * 1024)` — —
- `ViewCache.read(self, key, stamp, build)` — —
