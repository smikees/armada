# `armada/scheduler.py`

Local scheduler (SPEC §8/§12) — the missing heart: fire jobs on their cadence.

ARMADA owns scheduling itself (no OS cron required), so a realm is self-contained and portable.
A job declares a `schedule` string; the scheduler decides when it's due, checks today's reports,
durably claims today's attempt before dispatch, and fires it through the runner
(command or agent). Timezone and grace window come from realm.json, so a job
missed by a reboot still fires within the configured grace window.

Two run modes (CLI):
  * daemon  — loop forever, tick every --interval seconds (the "runs on its own" experience).
  * --once  — a single pass: fire everything due right now, then exit (drive from Task Scheduler,
              or use in tests). Both share the same due-logic, so behaviour is identical.

Schedule grammar (deliberately small + human):
    "manual"                 never auto-fires
    "daily 14:00"            every day at 14:00
    "mon-fri 09:30"          weekdays
    "mon,wed,fri 08:00"      a day list
    "sat 09:00"              a single day
    "mon-sun 00:00"          explicit all-week
    "0 8 * * sat#1"         first Saturday of each month (Armada cron extension)
Days: mon tue wed thu fri sat sun · ranges (mon-fri) · lists (mon,wed) · daily/everyday = all 7.

### `_cron_field(field: str, lo: int, hi: int, names: dict | None=None)`

Expand one cron field (*, a, a-b, a-b/n, */n, lists) into the set of values it matches.

### `is_cron(s: str)`

—

### `_nth_weekday(field: str)`

Armada's ``weekday#occurrence`` extension, e.g. ``sat#1`` for first Saturday.

### `_weekday_matches(field: str, day: 'datetime.date')`

—

### `cron_match(expr: str, dt: datetime.datetime)`

Standard 5-field cron match (min hour dom month dow), Vixie DOM/DOW OR-semantics.

### `cron_dow_days(field: str)`

The set of weekdays a cron day-of-week field covers (Sun=0 … Sat=6), or an empty set if it can't be read. Exposed so callers can reason about how often a schedule fires rather than comparing its spelling: '1-5', '1,2,3,4,5' and 'mon-fri' are one schedule written three ways.

### `_cron_parse(expr: str)`

Parse a 5-field cron once (cached): -> (mins, hours, doms, months, dow_field, dom_star, dow_star).

### `cron_day_times(expr: str, day: 'datetime.date')`

The (hour, minute) fire times of `expr` on `day` — O(hours×minutes), not a 1440-min scan. Returns [] if the day doesn't match. Used to project a calendar cheaply.

### `_read(p: Path)`

—

### `_load_json(p: Path)`

—

### `parse_days(spec: str)`

—

### `parse_schedule(sched: str)`

-> (weekday_set, hour, minute) or None for manual/unparseable.

### class `TimezoneError`

A configured realm clock must never silently become the machine clock.


### `_tz(realm_cfg: dict)`

—

### `now_in(realm_cfg: dict)`

The current time in the realm's own timezone.

### `iter_jobs(realm_root: Path)`

Yield (agent_id, job_id, job_dict) for every job in a native realm.

### `ran_today(realm_root: Path, agent_id: str, job_id: str, day_iso: str, not_before: datetime.datetime | None=None)`

—

### `due_now(job: dict, now: datetime.datetime, grace_min: int)`

—

### `_due_time(job: dict, now: datetime.datetime, grace_min: int)`

Most recent due fire time. Catch-up claims belong to its day, even after midnight.

### `_first_fire(job, fire)`

Keep the once-per-scheduled-day contract for cadences with multiple daily fires.

### `tick(realm_root, engine: str='auto', grace_min: Optional[int]=None, at: Optional[datetime.datetime]=None, dry_run: bool=False, *, _lease: _state.Lease | None=None)`

One pass, with at most one automatic attempt per job and realm-local day.

### `_adopt_new_realms(rescan, owned: dict, others: list)`

Take on realms registered since the daemon started (created or added in the app while it was running). Without this, a new realm's jobs never fired until the scheduler was restarted — and the scheduler is the thing nobody restarts. A realm another live process already owns is left to it.

### `_reconcile_leases(rescan, owned, others, *, primary=None, listener_stop=None)`

Drop idle locks after archive/removal or a cooperative deletion request.

### `run_daemon(realm_root, engine: str='auto', interval: int=60, grace_min: Optional[int]=None, also: Optional[list]=None, rescan=None, app_owner: int=0)`

Fire due jobs until stopped. `also` names further realms to tick in the same pass.

### `_note_running(on: bool)`

—

### `_update_wanted()`

Between passes: should this process restart onto new code (5.4)? Only ever for an installed copy; a development checkout answers no without looking further.
