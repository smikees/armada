# `armada/tool_admission.py`

Compile glob policy to closed, concrete provider tool lists.

Inventories are names only, never credentials. Exact allowlists prevent a newly
added server tool from acquiring access until its inventory has been refreshed.

### `native_limits(names, entry, allow_key, deny_key)`

Intersect ARMADA grants with existing provider restrictions.

### `inventory(root)`

—

### `remember(root, connector, names, provider)`

—

### `save_names(root, connector, names)`

Owner-confirmed inventory for providers without a no-model listing API.

### `known_names(root, cap, provider)`

—

### class `ToolAdmission`

—

- `ToolAdmission.__init__(self, root, agent, provider, audit)` — —
- `ToolAdmission.offer(self, sid, names)` — —
- `ToolAdmission.observe(self, event)` — —
- `ToolAdmission.observed_tools(self, names)` — Record adapter startup evidence, checking it against the compiled policy.

### `claude_args(engine)`

—

### `verify_engine_version(engine)`

Do not let an older CLI silently ignore newly enforced config keys.
