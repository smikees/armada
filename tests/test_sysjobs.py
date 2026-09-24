"""System jobs: the app's own upkeep, on a clock.

Two properties matter most. Cost is declared rather than implied — a system job must never quietly
become one that spends your subscription. And nothing fails silently: background work that dies
unnoticed is the exact failure mode this app has already been bitten by.
"""
import datetime as dt
import json
from pathlib import Path

import pytest

from armada import sysjobs


@pytest.fixture
def realm(tmp_path):
    (tmp_path / "realm.json").write_text(json.dumps({"name": "t"}), encoding="utf-8")
    return tmp_path


def test_definitions_live_in_the_package_not_the_realm(realm):
    """'Can't be edited or deleted' is structural: there's nothing in the realm to change."""
    assert sysjobs.JOBS and all(callable(j["run"]) for j in sysjobs.JOBS)
    assert not list(realm.glob("system_jobs/*"))


def test_every_job_declares_a_known_cost():
    for j in sysjobs.JOBS:
        assert j["cost"] in (sysjobs.FREE, sysjobs.QUOTA), f"{j['id']} has an undeclared cost"
        assert sysjobs.interval_minutes(j) > 0, f"{j['id']} has no cadence"
        assert j["name"] and j["description"]


def test_job_ids_are_unique():
    ids = [j["id"] for j in sysjobs.JOBS]
    assert len(ids) == len(set(ids))


def test_a_never_run_job_is_due(realm):
    assert sysjobs.due(realm, "model-catalog") is True


def test_running_records_outcome_and_clears_due(realm):
    r = sysjobs.run_one(realm, "prune-history")
    assert r["ok"] is True
    s = next(j for j in sysjobs.status(realm) if j["id"] == "prune-history")
    assert s["status"] == "ok" and s["last_run"] and s["due_now"] is False and s["next_due"]


def test_due_again_once_the_interval_elapses(realm):
    sysjobs.run_one(realm, "prune-history")
    st = sysjobs.state(realm)
    old = dt.datetime.now().astimezone() - dt.timedelta(hours=200)
    st["prune-history"]["last_run"] = old.isoformat(timespec="seconds")
    sysjobs._save(realm, st)
    assert sysjobs.due(realm, "prune-history") is True


def test_a_switched_off_job_does_not_run_even_by_hand(realm):
    """Off means off. It used to mean "off on a schedule, but still runnable by hand", which put a
    live Run now next to a switch saying the job does not run — two controls contradicting each
    other, with no way to tell which governed tonight."""
    sysjobs.set_enabled(realm, "prune-history", False)
    assert sysjobs.due(realm, "prune-history") is False
    assert sysjobs.run_one(realm, "prune-history")["ok"] is False
    r = sysjobs.run_one(realm, "prune-history", manual=True)
    assert r["ok"] is False and "switched off" in r["error"]
    sysjobs.set_enabled(realm, "prune-history", True)
    assert sysjobs.run_one(realm, "prune-history", manual=True)["ok"] is True


def test_a_failing_job_is_recorded_and_eventually_notified(realm, monkeypatch):
    """Silent background failure is the bug this feature exists to avoid — but so is a bell that
    rings for something that fixes itself on the next pass. Recorded on the first failure, raised
    once it's a pattern."""
    from armada import notify
    monkeypatch.setitem(sysjobs._BY_ID["prune-history"], "run",
                        lambda r: (_ for _ in ()).throw(RuntimeError("disk on fire")))
    r = sysjobs.run_one(realm, "prune-history")
    assert r["ok"] is False and "disk on fire" in r["detail"]
    s = next(j for j in sysjobs.status(realm) if j["id"] == "prune-history")
    assert s["status"] == "error", "the Jobs page shows it straight away"
    assert not notify.feed(realm), "but one miss does not interrupt"
    for _ in range(sysjobs._NOTIFY_AFTER_FAILS - 1):
        sysjobs.run_one(realm, "prune-history")
    fed = notify.feed(realm)
    assert fed and fed[0]["event"] == "system_job_failed" and fed[0]["href"] == "/jobs"
    assert "disk on fire" in fed[0]["body"]


def test_a_failing_job_never_raises_out(realm, monkeypatch):
    monkeypatch.setitem(sysjobs._BY_ID["prune-history"], "run",
                        lambda r: (_ for _ in ()).throw(KeyError("x")))
    sysjobs.run_one(realm, "prune-history")          # must not raise
    sysjobs.run_due(realm)                           # nor here


