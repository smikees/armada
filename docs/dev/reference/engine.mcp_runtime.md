# `armada/engine/mcp_runtime.py`

Live MCP startup evidence; saved OAuth credentials are not a connection test.

### `startup_lock()`

One Armada startup/refresh at a time across app, scheduler and status probes.

### `status(server: str, reply: dict)`

Keep tool names and exact startup errors, never transport config or credentials.

### `prompt(rows)`

—
