# `armada/engine/process.py`

Owned CLI lifetime: bounded pipe draining, output-independent deadlines and tree cleanup.

Provider modules own protocol parsing. A successful process exit alone is not a successful turn.
Windows children start suspended, enter a kill-on-close Job Object, then resume; POSIX children
start a new session. Cancellation is a request to this owner, never a bare Popen.kill().

### class `ProcessResult`

—


### class `RunProcess`

Cancellation handle passed to existing on_proc callers; kill requests owned cleanup.

- `RunProcess.__init__(self, process)` — —
- `RunProcess.pid(self)` — —
- `RunProcess.poll(self)` — —
- `RunProcess.kill(self)` — —

### `safe_emit(callback, event)`

A disconnected observer must not abandon the child or prevent terminal persistence.

### `supervise(args, *, prompt, on_line, timeout, cwd=None, env=None, on_proc=None, raw_output=False, launch=None)`

Run one owned process; on_line receives complete lines and may reject malformed output.

### `supervise_command(args, *, timeout, cwd=None, env=None, on_proc=None, launch=None)`

Own a noninteractive command without parsing a provider protocol.

### `supervise_rpc(args, *, start, on_message, timeout, cwd=None, env=None, on_proc=None)`

Own one interactive newline-JSON CLI session until its terminal notification.
