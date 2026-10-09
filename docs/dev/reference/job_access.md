# `armada/job_access.py`

Machine-local, owner-approved access and completion checks for external jobs.

Realm files are writable by agents. A job therefore cannot grant itself additional
folders or network access by adding fields to its own JSON. Grants live in the app's
machine config outside the agent sandbox and are bound to the approved job prompt.

### class `Grant`

—


### `identity(realm_root, agent_id: str, job_id: str)`

Stable key for a job on this machine, independent of path casing on Windows.

### `fingerprint(job: dict)`

Changing a prompt or tool mode revokes its access until the owner re-approves it.

### `grant_for(realm_root, agent_id: str, job: dict | None, *, reject_reparse=False)`

—

### `expanded_checks(realm_root, checks)`

Snapshot dated output requirements for a run in the realm's timezone.

### `verify(realm_root, grant: Grant, started_wall: float)`

Return an actionable failure, or empty text when every approved check passes.

### `reported_failure(job: dict, output: str)`

Opt-in result contract for agent jobs whose model turn is not the deliverable.
