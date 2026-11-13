# `armada/job_rules.py`

Validated, owner-approved prerequisites for unattended jobs; no execution here.

### `cadence(job)`

Present a window's opening time while preserving its scheduled days.

### `reference(value)`

—

### `validate(job)`

Reject ambiguous windows, unbounded waits and malformed automation controls.

### `validate_graph(root, agent, job)`

Check proposed dependency/fallback edges against the complete saved graph.
