# `armada/webui/_core.py`

ARMADA web UI — server-rendered screens matching the approved design handoff.

Reproduces the design's DOM (Industry design-system + ARMADA brand overrides, served from
webui/static/) from LIVE realm data, so the app looks like the mockups but shows the real realm.
This module renders the **realm overview dashboard** (design #2b): title bar, top nav with realm
switcher + tabs + user sections, KPI header, and the Register / From-the-Hand / Attention / Today
widgets. Other screens (agent frame, job detail) are added here as they're built.

### `_tz_options(selected: str)`

<option>s for the timezone select: 'System' first (value ''), then zones west→east. If the saved timezone isn't in the curated list, it's added so it stays selectable.

### `_user(realm_root)`

The owner's settings (source of truth in realm.json 'user'), falling back to the top-level owner/timezone for older realms.

### `_dot(status: str)`

—

### `_ver_tuple(label: str)`

Version part of a pretty label as a sortable tuple: 'Opus 4.8'→(4,8), 'Opus 5'→(5,), 'Opus'→().

### `_model_color_map(labels)`

label → colour by token-consumption index on the shared gradient (light = low, dark = high). All versions of a family share a price tier, so they share a colour; non-Claude labels fall back.

### `_htok(n: int)`

—

### `_totals_30d(realm, realm_root, today: datetime.date)`

Epoch-aware rolling-30-day (today-29 … today) token + api-eq totals from run telemetry. THE single source for both the Overview header KPIs (server-rendered) and the Usage endpoint's total_30d/usd_30d, so the header value doesn't change when usage.js refreshes it on load.

### `_usage_stats(realm, realm_root: Path, today: datetime.date)`

Aggregate ARMADA's own run-report telemetry over the last 30 days → overall total, per-agent totals (first), and per-model totals. Real data we log ourselves.

### `_usage_data(realm, realm_root, mode: str, window: str, by: str='agents')`

Windowed usage from run telemetry, for the Usage widget's line/graph modes. line: per-agent + per-model totals over a window (today/7d/mtd). graph: a stacked time series (weekly = last 7 days; monthly = last 12 months), split per agent (default) or per model.

### `_jc_norm(st)`

—

### `_jobcal_events(realm, realm_root, d_from, d_to)`

Job occurrences in [d_from, d_to]: projected from each job's schedule, with past slots resolved to their actual run status (success/failed/warn/missed); manual/ad-hoc runs added too.

### `_sysjobcal_events(realm_root, d_from, d_to)`

System-job occurrences in [d_from, d_to], in the same shape as _jobcal_events.

### `_from_hand(realm, realm_root)`

—

### `_attention(realm, realm_root, today)`

—

### `_today(realm, realm_root, today)`

—

### `_agent_memory_realm(realm_root: Path)`

—

### `_settings_realm(realm, realm_root)`

—

### `_user_avatar_modal()`

—

### `_widget_section_title(realm, wid: str)`

A default nav title for a widget promoted to a section.

### `_render_widget_section(realm, realm_root, name, wid, dark=False)`

Render a dashboard widget (register / usage / jobcal / a thread) as a full standalone page. The widget's own header becomes the page header; grip/⋮ chrome is dropped (section mode).

### `_load_dashboard(realm_root)`

Dashboard layout/state, persisted per realm (portable) in dashboard.json. Shape: {single:{id:bool}, order:[id], spans:{id:int}, heights:{id:px}, threads:[{agent,thread,...}]}.
