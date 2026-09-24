# `armada/util.py`

Small shared utilities: filesystem-path safety and atomic writes.

Kept dependency-free (stdlib only) so every module can import it cheaply.

### class `UnsafeSegment`

A request-supplied path segment that would escape or is malformed.


### `safe_seg(value, what: str='segment')`

Return `value` as a str if it's a single safe path segment, else raise.

### `is_safe_seg(value)`

—

### `write_text_atomic(path, text: str, encoding: str='utf-8')`

Write text so a crash/concurrent reader never sees a half-written file.

### `write_json_atomic(path, obj, indent: int=2)`

Serialize `obj` to JSON and write it atomically (see write_text_atomic).

### `sweep_temp_files(root, older_than_sec: float=3600.0)`

Delete stale `.tmp-*` files left by an atomic write that never completed. Returns the count.

### `pid_alive(pid)`

Best-effort: is a process with this pid currently running on this machine?

### `file_lock(target, timeout: float=5.0, poll: float=0.05)`

Best-effort cross-process advisory lock, so the web server and the always-on scheduler daemon don't lose each other's updates on a read-modify-write (e.g. appending to the same thread, or two edits of realm.json). Creates a sibling `<name>.lock` with O_CREAT|O_EXCL and spins up to `timeout`; if it can't acquire (stale/contended) it proceeds anyway rather than ever deadlocking the app — atomic writes still prevent corruption in that rare case.

### `data_dir()`

ARMADA's folder on this machine: `~/.armada` — config, the realm registry, logs, caches, the Telegram credential store. Never inside a realm; see ARCHITECTURE §4.1.

### `init_logging(filename: str='armada.log')`

Send the `armada` loggers to stderr (when there is one) and to ~/.armada/logs/<filename>.

### `swallowed(logger, what: str, *, level: int=logging.ERROR, quiet: tuple=(FileNotFoundError,))`

Log the exception currently being handled, from an `except` block that falls back on purpose.
