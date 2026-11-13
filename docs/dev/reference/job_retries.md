# `armada/job_retries.py`

Bounded job retries with durable attempt evidence and conservative replay rules.

### `count(job)`

—

### `validate(value)`

—

### `backoff(job)`

Owner-selected delays, indexed by retry number; replay admission is unchanged.

### `retryable(report)`

—

### `state_path(root, agent, job)`

—

### `pending(root, agent, job)`

—

### `cancel_waiting(root, agent, job, series_id)`

Withdraw only the backoff that this queued scheduler attempt resumed.

### `_waiting(data)`

—

### `execute(root, agent, job_id, job, run, *, sleep=time.sleep, clock=time.time)`

One logical invocation, including retries. Unknown crash outcomes stay held.
