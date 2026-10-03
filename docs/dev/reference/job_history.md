# `armada/job_history.py`

Job transcripts live separately from owner conversations; old logs stay intact.

### `save_transcript(agent_dir, run_id: str, content: dict)`

Keep large transcripts out of the small accounting log used by every dashboard.

### `thread_name(job_id: str)`

—

### `reports(agent_dir, job_id: str | None=None)`

—

### `apply_annotation(agent_dir, event: dict)`

Overlay a correction in views; the original accounting/transcript stays immutable.

### `annotate(agent_dir, run_id: str, result: dict, reason: str, *, supporting_evidence: dict)`

Add a dated correction to an existing run, never editing its original report.

### `legacy_turns(agent_dir, thread: str, messages: list[dict])`

Match completed old job turns by report timestamp; never rewrite the chat log.

### `_legacy_reports(agent_dir, mtime, size)`

—

### `transcript(agent_dir, ev: dict)`

Read a durable run snapshot, falling back to its original thread for old runs.
