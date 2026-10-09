# `armada/engine/mcp.py`

Translate MCP display names to their tool namespace without granting access.

### `registration_id(name: str)`

Stable CLI-safe registration, separate from the logical capability identity.

### `server_id(name: str)`

Claude-managed connectors use a collapsed, prefixed tool namespace.

### `connected_names(text: str)`

Names with an explicit Connected health result, never inferred from an icon.
