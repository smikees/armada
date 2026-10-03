# `armada/provider_login.py`

Owned browser-login processes. Only validated authorization URLs are held, in memory.

The official CLI owns OAuth and credentials. Output is drained, never logged or persisted.

### `authorization_url(provider, text)`

—

### `state(provider)`

—

### `_stop(item)`

—

### `cancel(provider)`

—

### `open_page(provider)`

—

### `begin(provider, launcher)`

—

### `_close()`

—

### `_begin_gemini(launcher)`

Google's supported CLI requires one interactive login; headless calls never prompt.
