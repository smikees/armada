# `armada/webui/agentbits.py`

Agent-rendering primitives (Layer 1, carved from _core.py in Phase 3).

Portraits/avatars, per-agent activity + status dots, model chips/marks, autonomy badges, run
history and the goals cell — shared by the Register, minister cards, goals and agent pages.
Imports only lower layers (never _core), so _core imports these names back without a cycle.

### `_bust(size: int, coord: bool)`

—

### `_avatar_file(realm_root, agent_id: str)`

—

### `_colour_peek(size: int)`

How far the colour disc sticks out past the avatar, in px.

### `_status_dot_on_avatar(state: str, size: int, grow: int=0)`

The activity dot, sat on the avatar's lower-right corner.

### `_portrait(realm_root, a, size: int, color: str='', dot: bool=False, dot_grow: int=0)`

An uploaded avatar image if present, else the generic bust.

### `_runs(realm_root: Path, agent_id: str)`

—

### `_health7(runs: list[dict], today: datetime.date)`

7 colour cells, oldest→newest, from run-reports.

### `_running_markers(realm_root, agent_id: str)`

Stems of fresh .running markers (jobs *and* the reserved '_chat' interactive-run marker).

### `_agent_busy(realm_root, agent_id: str)`

True if the agent is actively running anything right now — a scheduled job or a live chat.

### `_chat_running(realm_root, agent_id: str, thread: str)`

Is a live chat turn running in THIS thread right now?

### `_has_pending_proposals(realm_root, agent_id: str)`

True if the agent has job proposals sitting in _pending, awaiting the owner's approval.

### `_agent_has_unread(realm_root, agent_id: str)`

True if any of the agent's threads is flagged unread (unseen output).

### `_agent_activity(realm_root, agent_id: str)`

Live activity state for the status dot, highest-priority first: working — a run is executing right now (.running marker) input — the agent has a job proposal awaiting the owner's approval unseen — the agent has output in a thread the owner hasn't marked read idle — nothing pending.

### `_activity_dot(state: str, size: int=8)`

A free-standing status dot. Nothing renders one any more — the dot lives on the avatar's corner now (see _status_dot_on_avatar) — but it stays exported because several modules import it, and it's the obvious thing to reach for if a dot is ever needed away from an avatar.

### `_goals_cell(realm_root, a)`

Goals column: just the count of goals this agent advances (the titles live in the tooltip).

### `_jobs_cell(a)`

Jobs column, built like the Goals one beside it — a bare digit next to a pill read as a different kind of fact. Counts jobs that are on, which is the number that decides anything.

### `_pretty_model(m)`

Concrete model id → versioned label, e.g. 'claude-opus-4-8' → 'Opus 4.8', 'claude-sonnet-4-5-20250929' → 'Sonnet 4.5', 'claude-opus-5' → 'Opus 5'. Version digits after the family are joined with '.', stopping at a date stamp (≥6 digits). Family-only ids ('opus') stay 'Opus'. Keeps the exact version so the by-model split distinguishes e.g. Opus 4.7 vs 4.8.

### `_model_chip_label(value: str)`

A stored model value (concrete id 'claude-opus-5' or old label 'Claude Opus 5') → (is_claude, friendly label 'Claude Opus 5') for the model chips, so the icon + name always show.

### `_agent_stored_color(realm_root, agent_id: str)`

The agent's chosen colour from agent.json ('' if none/unreadable).

### `_thread_meta(agent_dir)`

—

### `_autonomy_of(realm_root, aid: str)`

—

### `_autonomy_badge(mode: str, size: int=14)`

—

### `_agent_model_effort(realm, realm_root, aid: str)`

—

### `_model_mark(model_value: str, size: int=12, effort: str='')`

The Claude mark for a model chip, tinted by token-consumption on the shared gradient. With an `effort`, the tint reflects the model+effort combo (agents); without it, the model alone (Usage breakdown). '' for non-Claude models.

### `_model_chip(model: str, effort: str, size: int=12)`

—

### `_running_jobs(realm_root, agent_id: str)`

Job ids with an in-progress run. Excludes reserved '_'-prefixed markers (e.g. '_chat', the interactive-chat marker) so they never masquerade as a running scheduled job.

### `_job_prompt(realm_root, agent_id: str, job_id: str)`

—

### `_job_created(realm_root, agent_id: str, job_id: str, jc: dict)`

—

### `_job_created_ts(realm_root, agent_id: str, job_id: str, jc: dict)`

When the job came into being, to the minute where we can tell.

### `_health_swatch(label: str, size: int=10, cls: str='')`

One status, at legend size. The single definition of what a status LOOKS like when it isn't a day in a strip — used by the legend and by the status filter's dropdown, which had its own flat-colour table and so was still showing the palette from two revisions ago.

### `_filter_dropdown(fid: str, default_label: str, options, width: str='', onpick: str='mcJobsFilter')`

A custom dropdown matching the realm switcher: a pill <summary> + a <details> menu. options: list of (value, label, status|"") — a status renders the legend's own swatch next to the option, and the same swatch next to the summary once selected. `width` fixes the control's width so it doesn't resize when a shorter option is chosen (the label ellipsizes instead). `onpick` is the JS function (by name) called after a selection — so the same dropdown drives different lists.

### `_health_legend_chips(exclude=())`

The shared status swatches (Jobs list legend + Job-calendar widget). Each swatch uses the same styling as the health squares — including the faint, border-less 'Not scheduled' fill. `exclude` drops states that don't apply to a given view (e.g. 'Not scheduled' on a calendar, which shows occurrences per day, not per job).

### `_health_square(label: str, tooltip: str, size: int=11, margin: bool=True)`

One day. Missed is a circled ✕ glyph rather than a shade of grey.

### `_job_health7(jruns, cadence, now, running: bool=False, since: str='', back: int=_WEEK_BACK, fwd: int=_WEEK_FWD)`

Per-day health for one job across a window, oldest→newest, schedule-aware: (weekday_full, 'DD Mon', status_label, is_weekend).

### `_sysjob_health7(runs, now, enabled: bool=True, back: int=_WEEK_BACK, fwd: int=_WEEK_FWD)`

The same week strip, for a job that runs on an INTERVAL rather than at a time of day.

### `_week_filter_bucket(week, back: int=_WEEK_BACK, days: int=_FILTER_BACK_DAYS)`

The status bucket the filters should match, read from the week strip the row already draws.

### `_coord_mark(size: int=15, tip: bool=False)`

The coordinator's laurel, for beside an agent's name.

### `_health7_header(today)`

The day-initials over the health squares, today marked so the split between what happened and what is coming is visible without counting.

### `_status_legend()`

—

### `_health_styles_js()`

The status styles and phrasings, handed to the browser.

### `_agent_health7(realm_root, a, now, back: int=6, fwd: int=0)`

The agent's week: per day, the worst status across every job it owns.

### `_agent_week_strip(realm_root, a, now, size: int=11, back: int=6, fwd: int=0)`

The rendered strip — squares only; the caller decides what to label it with.

### `_health_tip(day, dt, label, wknd, no_jobs: bool=False)`

'Friday 18 Sep · Job scheduled'. The bare adjective read as a property of the date.
