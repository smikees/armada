# `armada/engine/mcp_runtime.py`

Live MCP startup evidence; saved OAuth credentials are not a connection test.

### `startup_lock()`

One Armada startup/refresh at a time across app, scheduler and status probes.

### `status(server: str, reply: dict)`

Keep tool names and exact startup errors, never transport config or credentials.

### `prompt(rows, *, preflight=False)`

—

### `claude_startup(event)`

Actual per-turn init evidence, using the same namespaces as admission.

### `job_errors(rows, required, attempted_tools, *, root, provider)`

Optional startup failures remain diagnostics, not evidence of a failed task.
