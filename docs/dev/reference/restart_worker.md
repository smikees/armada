# `armada/restart_worker.py`

Standalone update supervisor, copied outside the package before replacement.

Only standard-library code runs here; the supervisor holds no installation lease.
It verifies the successor's version, painted desktop and required scheduler.

### `alive(pid)`

—

### `record(plan, phase, message, **extra)`

—

### `reading(plan, route)`

—

### `successor_endpoint(plan, owner=None)`

Follow a live successor when it had to move away from a newly occupied port.

### `readiness_error(plan)`

Reject stale servers, error pages and a desktop whose scheduler never came back.

### `verify(plan)`

—

### `ready_if_reachable(plan)`

—

### `launch_successor(plan, plan_path)`

—

### `recover_failure(plan, plan_path, reason, timeout=30)`

Rollback only an unacknowledged package after all of its leases have closed.

### `supervise(plan, plan_path, timeout=150)`

—

### `main()`

—
