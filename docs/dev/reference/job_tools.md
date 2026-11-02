# `armada/job_tools.py`

Read-only job tool checks and a daily owner notification, independent of providers.

### class `ToolConfigurationError`

A saved job cannot meet its output contract with its current tools setting.


### `agent_job(job: dict)`

—

### `required_results(job: dict)`

—

### `needs_tools(job: dict)`

Conservative review hint, never permission to grant tools or block a text-only job.

### `warning(job: dict)`

—

### `guard(job: dict)`

Fail before model selection, context compaction or provider execution.

### `findings(realm_root, only_agent: str='')`

Local reads only; safe on a page-render path. Never rewrite a job.

### `lint(realm_root)`

Notify once per job, durably deduplicated across app restarts and daily scans.

### `scan_all(primary=None)`

Check every registered active realm; one inaccessible realm cannot stop the others.

### `monitor(primary, stop: threading.Event)`

Run at startup and every day, even when scheduling is disabled or the app is in the tray.
