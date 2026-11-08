# `armada/section_snapshots.py`

Bounded background refreshes of owner-configured section snapshots.

### `_destination(root, section)`

—

### `_newest(pattern)`

—

### `_local(path)`

—

### `refresh(root, section, *, force=False, index=None)`

Read the source off the render path; validate current configuration before atomic commit.

### `request(root, index, *, force=False, ticket='')`

Coalesce per-section work; at most two workers and eight admitted refreshes.
