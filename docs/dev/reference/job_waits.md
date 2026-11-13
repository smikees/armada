# `armada/job_waits.py`

Durable pre-execution waits. Waiting owns no provider, worker or invocation lock.

### `_path(root)`

—

### `state(root)`

—

### `pending(root, agent, job)`

—

### `_save(root, key, row)`

—

### `bounds(job, fire)`

—

### `_finish_time(report)`

—

### `dependency_errors(root, job, now)`

—

### `evaluate(root, agent, job, fire, now, *, provider, refresh=True, request_id='')`

Return ready/waiting/failed; a terminal wait never silently opens again.

### `transition(root, agent, jid, status, *, request_id='')`

—

### `context(root, agent, jid)`

—

### `override_warning(root, job, *, provider='')`

—
