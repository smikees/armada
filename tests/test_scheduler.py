"""Scheduler grammar + cron — the heart of unattended running. Pure functions, no I/O."""
import datetime
from armada import scheduler as S


def test_parse_days_ranges_and_lists():
    assert S.parse_days("mon-fri") == {0, 1, 2, 3, 4}
    assert S.parse_days("sat,sun") == {5, 6}
    assert S.parse_days("daily") == {0, 1, 2, 3, 4, 5, 6}
    assert S.parse_days("mon") == {0}


def test_parse_schedule_simple():
    assert S.parse_schedule("mon-fri 14:00") == ({0, 1, 2, 3, 4}, 14, 0)
    assert S.parse_schedule("daily 09:30") == ({0, 1, 2, 3, 4, 5, 6}, 9, 30)


def test_parse_schedule_manual_or_bad_is_none():
    assert S.parse_schedule("manual") is None
    assert S.parse_schedule("") is None
    assert S.parse_schedule("mon-fri 99:99") is None


def test_is_cron_detects_five_field():
    assert S.is_cron("0 8 1-7 * 6")
    assert S.is_cron("0 11 1 1,4,7,10 *")
    assert not S.is_cron("mon-fri 14:00")
    assert not S.is_cron("manual")


def test_cron_match_vixie_dom_dow_or():
    # "0 8 1-7 * 6": Vixie OR-semantics — when BOTH dom (1-7) and dow (Sat) are restricted,
    # it fires at 08:00 when dom in 1..7 OR the day is Saturday.
    expr = "0 8 1-7 * 6"
    assert S.cron_match(expr, datetime.datetime(2026, 9, 5, 8, 0))    # Sat, dom=5  (both)
    assert S.cron_match(expr, datetime.datetime(2026, 9, 12, 8, 0))   # Sat, dom=12 (dow OR)
    assert S.cron_match(expr, datetime.datetime(2026, 9, 3, 8, 0))    # Thu, dom=3  (dom OR)
    assert not S.cron_match(expr, datetime.datetime(2026, 9, 10, 8, 0))  # Thu, dom=10 (neither)
    assert not S.cron_match(expr, datetime.datetime(2026, 9, 5, 8, 1))   # right day, wrong minute


def test_cron_match_quarterly():
    expr = "0 11 1 1,4,7,10 *"   # 11:00 on the 1st of Jan/Apr/Jul/Oct
    assert S.cron_match(expr, datetime.datetime(2026, 4, 1, 11, 0))
    assert not S.cron_match(expr, datetime.datetime(2026, 5, 1, 11, 0))
    assert not S.cron_match(expr, datetime.datetime(2026, 4, 2, 11, 0))


def test_due_now_simple_within_grace():
    now = datetime.datetime(2026, 9, 7, 14, 5)     # Mon 14:05
    job = {"schedule": "mon-fri 14:00"}
    assert S.due_now(job, now, grace_min=30)
    # outside grace
    assert not S.due_now(job, now.replace(hour=15), grace_min=30)
    # wrong weekday (Sat)
    assert not S.due_now(job, datetime.datetime(2026, 9, 5, 14, 5), grace_min=30)


def test_due_now_manual_never():
    assert not S.due_now({"schedule": "manual"}, datetime.datetime(2026, 9, 7, 14, 0), 30)
