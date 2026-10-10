# `armada/codex_apps.py`

Codex-native connected apps, discovered through the CLI's app-server protocol.

### `rpc(method, params, *, cwd=None, config=())`

—

### `valid_id(value)`

—

### `inventory(*, force=False, cwd=None)`

Runtime inventory, not the entire public app directory or its display metadata.

### `service(plugin, *, cwd=None)`

—

### `scoped_args(allowed, *, cwd=None)`

Invocation-only app policy. Preserve per-tool restrictions in the owner's config.

### `verify_snapshot(result, allowed)`

Check the actual thread before sending any prompt to the model. Never trust UI metadata.
