"""Jobs-section filter buckets: cadence + last-run status classification."""
from armada import webui


def test_cadence_bucket():
    b = webui._cadence_bucket
    assert b("manual") == "other"
    assert b("") == "other"
    assert b("0 9 * * *") == "daily"        # every day 09:00
    assert b("0 7 * * 1-5") == "daily"      # weekdays
    assert b("30 16 * * 1") == "weekly"     # Mondays
    assert b("0 8 * * 6") == "weekly"       # Saturdays
    assert b("0 9 1 * *") == "monthly"      # 1st of the month
    assert b("0 9 15 * *") == "monthly"
    assert b("0 9 1 1,4,7,10 *") == "quarterly"  # quarter starts
    assert b("not-a-cron") == "other"


def test_job_health7_scheduled_vs_missed():
    """The week is centred on today: three days back, today, three forward (so 6-12 Sep here)."""
    import datetime as dt
    tz = dt.timezone.utc
    now = dt.datetime(2026, 9, 9, 14, 0, tzinfo=tz)   # Wednesday 14:00 (before the 16:00 fire)
    cadence = "0 16 * * 1-5"                           # weekdays at 16:00
    jruns = [{"task": "j", "ts": "2026-09-08T16:00:05", "status": "ok"}]     # Tue: ran ok
    labels = {dt_lbl: status for _day, dt_lbl, status, _w in webui._job_health7(jruns, cadence, now)}
    assert sorted(labels) == ["06 Sep", "07 Sep", "08 Sep", "09 Sep", "10 Sep", "11 Sep", "12 Sep"]
    assert labels["06 Sep"] == "Not scheduled"  # Sunday — weekdays cron doesn't fire
    assert labels["07 Sep"] == "Missed"         # Monday, was due, no run
    assert labels["08 Sep"] == "Success"        # recorded ok
    assert labels["09 Sep"] == "Scheduled"      # today, weekday, 16:00 not yet reached
    assert labels["10 Sep"] == "Scheduled"      # Thursday ahead — due, hasn't happened
    assert labels["11 Sep"] == "Scheduled"      # Friday ahead
    assert labels["12 Sep"] == "Not scheduled"  # Saturday ahead — cron doesn't fire


def test_job_health7_never_marks_a_future_day_missed():
    """A day that has not happened cannot have been missed — the mistake you make by widening the
    window without revisiting the Scheduled/Missed branch."""
    import datetime as dt
    now = dt.datetime(2026, 9, 9, 14, 0, tzinfo=dt.timezone.utc)
    days = webui._job_health7([], "0 16 * * 1-5", now)
    assert [s for _d, _dt, s, _w in days[4:]].count("Missed") == 0


def test_job_health7_running_today():
    import datetime as dt
    now = dt.datetime(2026, 9, 9, 14, 0, tzinfo=dt.timezone.utc)
    days = webui._job_health7([], "0 16 * * 1-5", now, running=True)
    assert days[3][2] == "Running"              # today is the middle cell now, not the last
    assert days[3][1] == "09 Sep"



def test_job_health7_manual_never_scheduled():
    import datetime as dt
    now = dt.datetime(2026, 9, 9, 14, 0, tzinfo=dt.timezone.utc)
    days = webui._job_health7([], "manual", now)
    assert all(status == "Not scheduled" for _d, _dt, status, _w in days)


def test_status_bucket():
    s = webui._status_bucket
    assert s("ok") == "success"
    assert s("quiet") == "success"
    assert s("warn") == "warning"
    assert s("warning") == "warning"
    assert s("issues") == "warning"
    assert s("error") == "failed"
    assert s("") == "none"
    assert s(None) == "none"
    assert s("whatever") == "none"


# --- the filter reads the strip ------------------------------------------------------------------
#
# The bug: the row's filter bucket came from `last_status`, the outcome of the most recent recorded
# run. Four jobs that had never run all had no last status, all fell through to the same default,
# and all matched "Missed" — while the strip beside them showed two as missed and two as never
# having been due. Filtering on Missed returned the whole list.

def _week(*labels):
    """A strip, oldest→newest, of just the labels — the rest of the tuple doesn't matter here."""
    return [("Day", f"{i:02d} Sep", lab, False) for i, lab in enumerate(labels, start=1)]


def test_a_job_that_was_due_and_did_not_run_is_missed():
    from armada.webui import agentbits as AB
    wk = _week("Not scheduled", "Not scheduled", "Missed", "Not scheduled",
               "Scheduled", "Scheduled", "Not scheduled")
    assert AB._week_filter_bucket(wk) == "none"


def test_a_job_that_was_never_due_has_no_status_at_all():
    """Not "Missed" — the distinction the old default collapsed. It matches no status filter."""
    from armada.webui import agentbits as AB
    wk = _week("Not scheduled", "Not scheduled", "Not scheduled", "Not scheduled",
               "Scheduled", "Scheduled", "Scheduled")
    assert AB._week_filter_bucket(wk) == ""


def test_the_most_recent_outcome_wins():
    from armada.webui import agentbits as AB
    wk = _week("Failed", "Warning", "Success", "Not scheduled", "Scheduled", "Scheduled", "Scheduled")
    assert AB._week_filter_bucket(wk) == "success"


def test_scheduled_days_do_not_hide_the_outcome_underneath():
    """Today reading "Scheduled" (due again later) must not erase yesterday's failure."""
    from armada.webui import agentbits as AB
    wk = _week("Not scheduled", "Not scheduled", "Failed", "Scheduled", "Scheduled", "Scheduled", "Scheduled")
    assert AB._week_filter_bucket(wk) == "failed"


def test_the_future_half_of_the_strip_is_ignored():
    """The strip is a centred week. "Show me the failed jobs" asks about what has happened."""
    from armada.webui import agentbits as AB
    wk = _week("Not scheduled", "Not scheduled", "Not scheduled", "Not scheduled",
               "Failed", "Failed", "Failed")           # all three in the future
    assert AB._week_filter_bucket(wk) == ""


def test_nothing_older_than_four_days_counts():
    """Today plus the three before it. Checked on a longer strip, since the standard one is only
    three days deep and every past day on it is inside the window by construction."""
    from armada.webui import agentbits as AB
    assert AB._FILTER_BACK_DAYS == 4
    # back=5: indices 0-5 are the past, 5 is today.
    older = _week("Failed", "Not scheduled", "Not scheduled", "Not scheduled",
                  "Not scheduled", "Not scheduled", "Scheduled")
    assert AB._week_filter_bucket(older, back=5) == "", "a failure 5 days ago is out of the window"
    inside = _week("Not scheduled", "Not scheduled", "Failed", "Not scheduled",
                   "Not scheduled", "Not scheduled", "Scheduled")
    assert AB._week_filter_bucket(inside, back=5) == "failed", "3 days ago is inside it"


def test_a_running_job_reads_as_running():
    from armada.webui import agentbits as AB
    wk = _week("Success", "Success", "Success", "Running", "Scheduled", "Scheduled", "Scheduled")
    assert AB._week_filter_bucket(wk) == "running"
