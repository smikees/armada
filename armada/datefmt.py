"""Dates and times, one way everywhere (DESIGN_SYSTEM §9a, UI audit C2).

The month is always a word and times are 24-hour: `9/24` and `24/9` read differently to different
owners, `24 Sep` doesn't. Six formats had grown up across the app (`Thu 9/24, 22:30`, `17/09/26`,
`19-09-26 14:40`, `21-09-26`, `01 Oct 2027`, `Thu 24th`); these four replace them. The names are
fixed English rather than strftime's %b/%a, which follow the machine's locale on Windows and would
turn "Sep" into "sept." on a Spanish install. `static/js/sysjobs.js` mirrors `moment()`.
"""
from __future__ import annotations

import datetime as _dt

MON = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
DOW = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _today(today=None) -> _dt.date:
    from . import clock                      # the app's clock seam (frozen in the golden suite)
    return today or clock.today()


def moment(t: _dt.datetime) -> str:
    """A moment near now — next run, last run: `Thu 24 Sep, 22:30`."""
    return f"{DOW[t.weekday()]} {t.day} {MON[t.month - 1]}, {t:%H:%M}"


def day(d, today=None, year: bool = False) -> str:
    """A date: `24 Sep` this year, `1 Oct 2027` otherwise — or always with the year when it
    matters (an ETA, an appointment): `year=True`."""
    if isinstance(d, _dt.datetime):
        d = d.date()
    s = f"{d.day} {MON[d.month - 1]}"
    return f"{s} {d.year}" if year or d.year != _today(today).year else s


def stamp(t: _dt.datetime, today=None) -> str:
    """A timestamp in a list (artefacts, run history): `19 Sep, 14:40`; the year only if it isn't
    this one: `19 Sep 2025, 14:40`."""
    return f"{day(t, today)}, {t:%H:%M}"


def parse(s) -> _dt.datetime | None:
    """ISO text (with or without time or `Z`) → datetime, or None."""
    s = str(s or "").strip()
    if not s:
        return None
    try:
        return _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        try:
            d = _dt.date.fromisoformat(s[:10])
            return _dt.datetime(d.year, d.month, d.day)
        except ValueError:
            return None
