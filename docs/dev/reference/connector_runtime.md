# `armada/connector_runtime.py`

Provider-specific MCP connections for realm capabilities.

A realm grant is permission, not a provider login. Claude's MCP inventory and Codex's
MCP inventory are separate; never infer one provider's authentication from the other.

### `_login_key(realm_root, cap, provider)`

—

### `_codex_drive_client(cap)`

Read only the presence of Codex's own pre-registered OAuth client ID.

### `_login_finished(realm_root, provider)`

Discard earlier health checks; completed login alone never means Connected.

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

### `_claude_rows(realm_root=None)`

Read Claude's current MCP health, without returning URLs or credentials.

### class `_ClaudeInventory`

Compatibility boolean inventory with endpoint evidence retained only in memory.

- `_ClaudeInventory.__init__(self)` — —

### `claude_inventory()`

—

### `claude_connection(cap: dict, inventory: dict[str, bool | None] | None)`

—

### `gemini_inventory()`

The same global inventory admitted by GeminiEngine; no credential transfer.

### `gemini_connection(cap, inventory)`

—

### `connection_detail(cap, provider, state, error='')`

Owner-facing state and recovery action; unsupported is never called disconnected.

### `connection_snapshot(realm_root, *, force=False, provider=None)`

Nonblocking, independent provider checks; pending checks have a fixed deadline.

### `is_provider_placeholder(cap: dict)`

Old auto-discovery filed the model app itself as a user MCP connector.

### `connect_codex(cap: dict, realm_root=None)`

Register a reviewed realm endpoint and start Codex's own browser OAuth flow.

### `connect_claude(cap: dict, realm_root=None)`

Authenticate the existing Claude registration; never clone a cloud proxy.

### `connect_gemini(cap, realm_root=None, *, authenticate=False)`

Use the installed CLI's registration command and interactive /mcp authentication.

### `open_native_setup(cap, provider)`

The provider owns installation consent and OAuth; ARMADA never accepts either.

### `connector_setup(cap: dict, provider: str)`

Credential-free setup guidance for an approved connector, never evaluated as code.
