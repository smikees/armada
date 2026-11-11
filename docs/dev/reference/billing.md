# `armada/billing.py`

Provider lane selection for one invocation; retries never bypass replay evidence.

### `_refusal_path(provider)`

—

### `refusal(result)`

—

### `_reset(text)`

—

### `exhausted(root, provider='claude', model='')`

—

### `connector_guard(root, agent, request)`

—

### `replay_safe(result, events, *, root, job, run_id, started)`

—

### `execute(engine, request, *, root, agent, job, run_id, on_event, on_proc, invoke)`

—

### `notify_credit(root, provider, credit)`

—

### `publish_credit(root, provider, credit)`

—

### `_wait(engine, request, root, agent, job, run_id, reason, reset, on_event, on_proc, invoke, started=None, *, wait_for_credit=False, refused=None)`

—
