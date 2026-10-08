# `armada/managed_mcp.py`

Small stdio MCP transport for a single, scoped ARMADA managed-tools invocation.

The capability credential travels in the subprocess environment, never in a prompt or argv.
No owner API credential and no production mutation endpoint is available here.

### `serve()`

—
