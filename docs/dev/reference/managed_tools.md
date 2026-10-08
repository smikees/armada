# `armada/managed_tools.py`

Invocation-scoped MCP tools for draft jobs and read-only inspectors.

This broker deliberately has no shell, network, generic production write, or owner HTTP action.
Provider adapters expose only this MCP server during managed turns.

### `_tool(name, description, properties=None, required=(), *, read_only=True)`

—

### `_string(description)`

—

### class `ManagedTools`

—

- `ManagedTools.__init__(self, root, agent, *, output=None, job=None, inspector=False)` — —
- `ManagedTools.tools(self)` — —
- `ManagedTools._authorize(self)` — —
- `ManagedTools.call(self, name, arguments)` — —
- `ManagedTools._read(path)` — —
- `ManagedTools.__enter__(self)` — —
- `ManagedTools.configure(self, engine)` — —
- `ManagedTools.__exit__(self, *args)` — —

### `claude_args(engine)`

—

### `codex_args(engine, *, cwd=None)`

—
