# `armada/webui/schedfmt.py`

Schedule / status / date-format helpers (carved from _core.py in Phase 3).

A pure lower layer: cron/cadence labelling, next-run computation, status bucketing and
timestamp formatting. Depends only on datetime, the scheduler (lazy) and the status module —
never on _core rendering helpers — so _core imports these names back with no import cycle.

### `_humanize(cadence: str)`

Turn a cron/schedule string into a short friendly label (design style: 'weekdays 14:00').

### `_cadence_bucket(cadence: str)`

Classify a job's schedule into a coarse filter bucket: daily · weekly · monthly · quarterly · other (manual / anything else).

### `_sysjob_cadence_bucket(mins: int)`

Map a system job's interval onto the same coarse buckets the Cadence filter uses, so one filter bar works for both kinds of job.

### `_status_bucket(last_status: str)`

Map a run status to a coarse filter bucket: success · running · warning · failed · none.

### `_job_next_dt(cadence, now: datetime.datetime | None=None)`

The next scheduled fire for ONE cadence, or None for manual/ad-hoc.

### `_next_run_dt(agent, now: datetime.datetime | None=None)`

The earliest upcoming scheduled fire across all the agent's jobs (None if none upcoming).

### `_ordinal(n: int)`

1→1st, 2→2nd, 3→3rd, 4→4th, 11→11th, 21→21st, …

### `_next_hint(agent)`

The next run as 'DDD Nth HH:MM' (e.g. 'Sat 12th 05:05'); '—' when nothing is scheduled.

### `_fmt_ts(ts)`

Render a run timestamp as DD-MM-YY HH:MM (falls back to the raw string).
