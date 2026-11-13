# `armada/connector_health.py`

No-model connector heartbeats with durable history and bounded background checks.

### `_key(root)`

—

### `_path(root)`

—

### `settings(root)`

—

### `save(root, values)`

Owner endpoint only. Watching never grants an agent access to a connector.

### `snapshot(root)`

—

### `public_error(text)`

Preserve error codes/text, removing transport URLs and credential-like values.

### class `_NoRedirect`

—

- `_NoRedirect.redirect_request(self, *args, **kwargs)` — —

### `server_check(endpoint)`

An unauthenticated transport check proves reachability only, never tool access.

### `incident_check()`

—

### `probe(root, provider, ids)`

Only inventory/control messages; never sends a user turn or calls a broker tool.

### `record(root, provider, rows, now=None)`

—

### `request(root, provider, ids, *, max_age=300, not_before=0)`

Coalesce checks across processes. Pending work consumes no execution ticket.

### `context(root)`

—

### `_context(root)`

—

### `tick(root, now=None)`

Weekday watches plus faster checks around jobs, without blocking discovery.
