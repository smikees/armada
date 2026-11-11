# `armada/worker_bootstrap.py`

Standalone, unprivileged process trampoline. Never imports the Armada application.

The owner writes the launch description in a worker-readable, owner-writable directory.
Only this short command crosses CreateProcessWithLogonW's command-line limit. The whole
trampoline and its descendants enter the invocation Job Object before execution resumes.

### `observation_rights(spec)`

Retain owner administration of worker children/files; no reverse access.

### `main()`

—
