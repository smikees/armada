# `armada/job_results.py`

Versioned per-run job results. Execution, audit and delivery are independent.

### `instructions(run_id: str, job: dict)`

—

### `original_answer(output: str)`

Hide only the structured machine block; keep the agent's legacy marker verbatim.

### `_parse(output: str, run_id: str)`

—

### `_path(value, roots)`

—

### `check_aspect(check: dict)`

Approved checks may declare their aspect; old Telegram/publication checks retain it.

### `requirements(job: dict, checks)`

Add sealed machine-approved outputs/destinations without changing saved job prompts/grants.

### `evaluate(output: str, *, run_id: str, job: dict, root: Path, started: float, runtime_execution: str='completed', runtime_error: str='', roots=(), checks=())`

Validate claims against this run. Contract defects warn; runtime errors stay operational.

### `status(result: dict)`

—

### `label(result: dict)`

—

### `reason(result)`

Operational failure precedes secondary contract-validation diagnostics.
