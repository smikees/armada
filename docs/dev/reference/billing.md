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

### `_execute_external(engine, request, *, root, agent, config, run_id, reason, refused, started, reset, on_event, on_proc, invoke)`

One critical-job API attempt; billing authority stays with the Console.

### `publish_credit(root, provider, credit)`

—

### `_wait(engine, request, root, agent, job, run_id, reason, reset, on_event, on_proc, invoke, started=None, *, wait_for_credit=False, refused=None)`

—
