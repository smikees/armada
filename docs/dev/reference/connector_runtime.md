# `armada/connector_runtime.py`

Provider-specific MCP connections for realm capabilities.

A realm grant is permission, not a provider login. Claude's MCP inventory and Codex's
MCP inventory are separate; never infer one provider's authentication from the other.

### `codex_endpoint(cap: dict)`

Return a direct HTTPS MCP endpoint, never a Claude-only proxy or local command.

### `codex_inventory(engine: CodexEngine | None=None)`

Read the effective Codex server inventory; None means it could not be verified.

### `codex_connection(cap: dict, inventory: dict[str, dict] | None)`

Connection state for a *particular* provider, not the realm's generic status.

### `codex_live_inventory(realm_root, engine: CodexEngine | None=None)`

Verify startup in a gated, ephemeral thread without making a model request.

### `_identity(value: str)`

—

### `claude_inventory()`

Read Claude's current MCP health, without returning URLs or credentials.

### `claude_connection(cap: dict, inventory: dict[str, bool] | None)`

—

### `connection_snapshot(realm_root, *, force=False)`

Nonblocking, independent provider checks; pending checks have a fixed deadline.

### `is_provider_placeholder(cap: dict)`

Old auto-discovery filed the model app itself as a user MCP connector.

### `connect_codex(cap: dict, realm_root=None)`

Register a reviewed realm endpoint and start Codex's own browser OAuth flow.
