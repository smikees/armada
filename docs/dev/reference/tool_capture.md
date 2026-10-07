# `armada/tool_capture.py`

Opt-in local tool-result capture, run audits and conservative retention.

### `matches(tool, patterns)`

Case-sensitive, whole-name shell globs, independent of the host OS.

### `_safe_path(base, relative)`

Reject traversal, Windows aliases and reparse points before filesystem access.

### `validate(job, realm_root, job_id, *, run_id='validation', date=None)`

—

### class `ToolCapture`

Synchronous writes at result arrival; failures are audit data, never observer exceptions.

- `ToolCapture.__init__(self, root, job, job_id, run_id, provider, supported, agent)` — —
- `ToolCapture.fail(self, reason)` — —
- `ToolCapture._checked(self)` — —
- `ToolCapture.on_event(self, event)` — —
- `ToolCapture._event(self, event)` — —
- `ToolCapture.finish(self)` — —
- `ToolCapture.report(self)` — —
- `ToolCapture.audit(self, result)` — —

### `prune(realm_root)`

Prune only registered, expired run payloads; never recursively delete a folder.
