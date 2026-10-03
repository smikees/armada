# `armada/job_retries.py`

Bounded job retries with durable attempt evidence and conservative replay rules.

### `count(job)`

—

### `validate(value)`

—

### `retryable(report)`

—

### `state_path(root, agent, job)`

—

### `pending(root, agent, job)`

—

### `_waiting(data)`

—

### `execute(root, agent, job_id, job, run, *, sleep=time.sleep, clock=time.time)`

One logical invocation, including retries. Unknown crash outcomes stay held.
