# `armada/run_policy.py`

Machine-local owner choices, approval seals and fail-closed API reservations.

Realm-authored files are never authority for spending, fallback or priority grants.
No credentials are stored in this module's policy or accounting files.

### `_path()`

—

### `_read()`

—

### `scope_id(root, agent='')`

—

### `validate_job(job)`

—

### `_positive(value, name)`

—

### `seal_job(root, agent, job)`

—

### `verify_job(root, agent, job)`

—

### `import_legacy(root)`

Once on upgrade, preserve existing owner ceilings without changing job files.

### `settings(root=None, agent='', job=None, provider='claude')`

—

### `save(root, values, *, provider='claude', agent='', global_provider=False)`

—

### `audit(action, root=None, **values)`

—

### `_ledger_path(provider)`

—

### `cycle(settings, now=None)`

—

### `_ledger(provider)`

—

### `initialise_ledger(provider)`

Only owner key setup creates the first ledger; a missing used ledger stays closed.

### `credit(provider='claude', config=None)`

—

### `_stamp()`

—

### `_in_cycle(row, start)`

—

### `reserve(provider, invocation, config)`

—

### `settle(provider, invocation, cost)`

—

### `notify_once(root, key, message)`

—

### `admission(root, agent, thread, provider)`

Scheduling hints derived only from approved jobs and owner choices.

### `time_now()`

—
