# `armada/api_fallback.py`

Owner API fallback choices; the provider enforces externally managed budgets.

Keys stay in provider_keys, never in this policy, a realm, or a transcript. Local
usage is an observation of Armada calls, not the provider's authoritative balance.

### `_path()`

—

### `_read()`

—

### `_identity(root, agent)`

—

### `managed(provider)`

—

### `settings(provider='claude', root=None, agent='')`

—

### `save(provider, *, enabled=None, root=None, agent='', key_source=None, api_key=None, remove_key=False)`

—

### `credential(provider, root, agent)`

—

### `verify(provider, *, api_key=None, root=None, agent='', key_source=None)`

Free model-list authentication check; never make a generation request.

### `redact(value, secret)`

—

### `_usage_path(provider)`

—

### `reported_cost(value)`

A finite nonnegative receipt amount, or None for unavailable data.

### `_usage(provider)`

—

### `start(provider, run_id, root, agent)`

—

### `finish(provider, run_id, result)`

—

### `credit(provider='claude')`

—
