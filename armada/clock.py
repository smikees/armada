"""One place the app asks what time it is.

Every screen that draws a week strip, a next-run time or a "today" marker reads the clock, and
until now each did so by calling `datetime.now()` where it stood. That is fine in production and
ruinous for the golden page tests: the snapshots carry weekday letters, dates and — the part no
amount of string-scrubbing can normalise — which squares in a job's week read Scheduled versus
Missed. Those change by themselves at midnight, so the suite went red every morning and the fix
each time was to regold, which quietly accepts whatever the page now says.

So the render path asks here instead, and a test can freeze it. The seam is deliberately tiny:
two functions and a context manager, no timezone cleverness, no injected clock objects threaded
through call signatures.

`now()` is timezone-aware (local), because that is what the schedule code compares against;
`today()` is its date. A frozen value is used exactly as given, so a test picks a date whose week
it wants to assert and gets the same page every day of the year.
"""
from __future__ import annotations

import contextlib
import datetime

_frozen: datetime.datetime | None = None


def now() -> datetime.datetime:
    """The current local time, timezone-aware — or whatever `freeze` was given."""
    if _frozen is not None:
        return _frozen
    return datetime.datetime.now().astimezone()


def today() -> datetime.date:
    return now().date()


def freeze(when) -> None:
    """Pin the clock. `when` may be a datetime, a date, or an ISO string; None unfreezes.

    Naive values are given the local offset, so a frozen clock compares against schedule times
    the same way a real one does — a naive/aware mix raises rather than misordering, and finding
    that out inside a page render is a poor place to learn it.
    """
    global _frozen
    if when is None:
        _frozen = None
        return
    if isinstance(when, str):
        when = datetime.datetime.fromisoformat(when)
    if isinstance(when, datetime.datetime):
        dt = when
    else:                                   # a plain date — midday, to sit clear of both edges
        dt = datetime.datetime.combine(when, datetime.time(12, 0))
    if dt.tzinfo is None:
        dt = dt.astimezone()
    _frozen = dt


@contextlib.contextmanager
def frozen(when):
    """`with clock.frozen("2026-09-19T20:12:00"): ...` — restores the previous setting after."""
    prev = _frozen
    freeze(when)
    try:
        yield
    finally:
        globals().__setitem__("_frozen", prev)
