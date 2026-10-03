# `armada/providers.py`

App-wide provider connections. Credentials remain with the official CLIs.

Rendering reads the last observation; explicit status requests probe the CLIs. Disconnecting
blocks new Armada calls without signing other applications out or changing stored agent models.

### `_check(provider)`

—

### `allowed(provider)`

—

### `require_allowed(provider)`

—

### `_save(provider, **values)`

—

### `connected()`

Last confirmed usable connections, without running a CLI during rendering.

### `observed()`

—

### `status(provider, force=False)`

—

### `statuses(force=False)`

—

### `disconnect(provider)`

—

### `connect(provider)`

Use an existing CLI login, or launch the CLI's browser OAuth flow without a console.
