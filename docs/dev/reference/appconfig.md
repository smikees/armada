# `armada/appconfig.py`

App-level (per-machine) configuration — distinct from a realm's own files.

Stored at ~/.armada/config.json, this holds preferences that belong to the ARMADA install
rather than to any single realm (e.g. the chosen visual theme). Kept tiny and best-effort:
a missing or corrupt file renders with empty defaults. Mutations require a readable object
and never overwrite an unreadable or damaged file.

### `_path()`

—

### `_read()`

—

### `load()`

—

### `get(key: str, default=None)`

—

### `save(updates: dict)`

Merge `updates` into the existing config and write atomically.
