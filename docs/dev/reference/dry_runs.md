# `armada/dry_runs.py`

Temporary draft jobs, with separate history, explicit models and owned cancellation.

### `base(root)`

—

### `directory(root, agent, job, run_id)`

—

### `settings(job)`

—

### `models(root)`

—

### `is_command(job)`

—

### `start(root, agent, job_id, model='', *, requested_by='user', engine=None)`

Capture configuration before dispatch. No production invocation or job marker is used.

### `_execute(root, folder, job, info, session, engine)`

—

### `_command(root, folder, job, info, session)`

Only the user's explicit, fingerprinted draft command may execute.

### `output_files(folder)`

—

### `listing(root, agent, job)`

—

### `read(root, agent, job, run_id)`

—

### `stop(root, agent, job, run_id)`

—

### `prune(root, *, now=None)`

—
