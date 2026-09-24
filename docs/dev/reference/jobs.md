# `armada/jobs.py`

Agent-authored job proposals (pending owner approval).

An agent that runs with tools can PROPOSE a scheduled job for itself by writing a JSON file to
its own ``jobs/_pending/<slug>.json`` (with its Write tool — reliable on this host; only the
Claude Code bash *sandbox* is flaky here, plain file writes are fine). Proposals live in the
``_pending/`` sub-folder, which the scheduler and the realm reader never glob (both use the
non-recursive ``jobs/*.json``), so a proposal simply CANNOT fire until the owner approves it.

``approve`` validates a proposal, stamps provenance + a ``created`` date, marks it enabled, and
writes it as the canonical ``jobs/<slug>.json`` (removing the pending file). ``reject`` just
deletes the pending file. This preserves the "explicit permission required" posture: an agent
may line up work for itself, but nothing new auto-runs on the owner's machine without a click.

### `_now()`

—

### `_pending_dir(realm_root, agent_id: str)`

—

### `_read_json(p: Path)`

—

### `slugify(s: str)`

—

### `validate(job: dict)`

Validate a proposal dict (no disk I/O). Returns (ok, errors, normalized_job).

### `iter_pending(realm_root)`

Yield (agent_id, slug, job, path) for every pending proposal in the realm.

### `list_for_agent(realm_root, agent_id: str)`

Validated proposals owned by one agent: [{slug, job, ok, errors}].

### `count_pending(realm_root)`

—

### `_find_pending(realm_root, agent_id: str, slug: str)`

Locate a pending file by (agent, stem) WITHOUT building a path from the raw slug — match against real stems on disk so an odd slug can't traverse out of the folder.

### `approve(realm_root, agent_id: str, slug: str)`

—

### `reject(realm_root, agent_id: str, slug: str)`

—

### `ledger_events(realm_root, agent_id: str)`

—

### `log_event(realm_root, agent_id: str, jid: str, name: str, event: str)`

—

### `sync_proposals(realm_root, agent_id: str)`

Record a 'proposed' ledger event for any _pending file that isn't already open in the ledger. Called after an agent turn (the agent wrote the file directly, so we detect it here).

### `_read_jsonl(p: Path)`

—

### `status_for_agent(realm_root, agent_id: str)`

Full-visibility snapshot of one agent's job proposals, derived from the durable ledger: pending — proposals currently in _pending (ground truth on disk), approved — proposals the owner approved (now live jobs), rejected — proposals the owner rejected, history — the chronological event trail (newest first), so nothing is lost.
