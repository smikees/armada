"""The Cadence filter on the Jobs page buckets a schedule as daily/weekly/monthly/quarterly.

The bucket used to be decided by comparing the cron day-of-week field to the literal '1-5', so
identical schedules bucketed differently depending on how they were written, and Mon-Sat sorted
as rarer than Mon-Fri while running more often. A filter that hides the thing you're looking for
is worse than no filter.
"""
from armada import scheduler
from armada.webui.schedfmt import _cadence_bucket as bucket


def test_every_day_is_daily():
    assert bucket("0 9 * * *") == "daily"


def test_weekdays_is_daily_however_it_is_written():
    for dow in ["1-5", "1,2,3,4,5", "mon-fri", "MON-FRI"]:
        assert bucket(f"0 9 * * {dow}") == "daily", dow


def test_six_days_a_week_is_not_rarer_than_five():
    """Mon-Sat runs one day MORE than weekdays; it must not land in a rarer bucket."""
    assert bucket("0 0 * * 1-6") == "daily"


def test_a_few_named_days_is_weekly():
    assert bucket("0 18 * * 1,4") == "weekly"
    assert bucket("0 18 * * 0") == "weekly"
    assert bucket("0 4 * * mon") == "weekly"


def test_day_of_month_is_monthly():
    assert bucket("30 6 1 * *") == "monthly"


def test_month_constrained_is_quarterly():
    assert bucket("0 11 1 1,4,7,10 *") == "quarterly"


def test_manual_and_junk_are_other():
    assert bucket("") == "other"
    assert bucket("manual") == "other"
    assert bucket("not a cron") == "other"
    assert bucket("0 9 * * nonsense") == "other"


def test_bucket_never_invents_a_category():
    allowed = {"daily", "weekly", "monthly", "quarterly", "other"}
    for c in ["0 9 * * *", "0 9 * * 1-5", "0 9 * * 6", "0 9 1 * *", "0 9 1 3 *", "manual", "", "x"]:
        assert bucket(c) in allowed, c


def test_cron_dow_days_reads_the_spellings_the_bucket_relies_on():
    assert scheduler.cron_dow_days("1-5") == {1, 2, 3, 4, 5}
    assert scheduler.cron_dow_days("1,2,3,4,5") == {1, 2, 3, 4, 5}
    assert scheduler.cron_dow_days("mon-fri") == {1, 2, 3, 4, 5}
    assert scheduler.cron_dow_days("1-6") == {1, 2, 3, 4, 5, 6}
    assert scheduler.cron_dow_days("0") == {0}
    assert scheduler.cron_dow_days("7") == {0}          # cron allows 7 for Sunday
    assert scheduler.cron_dow_days("*") == {0, 1, 2, 3, 4, 5, 6}
    assert scheduler.cron_dow_days("garbage") == set()


def test_bucket_agrees_with_how_often_the_job_actually_fires():
    """Cross-check against the real matcher: a 'daily' bucket should fire on >=5 days a week."""
    import datetime as dt
    for expr in ["0 9 * * *", "0 9 * * 1-5", "0 0 * * 1-6", "0 18 * * 1,4"]:
        week = dt.datetime(2026, 9, 14, 0, 0)        # a Monday
        hits = 0
        for d in range(7):
            day = week + dt.timedelta(days=d)
            if any(scheduler.cron_match(expr, day.replace(hour=h, minute=m))
                   for h in range(24) for m in (0, 18, 30)):
                hits += 1
        expected = "daily" if hits >= 5 else "weekly"
        assert bucket(expr) == expected, f"{expr}: fires {hits} days/week, bucketed {bucket(expr)}"
