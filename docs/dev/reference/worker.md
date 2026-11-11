# `armada/worker.py`

Owner-controlled Windows worker boundary for every provider and local tool child.

Only owner code can decrypt the launch password, change the worker policy, or read
the provider key held by the API gateway. The worker receives its own Windows identity,
profile, environment and desktop. Missing/broken setup never downgrades to the owner.

### `_path()`

—

### `state()`

—

### `enabled()`

—

### `require()`

—

### `password(value)`

—

### `home()`

—

### `_within(path, root)`

—

### `_acl(path, sid, rights)`

Grant only a host-selected file/folder; no shell interpolation of paths or SIDs.

### `deletion_guard_paths(value)`

Read-only access check: list only trusted ancestors this worker can replace.

### `_safe_temporary(path)`

—

### `_access(path, value, *, temporary=False)`

—

### `environment(value, supplied=None)`

Allowlist the worker environment. Only explicit invocation credentials cross it.

### `popen(args, **kwargs)`

—

### `run(args, *, input=None, capture_output=False, timeout=None, check=False, **kwargs)`

—

### `read_text(path, *, encoding='utf-8', errors='strict')`

Read a CLI-owned worker file without widening its private credential ACL.

### `clean_temporary(path)`

CLI-private ACLs must be cleaned by the worker which created those files.

### `temporary_directory(**kwargs)`

—

### `temporary_folder(**kwargs)`

An owner-created runtime folder explicitly shared with its worker identity.

### `temp_root()`

Worker CLIs must be able to inspect every parent of runtime input paths.

### `desktop(value)`

Open only the unique Armada station created by the fixed setup task.

### `draft_desktop()`

LPAC scripts use the private station too, with no inherited owner clipboard.

### `status()`

—

### `setup(roots)`

Prepare an owner-only request, then request Windows elevation for account setup.

### `verify()`

Real identity/access probe, using a synthetic DPAPI secret and owned process tree.

### `_verify()`

—
