# `armada/capscan.py`

Real capability version-scan + update, via the Claude Code CLI.

ARMADA can genuinely see/update only capabilities registered with the CLI (`claude plugin`,
`claude mcp`). It reconciles those into the realm's capability list with real installed/latest
versions and applies updates with `claude plugin update`. Capabilities managed elsewhere (the
desktop app's plugin/connector layer) aren't visible here — we simply leave them untouched.

Everything here is best-effort and never raises out: a missing CLI or an offline registry just
means "nothing to report", so a scan can't break the app or a run.

### `_lp()`

—

### `_run(args, timeout=60)`

—

### `_norm_plugin(d: dict)`

Normalise one plugin record from `claude plugin list [--available] --json` (shape-tolerant).

### `list_plugins()`

Installed plugins with any available (latest) version — real data from the CLI, or [].

### `list_mcp()`

Configured MCP servers from the CLI as [{name, remote, command}].

### `extension_identity(command: str)`

{id, publisher, name} for a Claude Desktop extension command, or {} if it isn't one.

### `_discovered_provenance(command: str)`

What the command line proves about a discovered server.

### `_norm(s)`

—

### `reconcile(toolkit: dict, plugins: list, mcp: list, *, discover: bool=False)`

Write real installed/latest versions onto the toolkit items this realm already has.

### `scan(realm_root)`

Scan CLI-known capabilities and write real installed/latest into realm.json. Best-effort.

### `apply_plugin_update(name: str)`

Really update a CLI-installed plugin (`claude plugin update <name>`).
