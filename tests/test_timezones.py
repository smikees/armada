"""Named zones work without a machine timezone database, including both DST transitions."""
import datetime as dt
import json
from zoneinfo import ZoneInfo, reset_tzpath

import pytest

from armada import clock, scheduler


@pytest.fixture(autouse=True)
def packaged_timezone_source():
    import zoneinfo
    old = zoneinfo.TZPATH
    reset_tzpath(())
    ZoneInfo.clear_cache()
    try:
        yield
    finally:
        reset_tzpath(old)
        ZoneInfo.clear_cache()


@pytest.mark.parametrize("utc,zone,expected", [
    ("2026-10-03T12:00:00+00:00", "America/New_York", "2026-10-03T08:00:00-04:00"),
    ("2026-10-03T23:00:00+00:00", "Asia/Tokyo", "2026-10-04T08:00:00+09:00"),
    ("2026-03-08T06:59:00+00:00", "America/New_York", "2026-03-08T01:59:00-05:00"),
    ("2026-03-08T07:00:00+00:00", "America/New_York", "2026-03-08T03:00:00-04:00"),
    ("2026-11-01T05:30:00+00:00", "America/New_York", "2026-11-01T01:30:00-04:00"),
    ("2026-11-01T06:30:00+00:00", "America/New_York", "2026-11-01T01:30:00-05:00"),
])
def test_realm_clock_converts_from_absolute_instant(monkeypatch, utc, zone, expected):
    monkeypatch.setattr(clock, "now", lambda: dt.datetime.fromisoformat(utc))
    assert scheduler.now_in({"timezone": zone}).isoformat() == expected


def test_invalid_zone_holds_work_before_upkeep_or_dispatch(tmp_path, monkeypatch):
    (tmp_path / "realm.json").write_text(json.dumps({"schema_version": 1, "timezone": "Mars/Olympus"}))
    from armada import realmformat, sysjobs
    monkeypatch.setattr(realmformat, "ensure", lambda *_: None)
    monkeypatch.setattr(sysjobs, "run_due", lambda *_: pytest.fail("must not run with the wrong clock"))
    result = scheduler.tick(tmp_path)
    assert result[0]["job"] == "timezone-hold" and result[0]["status"] == "held"
    assert "Mars/Olympus" in result[0]["detail"]


def test_missing_database_never_falls_back_to_local(monkeypatch):
    import zoneinfo
    def missing(_):
        raise zoneinfo.ZoneInfoNotFoundError("unavailable")
    monkeypatch.setattr(zoneinfo, "ZoneInfo", missing)
    with pytest.raises(scheduler.TimezoneError, match="repair the installation"):
        scheduler.now_in({"timezone": "Europe/Madrid"})


@pytest.mark.parametrize("config", [{}, {"timezone": ""}, {"timezone": "local"}])
def test_unconfigured_zone_intentionally_uses_machine_clock(monkeypatch, config):
    instant = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(clock, "now", lambda: instant)
    assert scheduler.now_in(config) is instant


@pytest.mark.parametrize('zone,schedule,instants,expected', [
    ('Asia/Tokyo', 'sun 08:00', ['2026-10-03T22:59:00+00:00', '2026-10-03T23:00:00+00:00'], [0,1]),
    ('America/New_York', 'daily 02:30', ['2026-03-08T06:59:00+00:00', '2026-03-08T07:00:00+00:00'], [0,1]),
    ('America/New_York', 'daily 01:30', ['2026-11-01T05:30:00+00:00', '2026-11-01T06:30:00+00:00'], [1,0]),
])
def test_schedule_uses_realm_day_catches_up_gap_and_does_not_repeat_fold(
        tmp_path, monkeypatch, zone, schedule, instants, expected):
    from armada import preflight, realmformat, runner, sysjobs
    (tmp_path/'realm.json').write_text(json.dumps({'schema_version':realmformat.CURRENT,'timezone':zone}))
    jobs = tmp_path/'agents/a/jobs'
    jobs.mkdir(parents=True)
    (jobs/'daily.json').write_text(json.dumps({'id':'daily','schedule':schedule}))
    monkeypatch.setattr(preflight,'hold_reason',lambda *_:'')
    monkeypatch.setattr(sysjobs,'run_due',lambda *_:[])
    monkeypatch.setattr(runner,'run_job',lambda *a,**kw:{'status':'ok'})
    for instant, count in zip(instants, expected):
        monkeypatch.setattr(clock,'now',lambda:dt.datetime.fromisoformat(instant))
        fired = scheduler.tick(tmp_path,grace_min=60)
        assert len(fired) == count
        assert all(item['status']=='ok' for item in fired)
