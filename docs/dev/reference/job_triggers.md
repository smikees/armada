# `armada/job_triggers.py`

Audited, bounded requests to run sealed jobs; never accepts execution instructions.

### `_path(root)`

—

### `history(root)`

—

### `_update(root, identity, **values)`

—

### `active(root, agent, job)`

—

### `validate_coordinator(root, agent, job, coordinator)`

Recheck owner authorization both at request time and after admission queues.

### `prerequisites(root, job, request)`

Automatic fallback starts obey their own approved prerequisites and deadline.

### `wait_for_prerequisites(root, request)`

—

### `enqueue(root, agent, jid, reason, *, coordinator='', fallback_for=None)`

—

### `fallback(root, agent, job, report)`

—

### `report_fields(job)`

—
