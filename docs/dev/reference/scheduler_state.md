# `armada/scheduler_state.py`

Scheduler leases and durable daily attempts. A PID is diagnostic, never lock ownership.

The kernel lease prevents concurrent dispatch; the attempt record prevents replay after a crash.
Neither can make a provider's external side effects exactly once. See dev/PERSISTENCE.md.

### `_owner_path(root)`

—

### `_stamp()`

—

### class `Lease`

An open kernel lock, an unguessable incarnation token, and a non-reentrant tick gate.

- `Lease.__init__(self, root, lock, token)` — —
- `Lease.verify(self, root)` — —
- `Lease.close(self)` — —

### `acquire(root)`

Return exclusive ownership, None when busy; raise on any persistence error.

### `holder(root)`

Best-effort status; stale modern metadata is not evidence of a running scheduler.

### `release(lease: Lease)`

—

### `_attempt_path(root, day)`

—

### `_key(agent, job)`

—

### `_attempts(path)`

—

### `claim(lease: Lease, agent, job, day)`

Persist admission before side effects. Return (attempt, newly_claimed). Never replay.

### `inspect_attempt(root, agent, job, day)`

Advisory dry-run read; creates neither state nor lock files.

### `resume_waiting(lease, agent, job, day)`

Transfer a known finished-attempt backoff after a scheduler restart.

### `finish(lease: Lease, attempt, status)`

Complete only our own claim; a failure leaves it uncertain and ineligible for replay.
