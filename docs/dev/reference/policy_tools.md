# `armada/policy_tools.py`

Invocation-local filesystem tools and durable policy refusal evidence.

### class `PolicyAudit`

—

- `PolicyAudit.__init__(self, root, agent)` — —
- `PolicyAudit.offer(self, names)` — —
- `PolicyAudit.refuse(self, *, tool='', path='', reason='Denied by owner policy')` — —
- `PolicyAudit.report(self)` — —

### class `PolicyTools`

File writes are checked on every call; no shell operation is provided.

- `PolicyTools.__init__(self, root, agent, audit, *, cancelled=None)` — —
- `PolicyTools.tools(self)` — —
- `PolicyTools.call(self, name, arguments)` — —
- `PolicyTools._validated_content(self, path, content)` — —
- `PolicyTools.__enter__(self)` — —
- `PolicyTools.configure(self, engine)` — —

### `codex_args(tools)`

—

### `claude_args(tools)`

—
