# `armada/inspection.py`

Owner-approved inspector authority and registered, read-only artifact access.

### `identity(root, agent)`

—

### `_set(key, entry, value)`

—

### `approve(root, agent, enabled)`

—

### `enabled(root, agent)`

—

### `command_fingerprint(job)`

—

### `approve_command(root, agent, job)`

—

### `command_approved(root, agent, job)`

—

### `artifacts(root)`

Only recorded output artifacts inside their producer's authorized file roots.

### `checked_path(path, roots, *, must_exist=False)`

Reject escapes and reparse points, including links whose target remains inside a root.
