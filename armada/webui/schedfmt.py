"""Schedule / status / date-format helpers (carved from _core.py in Phase 3).

A pure lower layer: cron/cadence labelling, next-run computation, status bucketing and
timestamp formatting. Depends only on datetime, the scheduler (lazy) and the status module —
never on _core rendering helpers — so _core imports these names back with no import cycle.
"""
from __future__ import annotations
from .. import datefmt
import datetime
from .. import clock
from .. import status


_DOW_NAME = {0: "Sun", 1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat"}


def _ranges(values, label=str):
    """Compact sorted values into readable singletons/ranges, never cron syntax."""
    values = sorted(values)
    groups = []
    for value in values:
        if groups and value == groups[-1][-1] + 1:
            groups[-1].append(value)
        else:
            groups.append([value])
    return ", ".join(label(g[0]) if len(g) == 1 else
                     ", ".join(map(label, g)) if len(g) == 2 else
                     label(g[0]) + "–" + label(g[-1]) for g in groups)


def _day_label(days):
    if days == set(range(7)):
        return "daily"
    if days == {1, 2, 3, 4, 5}:
        return "weekdays"
    if days == {0, 6}:
        return "weekends"
    return _ranges({d or 7 for d in days}, lambda d: _DOW_NAME[d % 7])


def _time_label(minutes, hours):
    times = sorted(h * 60 + m for h in hours for m in minutes)
    stamp = lambda t: f"{t // 60:02d}:{t % 60:02d}"
    if len(times) <= 4:
        return ", ".join(map(stamp, times))
    gaps = {b-a for a, b in zip(times, times[1:])}
    if len(gaps) == 1:
        step = gaps.pop()
        interval = ("every minute" if step == 1 else "hourly" if step == 60 else
                    f"every {step // 60} hours" if step % 60 == 0 else f"every {step} min")
        full_day = times[-1] + step == times[0] + 1440
        if full_day and times[0] < step:
            return interval + (f" at :{times[0]:02d}" if 0 < times[0] < 60 else
                               f", from {stamp(times[0])}" if times[0] else "")
        return f"{interval}, {stamp(times[0])}–{stamp(times[-1])}"
    minute_label = "at minutes " + _ranges(minutes)
    if hours == set(range(24)):
        return minute_label + " each hour"
    return minute_label + " during hours " + _ranges(hours, lambda h: f"{h:02d}")


def _humanize(cadence: str) -> str:
    """Describe the scheduler's actual grammar, including steps and DOM/DOW OR."""
    if not cadence or cadence.strip().lower() in ("manual", "none", "on-demand"):
        return "on demand"
    from .. import scheduler as S
    if not S.is_cron(cadence):
        parsed = S.parse_schedule(cadence)
        if parsed:
            days, hour, minute = parsed
            return f"{_day_label({(d+1) % 7 for d in days})} {hour:02d}:{minute:02d}"
        return "Schedule needs review"
    try:
        minutes, hours, doms, months, dow, dom_star, dow_star = S._cron_parse(cadence)
        days = S.cron_dow_days(dow)
        if not all((minutes, hours, doms, months, days)):
            return "Schedule needs review"
        nth = S._nth_weekday(dow)
        weekday = f"{_ordinal(nth[1])} {_DOW_NAME[nth[0]]}" if nth else _day_label(days)
        monthday = _ordinal(next(iter(doms))) if len(doms) == 1 else "days " + _ranges(doms)
        day = ("daily" if dow_star else weekday) if dom_star else (
              monthday if dow_star else monthday + " or " + weekday)
        if months != set(range(1, 13)):
            names = ("", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
            day += " in " + _ranges(months, lambda m: names[m])
        return day + " " + _time_label(minutes, hours)
    except (ValueError, TypeError, IndexError):
        return "Schedule needs review"


def _cadence_bucket(cadence: str) -> str:
    """Classify a job's schedule into a coarse filter bucket:
    daily · weekly · monthly · quarterly · other (manual / anything else)."""
    if not cadence or cadence == "manual":
        return "other"
    from .. import scheduler as S
    if not S.is_cron(cadence):
        return "other"
    f = str(cadence).split()
    if len(f) != 5:
        return "other"
    _minute, _hour, dom, mon, dow = f
    if "#" in dow:
        return "monthly"
    if mon != "*":
        return "quarterly"          # month-constrained cadences (e.g. quarter starts)
    if dom != "*":
        return "monthly"            # a specific day-of-month
    if dow == "*":
        return "daily"              # every day
    # Bucket on how many days the field actually covers, not on how it is spelled. The old test
    # was `dow in ("*", "1-5")`, which meant '1,2,3,4,5' and 'mon-fri' — the same schedule, and
    # the spelling most UIs emit — were filed as weekly, and Mon-Sat ('1-6') sorted as rarer than
    # weekdays despite running one day MORE per week. Five days or more belongs with the dailies.
    days = S.cron_dow_days(dow)
    if not days:
        return "other"              # unreadable field: not a claim we can make
    return "daily" if len(days) >= 5 else "weekly"


def _sysjob_cadence_bucket(mins: int) -> str:
    """Map a system job's interval onto the same coarse buckets the Cadence filter uses, so one
    filter bar works for both kinds of job."""
    if mins <= 0:
        return "other"
    if mins <= 24 * 60:
        return "daily"
    if mins <= 7 * 24 * 60:
        return "weekly"
    if mins <= 31 * 24 * 60:
        return "monthly"
    return "quarterly"


def _status_bucket(last_status: str) -> str:
    """Map a run status to a coarse filter bucket: success · running · warning · failed · none."""
    return {status.SUCCESS: "success", status.QUIET: "success", status.RUNNING: "running",
            status.WARN: "warning", status.FAILED: "failed"}.get(status.normalize(last_status), "none")


_STATUS_FILTERS = [("success", "Success"), ("running", "Running"), ("warning", "Warning"),
                   ("failed", "Failed"), ("none", "Missed")]
_CADENCE_FILTERS = [("daily", "Daily"), ("weekly", "Weekly"), ("monthly", "Monthly"),
                    ("quarterly", "Quarterly"), ("other", "Other")]


def _job_next_dt(cadence, now: datetime.datetime | None = None) -> datetime.datetime | None:
    """The next scheduled fire for ONE cadence, or None for manual/ad-hoc.

    Split out of _next_run_dt so a single job row and the agent header compute "next" the same way
    — the alternative was a second scan that could disagree with the first about the same cron.
    """
    from .. import scheduler as S
    now = now or clock.now().replace(tzinfo=None)
    sched = cadence or "manual"
    cron = isinstance(sched, str) and S.is_cron(sched)
    parsed = None if cron else S.parse_schedule(sched)
    if not cron and not parsed:
        return None                           # manual / ad-hoc — no scheduled next run
    for off in range(0, 400):                 # scan up to ~13 months ahead
        day = (now + datetime.timedelta(days=off)).date()
        if cron:
            occs = S.cron_day_times(sched, day)
        else:
            ds, hh, mm = parsed
            occs = [(hh, mm)] if day.weekday() in ds else []
        hit = next((datetime.datetime(day.year, day.month, day.day, h, m)
                    for h, m in sorted(occs)
                    if datetime.datetime(day.year, day.month, day.day, h, m) > now), None)
        if hit:
            return hit
    return None


def _next_run_dt(agent, now: datetime.datetime | None = None) -> datetime.datetime | None:
    """The earliest upcoming scheduled fire across all the agent's jobs (None if none upcoming)."""
    now = now or clock.now().replace(tzinfo=None)
    hits = [dt for dt in (_job_next_dt(j.cadence, now) for j in getattr(agent, "jobs", [])) if dt]
    return min(hits) if hits else None


def _ordinal(n: int) -> str:
    """1→1st, 2→2nd, 3→3rd, 4→4th, 11→11th, 21→21st, …"""
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def _next_hint(agent) -> str:
    """The next run, `Thu 24 Sep, 05:05` (DESIGN_SYSTEM §9a); '—' when nothing is scheduled."""
    dt = _next_run_dt(agent)
    return datefmt.moment(dt) if dt else "—"


def _fmt_ts(ts) -> str:
    """A run/file timestamp as `19 Sep, 14:40` (year added if not this year; §9a). Falls back to
    the raw string."""
    s = str(ts or "")
    if not s:
        return ""
    dt = datefmt.parse(s)
    return datefmt.stamp(dt) if dt else s[:16]
