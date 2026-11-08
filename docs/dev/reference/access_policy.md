# `armada/access_policy.py`

Strict, provider-neutral connector tool and filesystem write policy.

The owner edits policy; models cannot grant permissions. Missing fields preserve
legacy behavior, whereas an explicit empty allowlist grants nothing.

### `error(message)`

—

### `patterns(value, label, *, paths=False)`

—

### class `ToolRule`

—

- `ToolRule.permits(self, tool)` — —

### class `AccessPolicy`

—

- `AccessPolicy.scoped(self)` — —
- `AccessPolicy.rule(self, connector)` — —

### `validate(realm, agent)`

Validate even unused policies; a malformed policy never becomes unrestricted.

### `load(root, agent)`

—

### `path_matches(path, pattern)`

Case-insensitive path globs: * stays in a segment; ** spans folders.

### `writable_path(root, policy, value, *, agent_records=False)`

Validate the canonical target and every ancestor before any write occurs.

### `_updated(before, changes, agent)`

—

### `preview(root, agent, changes, provider, *, realm_defaults=False)`

Evaluate an unsaved owner edit with the execution validator, without writes or discovery.

### `save(root, agent, changes)`

Owner API mutation; policy and its change log are one locked atomic write.
