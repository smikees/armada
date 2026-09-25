# `armada/sysjobs.py`

System jobs — the recurring work ARMADA does to keep itself current.

Some of what the app needs doing is on a clock rather than on demand: asking Anthropic which models
exist so new ones appear and retired ones are marked, checking whether capabilities have updates,
trimming history so it can't grow forever. Until now these were scattered — the model refresh ran on
a background thread at every server start (so fifteen times during a busy session, and never if the
app stayed shut), and the update scan only happened if someone pressed a button.

Shape, mirroring system skills: the DEFINITION ships in this package, so it can't be edited or
deleted and it improves when ARMADA updates. Only the STATE — last run, outcome, whether you've
switched it off — lives in the realm.

Two things are deliberate.

**Cost is declared, not implied.** A job is either `free` (deterministic local work) or `quota` (it
invokes agents and spends your Claude subscription). The UI shows which, because "system job" must
never quietly become "thing that spends money".

**Silence is the enemy.** Background work that fails invisibly is the failure mode that bit this
app twice in one day. Every run records its outcome, and failures land in the notification feed.

### `_job_model_catalog(realm_root)`

—

### `_job_capability_updates(realm_root)`

—

### `_job_inbox_dispatch(realm_root)`

Deliver agent-to-agent tasks. Declared QUOTA because it *can* invoke agents — but only where a message is actually waiting; an empty pass is a handful of directory listings and costs nothing.

### `_job_telegram_inbox(realm_root)`

Answer prompts sent from Telegram. QUOTA because a message becomes an agent run — but the check itself is one HTTPS call and costs nothing, so an idle pass is free.

### `_job_usage_keepalive(realm_root)`

Keep Claude Code's sign-in fresh, so the usage bars don't go dark between agent runs.

### `_record_keepalive(realm_root, stdout: str, ok: bool)`

Count the keep-alive's few tokens as System usage (sysusage), from the CLI's JSON result.

### `_job_prune_history(realm_root)`

—

### `_job_environment_context(realm_root)`

Re-probe the machine and rebuild the system memory ("Environment, realm and owner context").

### `_job_catalogue_refresh(realm_root)`

Re-read what could be added: the plugin marketplaces on this machine and Anthropic's public skills repository.

### `_job_app_update(realm_root)`

Keep ARMADA itself up to date (5.4). Machine-wide, though it's listed in every realm: the updater keeps its own clock, so a second realm's pass inside the same 12 hours just reports the last answer instead of asking GitHub again.

### `_state_path(realm_root)`

—

### `state(realm_root)`

—

### `_save(realm_root, st: dict)`

—

### `set_enabled(realm_root, jid: str, on: bool)`

—

### `is_enabled(realm_root, jid: str)`

—

### `_record_run(entry: dict, ts: str, ok: bool)`

Append one run to a job's rolling history, oldest trimmed first.

### `_parse(ts: str)`

—

### `interval_minutes(j: dict)`

A job declares either every_hours or every_minutes — inbox delivery needs to run far more often than housekeeping, and checking costs nothing when there's nothing to do.

### `due(realm_root, jid: str, now=None)`

Interval-based, not cron: these are 'every so often', not 'at 07:00'.

### `status(realm_root)`

Everything the System tab needs: definition + live state, newest-relevant first.

### `run_one(realm_root, jid: str, manual: bool=False)`

Run one system job now. Never raises: a broken housekeeping job must not take down the scheduler or the request that triggered it.

### `run_due(realm_root)`

Every enabled job whose interval has elapsed. Called once per scheduler tick.
