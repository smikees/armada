# `armada/provider_limits.py`

Independent, bounded subscription checks; HTTP requests never wait on a CLI.

### class `_Entry`

—


### `_probe(provider, realm)`

—

### `_failure(entry, reason, message, now)`

—

### `_run(key, entry, provider, realm)`

—

### `read(provider: str, realm=None, force: bool=False)`

Return a cached reading or pending state, without blocking other provider checks.
