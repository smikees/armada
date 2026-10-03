# `armada/util.py`

Small shared utilities: filesystem-path safety and atomic writes.

Kept dependency-free (stdlib only) so every module can import it cheaply.

### class `UnsafeSegment`

A request-supplied path segment that would escape or is malformed.


### `safe_seg(value, what: str='segment')`

Return `value` as a str if it's a single safe path segment, else raise.

### `is_safe_seg(value)`

—

### `_replace_retrying(src, dst, attempts: int=12)`

os.replace, patient with Windows' momentary locks.

### `write_text_atomic(path, text: str, encoding: str='utf-8', *, newline=None)`

Write text so a crash/concurrent reader never sees a half-written file.

### `write_json_atomic(path, obj, indent: int=2)`

Serialize `obj` to JSON and write it atomically (see write_text_atomic).

### `sweep_temp_files(root, older_than_sec: float=3600.0)`

Delete stale `.tmp-*` files left by an atomic write that never completed. Returns the count.

### `pid_alive(pid)`

Best-effort: is a process with this pid currently running on this machine?

### class `StateError`

Stored state cannot safely be changed; preserve it for recovery.


### class `UnsupportedSchemaError`

A newer application owns the format; this build must leave it read-only.


### class `FileLockTimeout`

Another writer still owns the lock. The critical section was not entered.


### `read_json_state(path, *, default=None, max_schema='current')`

Strict mutation input. Only a missing file may use a supplied default factory.

### `assert_realm_writable(target, *, allow_invalid_realm=False)`

Any writer inside a known realm must understand its format; no tolerant write fallback.

### `_os_lock(fd, *, release=False)`

—

### `file_lock(target, timeout: float=5.0, poll: float=0.05, *, validate_state=True)`

Exclusive process/thread lock. Timeout and I/O errors never enter the critical section.

### `mutate_json(path, mutate, *, default=None, validate=None, timeout=5.0)`

Read, validate, mutate and atomically commit under one exclusive lock.

### `data_dir()`

ARMADA's folder on this machine: `~/.armada` — config, the realm registry, logs, caches, the Telegram credential store. Never inside a realm; see ARCHITECTURE §4.1.

### `init_logging(filename: str='armada.log')`

Send the `armada` loggers to stderr (when there is one) and to ~/.armada/logs/<filename>.

### `swallowed(logger, what: str, *, level: int=logging.ERROR, quiet: tuple=(FileNotFoundError,))`

Log the exception currently being handled, from an `except` block that falls back on purpose.
