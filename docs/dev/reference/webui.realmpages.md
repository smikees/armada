# `armada/webui/realmpages.py`

Realm-level management pages (Phase 3 split of agentpages): Ministers, Jobs (health grid + filters) and Artefacts.

### `_fmt_date_short(s)`

A date with its year, `17 Sep 2026` (an appointment; DESIGN_SYSTEM §9a). Falls back to the raw string.

### `_new_agent_form(realm, cancel_html: str)`

Shared appoint-a-agent form body (fields + actions). Used by the full /new/agent page and the dashboard Appoint modal — same field IDs, so mcNewAgent() works in both.

### `_reinstate_pane(realm, retired: list)`

Pick someone back out of retirement.

### `_appoint_modal(realm)`

The Appoint form as a dashboard modal — same form as /new/agent, opened in place.

### `_health_grid(realm, realm_root, today)`

Scheduler/reliability: jobs × last-7-days grid.

### `_agent_cap_counts(realm_root, aid: str)`

How many connected capabilities this agent can actually USE, per kind.

### `_cap_count_row(realm_root, aid: str, is_coord: bool=False, active_jobs: int=0)`

The card's footer tally, in two groups.

### `_realm_ministers(realm, realm_root, today)`

—

### `_jobs_view_toggle()`

List / calendar selector — borderless icons, sits at the start of a filter row. Used by both the User and the System pane, which is the point: one Jobs page, one set of views.

### `_sysjob_every(mins: int)`

A system job's interval in the same shorthand the Cadence column uses for cron jobs.

### `_sysjob_next(iso_ts: str, due_now: bool, now)`

When this job will actually run next: 'Mon 9/21, 20:00'.

### `_sysjob_when(iso_ts: str, now)`

'3h ago' / 'in 2d' / '—'. Rendered server-side so the row is complete without JavaScript.

### `_system_job_row(j, now, grid: str)`

One system job, in the same row as a user job — minus the parts that don't apply.

### `_system_jobs_table(realm_root, now)`

The System pane's list — the User jobs list, over ARMADA's own upkeep work.

### `_system_jobs_header(today)`

The User list's header, minus Owner, plus a column for Run now.

### `_job_token_estimate(jruns)`

(median total tokens per run, sample size) from this job's own telemetry.

### `_job_cost_pill(kind: str, tokens: int, n: int)`

What one run of this job costs you, in the same language the System jobs list uses.

### `_job_list_header(today, show_owner: bool, list_id: str)`

—

### `_job_row(realm_root, a, j, now, runs_all, running, show_owner: bool, open_job: str='')`

One job, expandable, identical on both pages bar the Kind and Owner cells.

### `_job_list(realm, realm_root, pairs, today, now, show_owner: bool=False, list_id: str='mc-joblist', open_job: str='')`

Header + rows for a set of (agent, job) pairs. `pairs` rather than one agent so the realm page can pour every agent's jobs into the same list.

### `_realm_jobs(realm, realm_root, today)`

—

### `_hold_banner(realm_root)`

Why this realm's scheduled jobs aren't running, where the owner looks for them.

### `_system_jobs_pane(realm, realm_root, today, now)`

The System tab: the same list and calendar views as User jobs, over ARMADA's own upkeep work.

### `_jobs_filter_bar(owners, n: int, now, lead: str='', pfx: str='jf', table: str='mc-jobstable', f1key: str='owner', f1_label: str='All owners')`

Owner · Last-run · Cadence dropdowns above a Jobs table (client-side filtering), plus an 'as of' timestamp and a refresh button. `lead` is placed at the very start of the row (used for the list/calendar view selector). Dropdowns match the realm switcher style.
