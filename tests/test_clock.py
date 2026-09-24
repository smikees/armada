"""The render path asks one place what time it is, and a test can pin it.

Why this exists: the golden snapshots carry today in them — weekday letters, dates, and which
squares in a job's week strip read Scheduled versus Missed. That last one no amount of
string-scrubbing can normalise, so the suite went red every morning and the remedy each time was
to regold, which silently accepts whatever the page has started saying. A snapshot needs a time.
"""
import datetime
import json

import pytest

from armada import clock, reader, scheduler
from armada.webui import realmpages as R


@pytest.fixture
def realm(tmp_path):
    root = tmp_path / "realm"
    ad = root / "agents" / "warren"
    (ad / "jobs").mkdir(parents=True)
    (root / "realm.json").write_text(json.dumps({"name": "Cabinet"}), encoding="utf-8")
    (ad / "agent.json").write_text(json.dumps({"id": "warren", "display": "Warren"}),
                                   encoding="utf-8")
    (ad / "jobs" / "daily.json").write_text(json.dumps(
        {"id": "daily", "name": "Daily", "cron": "0 9 * * *", "prompt": "p",
         "created": "2026-01-01T00:00:00+00:00"}), encoding="utf-8")
    return root


def test_unfrozen_is_the_real_clock():
    before = datetime.datetime.now().astimezone()
    n = clock.now()
    assert abs((n - before).total_seconds()) < 5
    assert n.tzinfo is not None, "schedule code compares against this; it has to be aware"


def test_freezing_pins_now_and_today():
    with clock.frozen("2026-09-19T20:12:00"):
        assert clock.now().isoformat()[:19] == "2026-09-19T20:12:00"
        assert clock.today() == datetime.date(2026, 9, 19)
    assert clock.today() == datetime.date.today()


def test_a_bare_date_freezes_to_midday():
    """Clear of both ends of the day, so a frozen render doesn't sit on a boundary."""
    with clock.frozen(datetime.date(2026, 9, 19)):
        assert clock.now().hour == 12


def test_the_context_manager_restores_what_it_found():
    with clock.frozen("2026-01-01T00:00:00"):
        with clock.frozen("2026-06-06T06:06:06"):
            assert clock.today() == datetime.date(2026, 6, 6)
        assert clock.today() == datetime.date(2026, 1, 1)
    assert clock.today() == datetime.date.today()


def test_the_realm_clock_honours_the_freeze(realm):
    """The Jobs page takes its week from scheduler.now_in, not from clock directly — so that had
    to route through the seam too, or the one page most full of dates stayed unfrozen."""
    cfg = {"timezone": "Europe/Madrid"}
    with clock.frozen("2026-09-19T20:12:00"):
        assert scheduler.now_in(cfg).date() == datetime.date(2026, 9, 19)
        assert scheduler.now_in({}).date() == datetime.date(2026, 9, 19)


def test_a_rendered_page_moves_with_the_frozen_clock(realm):
    """The property the goldens depend on: same fixture, same code, different day, different page
    — and therefore, at a fixed day, the same page forever."""
    model = reader.read(str(realm))
    with clock.frozen("2026-09-19T20:12:00"):
        sat = R._realm_jobs(model, realm, clock.today())
    with clock.frozen("2026-11-11T20:12:00"):
        nov = R._realm_jobs(model, realm, clock.today())
    assert "19 Sep" in sat and "19 Sep" not in nov
    assert "11 Nov" in nov


def test_the_golden_run_pins_a_specific_instant():
    """If this constant moves, the whole golden set has to be regolded — deliberately, not by
    the calendar doing it for us."""
    from tests import golden_support as g
    assert g.GOLDEN_NOW == "2026-09-19T20:12:00"
    with clock.frozen(g.GOLDEN_NOW):
        assert clock.now().strftime("%A") == "Saturday"
