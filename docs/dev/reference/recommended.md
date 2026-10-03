# `armada/recommended.py`

Starter capabilities with explicit upstream sources and connection requirements.

Skills are downloaded through the catalogue. Optional MCP entries are saved for setup,
not reported as connected: their upstream installers and account consent are separate.
See docs/dev/STARTER_CAPABILITIES.md for the reviewed shortlist and integration work.

### `for_template(template: str)`

The list with `on` set for this template: an entry's own default, or its default_for.

### `by_key(key: str)`

—
