# `armada/managed_tools.py`

Invocation-scoped MCP tools for draft jobs and narrowly scoped inspectors.

This broker has no shell, live connectors, web or owner HTTP action. Inspector outputs
and owner notification use host-managed operations with no model-chosen recipient.
Provider adapters expose only this MCP server during managed turns.

### `_tool(name, description, properties=None, required=(), *, read_only=True)`

—

### `_string(description)`

—

### class `ManagedTools`

—

- `ManagedTools.__init__(self, root, agent, *, output=None, job=None, inspector=False, snapshot=None, script_grant=None, cancelled=None)` — —
- `ManagedTools.tools(self)` — —
- `ManagedTools._authorize(self)` — —
- `ManagedTools.call(self, name, arguments)` — —
- `ManagedTools._read(path)` — —
- `ManagedTools.__enter__(self)` — —
- `ManagedTools.configure(self, engine)` — —
- `ManagedTools.seal(self)` — Expire actions before terminal report persistence and snapshot their audit.
- `ManagedTools.__exit__(self, *args)` — —

### `claude_args(engine)`

—

### `codex_args(engine, *, cwd=None)`

—
