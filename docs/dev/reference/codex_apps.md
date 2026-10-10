# `armada/codex_apps.py`

Codex-native connected apps, discovered through the CLI's app-server protocol.

### `rpc(method, params, *, cwd=None, config=(), max_line=None, timeout=45)`

—

### `valid_id(value)`

—

### `inventory(*, force=False, cwd=None)`

Runtime inventory, not the entire public app directory or its display metadata.

### `valid_plugin(name)`

—

### `plugin_url(name)`

The plugin's own page in ChatGPT, where its install consent and sign-in happen.

### `plugin_directory(*, cwd=None)`

The ChatGPT plugin directory (chatgpt.com/plugins) as Codex sees it, via `plugin/list`.

### `service(plugin, *, cwd=None)`

—

### `scoped_args(allowed, *, cwd=None)`

Invocation-only app policy. Preserve per-tool restrictions in the owner's config.

### `verify_snapshot(result, allowed)`

Check the actual thread before sending any prompt to the model. Never trust UI metadata.