def test_one_broken_job_does_not_stop_the_others(realm, monkeypatch):
    monkeypatch.setitem(sysjobs._BY_ID["model-catalog"], "run",
                        lambda r: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setitem(sysjobs._BY_ID["capability-updates"], "run", lambda r: {"ok": True, "detail": "fine"})
    monkeypatch.setitem(sysjobs._BY_ID["prune-history"], "run", lambda r: {"ok": True, "detail": "fine"})
    results = sysjobs.run_due(realm)
    assert len(results) == len(sysjobs.JOBS), "every job is attempted"
    by_id = {r["id"]: r for r in results}
    assert by_id["model-catalog"]["ok"] is False, "the broken one fails"
    # …and the ones after it in the list still ran and succeeded. Named rather than counted: some
    # jobs legitimately fail in a sandbox with no network, and counting ties this test to which
    # ones happen to work offline rather than to what it is actually checking.
    assert by_id["capability-updates"]["ok"] and by_id["prune-history"]["ok"]


def test_quota_jobs_are_skipped_when_signed_out(realm, monkeypatch):
    """With notifications live, running these signed out would produce a storm of failures rather
    than one clear message — the sign-in banner already says what's wrong."""
    from armada import auth
    monkeypatch.setattr(auth, "status", lambda force=False: {"logged_in": False})
    monkeypatch.setitem(sysjobs._BY_ID["prune-history"], "cost", sysjobs.QUOTA)
    r = sysjobs.run_one(realm, "prune-history")
    assert r["ok"] is False and r.get("skipped") is True


def test_free_jobs_run_regardless_of_sign_in(realm, monkeypatch):
    from armada import auth
    monkeypatch.setattr(auth, "status", lambda force=False: {"logged_in": False})
    assert sysjobs.run_one(realm, "prune-history")["ok"] is True


def test_unknown_job_is_rejected(realm):
    assert sysjobs.run_one(realm, "nope")["ok"] is False
    assert sysjobs.set_enabled(realm, "nope", True)["ok"] is False


def test_corrupt_state_reads_as_never_run(realm):
    (realm / sysjobs._STATE).write_text("{not json", encoding="utf-8")
    assert sysjobs.state(realm) == {}
    assert sysjobs.due(realm, "model-catalog") is True


def test_boot_no_longer_refreshes_models_unconditionally():
    """It used to fire on every server start — repeatedly during a working session, never if the
    app stayed shut. Now it's a scheduled job that boot only nudges when actually due."""
    src = Path(sysjobs.__file__).with_name("serve.py").read_text(encoding="utf-8")
    assert "_models.refresh(realm)" not in src
    assert 'sysjobs.due(realm, "model-catalog")' in src


def test_scheduler_runs_system_jobs():
    src = Path(sysjobs.__file__).with_name("scheduler.py").read_text(encoding="utf-8")
    assert "sysjobs.run_due" in src


def _sys_table(tmp_path):
    import datetime
    from armada.webui import realmpages
    html, n = realmpages._system_jobs_table(tmp_path, datetime.datetime.now().astimezone())
    return html, n


def test_ui_shows_cost_for_every_job(tmp_path):
    html, n = _sys_table(tmp_path)
    assert n == len(sysjobs.JOBS)
    assert html.count("mc-cap-pill") == n, "every system job must declare its cost"
    # Word-for-word the User list's pills. The same cost means the same thing on both tabs, and
    # two spellings of it invites the question of whether it does.
    assert "uses quota" in html and ">free<" in html


def test_ui_renders_a_real_toggle_per_job(tmp_path):
    """The switch is drawn on .mc-toggle-sl; the input is zero-sized and transparent. Emitting a
    bare <span> renders no control at all — which is exactly what happened."""
    html, n = _sys_table(tmp_path)
    assert html.count('class="mc-toggle"') == n
    assert html.count('class="mc-toggle-sl"') == n, "the toggle needs its slider span or it is invisible"
    assert html.count("mcSysJobToggle") == n
    js = (Path(sysjobs.__file__).parent / "webui" / "static" / "js" / "sysjobs.js").read_text(encoding="utf-8")
    assert "window.mcSysJobToggle" in js and "window.mcSysJobRun" in js


def test_system_jobs_use_the_same_list_chrome_as_user_jobs(tmp_path):
    """One list, drawn once. System jobs were a <table> while user jobs were expandable rows, which
    is how the same two facts came to be laid out two different ways on two tabs of one page."""
    html, _n = _sys_table(tmp_path)
    assert 'id="mc-sysjobstable"' in html and "mc-joblist" in html
    assert "mcSortJobs" in html, "the header sorts through the same code the User list uses"
    for attr in ("data-status=", "data-cadence=", "data-cost=", "data-owner=",
                 "data-jstatus=", "data-jcad=", "data-name="):
        assert attr in html, f"rows need {attr} for the shared filters and sorting to work"


def test_system_rows_drop_what_does_not_apply(tmp_path):
    """No Owner (always ARMADA — a column of identical values is decoration), no Last run (the week
    strip says more than one timestamp did), and no expand (there is nothing behind the row)."""
    html, _n = _sys_table(tmp_path)
    assert "Last run" not in html
    assert ">ARMADA<" not in html
    assert "<details" not in html and "mc-jcaret" not in html


def test_system_rows_carry_the_week_strip_and_next_run(tmp_path):
    html, n = _sys_table(tmp_path)
    assert html.count("data-week") == n
    assert html.count("data-next-cell") == n
    assert "On/Off" in html, "the switch column is named on both tabs"


def test_run_now_matches_the_user_list_button(tmp_path):
    """Same primary button, same play icon. A system job has no expanded view to put it in, so it
    lives in the row — but it should not become a different-looking control because of that."""
    html, n = _sys_table(tmp_path)
    assert html.count('class="btn btn-primary btn-sm"') == n
    assert html.count("mcSysJobRun") == n


def test_environment_context_job_is_weekly_and_free():
    j = sysjobs._BY_ID["environment-context"]
    assert sysjobs.interval_minutes(j) == 7 * 24 * 60
    assert j["cost"] == sysjobs.FREE


def test_environment_context_refresh_never_overwrites_user_memories(tmp_path, monkeypatch):
    """It regenerates the managed system memory from sources only. A realm memory the user wrote
    must come through a refresh byte-identical."""
    from armada import memory as _memory
    (tmp_path / "memory").mkdir(parents=True)
    (tmp_path / "realm.json").write_text('{"name":"T","user":{"name":"Mihai"}}', encoding="utf-8")
    mine = tmp_path / "memory" / "my-note.md"
    mine.write_text("---\ntitle: Mine\n---\nDo not touch this.\n", encoding="utf-8")
    before = mine.read_bytes()
    r = sysjobs.run_one(tmp_path, "environment-context", manual=True)
    assert r["ok"] is True
    assert mine.read_bytes() == before
    sysmem = (tmp_path / "memory" / _memory.SYSTEM_MEMORY_FILE).read_text(encoding="utf-8")
    assert "Mihai" in sysmem, "owner facts come from settings, and survive the refresh"


def test_toggle_markup_matches_the_shared_stylesheet():
    css = (Path(sysjobs.__file__).parent / "webui" / "static" / "brand.css").read_text(encoding="utf-8")
    assert ".mc-toggle .mc-toggle-sl" in css      # the class the JS must emit to be visible


# --- the week strip -----------------------------------------------------------------------------
# A system job runs on an interval, not at a time of day, which changes what a blank day means.

def _strip(runs, enabled=True, now=None):
    import datetime
    from armada.webui.agentbits import _sysjob_health7
    now = now or datetime.datetime.now().astimezone()
    return [lbl for _d, _dt, lbl, _w in _sysjob_health7(runs, now, enabled)]


def _iso(days_ago: int) -> str:
    import datetime
    return (datetime.datetime.now().astimezone()
            - datetime.timedelta(days=days_ago)).isoformat(timespec="seconds")


def test_an_interval_job_is_never_marked_missed():
    """The whole point of the separate strip. "Every 30 minutes" cannot be late — it runs when the
    scheduler next comes round — so a day with no record means we have no record, not that
    something went wrong. Marking those red would put a week of failures against every job on a
    machine that was simply switched off over the weekend."""
    assert "Missed" not in _strip([])
    assert "Missed" not in _strip([{"ts": _iso(2), "status": "error"}])


def test_past_days_take_the_worst_recorded_status():
    runs = [{"ts": _iso(2), "status": "ok"}, {"ts": _iso(2), "status": "error"}]
    assert _strip(runs)[1] == "Failed", "one bad run in a day makes the day bad"
    assert _strip([{"ts": _iso(2), "status": "ok"}])[1] == "Success"


def test_days_with_no_record_read_as_nothing_scheduled():
    assert _strip([])[0] == "Not scheduled"      # three days back


def test_today_and_ahead_are_scheduled_while_the_job_is_on():
    s = _strip([])
    assert s[3:] == ["Scheduled"] * 4, "an interval job is always going to run again"


def test_a_job_switched_off_is_not_scheduled():
    assert _strip([], enabled=False)[3:] == ["Not scheduled"] * 4


def test_a_recorded_run_today_beats_the_pencilled_in_one():
    s = _strip([{"ts": _iso(0), "status": "error"}])
    assert s[3] == "Failed", "what actually happened outranks what is still to come"


def test_running_a_job_records_it_in_a_bounded_history(tmp_path, monkeypatch):
    monkeypatch.setattr(sysjobs, "_HISTORY_MAX", 3)
    jid = "prune-history"
    for _ in range(5):
        sysjobs.run_one(tmp_path, jid, manual=True)
    runs = sysjobs.state(tmp_path)[jid]["runs"]
    assert len(runs) == 3, "history is trimmed on write so the state file can't grow forever"
    assert all(r.get("ts") and r.get("status") in ("ok", "error") for r in runs)
    assert [j for j in sysjobs.status(tmp_path) if j["id"] == jid][0]["runs"] == runs


def test_a_realm_with_no_history_yet_shows_an_empty_week(tmp_path):
    """Jobs that ran before this build kept only their last run. An empty week is the honest
    answer; inventing days from a single timestamp is not."""
    j = [x for x in sysjobs.status(tmp_path) if x["id"] == "prune-history"][0]
    assert j["runs"] == []
