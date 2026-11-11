# `armada/worker_files.py`

Private runtime staging with held Windows handles, never path-based ACL grants.

The worker controls its profile and can redirect paths. Create inputs with an
owner-only descriptor, verify the opened object, and hold it against replacement
until inputs are complete and execution grants the worker access.

### `_api()`

—

### `_same_path(left, right)`

—

### class `RuntimeFolder`

Owner-private staging, then worker Modify access through the same held object.

- `RuntimeFolder.__init__(self, value, *, prefix='armada-', suffix='', dir=None)` — —
- `RuntimeFolder._open_guard(self, path, access)` — —
- `RuntimeFolder._verify_private(self, owner_sid)` — —
- `RuntimeFolder.grant(self, sid)` — —
- `RuntimeFolder.release(self)` — —
- `RuntimeFolder.cleanup(self)` — —
