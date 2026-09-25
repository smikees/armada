# `armada/sysusage.py`

System usage: tokens ARMADA itself spends, as opposed to the owner's agents.

Two sources today (Mihai, 2026-09-25: "System (any jobs + Alexander if any support
conversations) should be a default line in all cost reports/graphs"):

- system jobs that call Claude directly rather than through an agent (the sign-in keep-alive);
- Alexander's support conversations (docs/dev/ALEXANDER.md).

System jobs that *wake an agent* (inbox dispatch, Telegram) are not System usage: the run is the
agent's, logged in the agent's own run file, and shows under that agent.

One JSON line per run in `<realm>/system_runs.jsonl`, the same shape the agents' run files use
(`ts`, `task`, `model`, `status`, `tokens`), so the usage code can read both the same way.

### `_path(realm_root)`

—

### `record(realm_root, task: str, model: str, tokens: dict, ok: bool=True)`

Append one System run. Never raises: accounting must not break the work it accounts for.

### `runs(realm_root)`

—
