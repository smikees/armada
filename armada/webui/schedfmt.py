"""Schedule / status / date-format helpers (carved from _core.py in Phase 3).

A pure lower layer: cron/cadence labelling, next-run computation, status bucketing and
timestamp formatting. Depends only on datetime, the scheduler (lazy) and the status module —
never on _core rendering helpers — so _core imports these names back with no import cycle.
"""
from __future__ import annotations
import datetime
from .. import clock
from .. import status


_DOW_NAME = {0: "Sun", 1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat"}


def _humanize(cadence: str) -> str:
    """Turn a cron/schedule string into a short friendly label (design style: 'weekdays 14:00')."""
    if not cadence or cadence == "manual":
        return "on demand"
    from .. import scheduler as S
    if S.is_cron(cadence):
        f = cadence.split()
        try:
            mm, hh = int(f[0]), int(f[1])      # cron order is: minute hour ...
            time = f"{hh:02d}:{mm:02d}"
        except ValueError:
            return cadence
        dom, mon, dow = f[2], f[3], f[0 + 4]
        if dom == "*" and dow == "*":
            day = "daily"
        elif dow == "1-5":
            day = "weekdays"
        elif dow in ("0", "7"):
            day = "Sun"
        elif dow == "6" and dom == "*":
            day = "Sat"
        elif dow == "6" and dom == "1-7":
            day = "1st Sat"
        elif "," in dow:
            day = ",".join(_DOW_NAME.get(int(x) % 7, x) for x in dow.split(","))
        elif "-" in dow:
            a, b = dow.split("-", 1)
            day = f"{_DOW_NAME.get(int(a) % 7, a)}-{_DOW_NAME.get(int(b) % 7, b)}"
        elif dow != "*":
            try:
                day = _DOW_NAME.get(int(dow) % 7, dow)
            except ValueError:
                day = dow
        elif dom == "1" and mon != "*":
            day = "quarterly"
        elif dom == "1":
            day = "1st"
        else:
            day = f"d{dom}"
        return f"{day} {time}"
    return cadence[:14]


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
    """The next run as 'DDD Nth HH:MM' (e.g. 'Sat 12th 05:05'); '—' when nothing is scheduled."""
    dt = _next_run_dt(agent)
    return f"{dt:%a} {_ordinal(dt.day)} {dt:%H:%M}" if dt else "—"


def _fmt_ts(ts) -> str:
    """Render a run timestamp as DD-MM-YY HH:MM (falls back to the raw string)."""
    s = str(ts or "")
    if not s:
        return ""
    try:
        dt = datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.strftime("%d-%m-%y %H:%M")
    except ValueError:
        return s[:16]
