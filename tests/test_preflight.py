"""Can this realm run on this machine — and if not, does it say so loudly and stop?

The failure this prevents: a realm restored from an export runs its jobs nightly against a
workspace folder that doesn't exist here, failing identically every time, until someone reads a
week of notifications and works out why.
"""
import json

import pytest

from armada import appconfig, approot, preflight, scheduler, workspace


@pytest.fixture(autouse=True)
def _approot(tmp_path, monkeypatch):
    """Point the app root at tmp_path so realms built below count as inside it — and so no test
    reads or writes the developer's real ~/.armada/config.json."""
    cfgdir = tmp_path / "home" / ".armada"
    cfgdir.mkdir(parents=True)
    monkeypatch.setattr(appconfig, "_path", lambda: cfgdir / "config.json")
    approot.set_root(str(tmp_path))
    yield


def _realm(tmp_path, *, ws=None, jobs=None, agents=("warren",)):
    r = tmp_path / "realm"
    r.mkdir(parents=True, exist_ok=True)
    cfg = {"name": "R"}
    if ws is not None:
        cfg["workspace"] = ws
    (r / "realm.json").write_text(json.dumps(cfg), encoding="utf-8")
    for a in agents:
        (r / "agents" / a / "jobs").mkdir(parents=True)
        (r / "agents" / a / "agent.json").write_text(json.dumps({"id": a}), encoding="utf-8")
        for jid, prompt in (jobs or {}).items():
            (r / "agents" / a / "jobs" / f"{jid}.json").write_text(
                json.dumps({"id": jid, "prompt": prompt}), encoding="utf-8")
    return r


def _by_id(res, cid):
    return next(c for c in res["checks"] if c["id"] == cid)


# --------------------------------------------------------------------------- workspace

def test_a_missing_workspace_blocks(tmp_path):
    r = _realm(tmp_path, ws=str(tmp_path / "not-here"))
    c = preflight.workspace_check(r)
    assert c["ok"] is False and c["severity"] == preflight.BLOCK
    assert c["action"] == "set-workspace"


def test_a_present_workspace_passes(tmp_path):
    w = tmp_path / "work"
    w.mkdir()
    c = preflight.workspace_check(_realm(tmp_path, ws=str(w)))
    assert c["ok"] is True and str(w) in c["detail"]


def test_an_unset_workspace_blocks_only_if_jobs_refer_to_one(tmp_path):
    needs = _realm(tmp_path / "a", jobs={"j": "read D:\\Work\\Finance\\x.csv"})
    c = preflight.workspace_check(needs)
    assert c["ok"] is False and "D:\\Work" in c["detail"]

    doesnt = _realm(tmp_path / "b", jobs={"j": "summarise the news"})
    assert preflight.workspace_check(doesnt)["ok"] is True


def test_a_realm_using_the_token_is_ready_once_the_root_is_set(tmp_path):
    w = tmp_path / "work"
    w.mkdir()
    r = _realm(tmp_path, ws=str(w), jobs={"j": "read {workspace}/Finance/x.csv"})
    assert preflight.workspace_check(r)["ok"] is True


# --------------------------------------------------------------------------- realm files

def test_unreadable_job_files_block(tmp_path):
    r = _realm(tmp_path, jobs={"good": "fine"})
    (r / "agents" / "warren" / "jobs" / "broken.json").write_text("{not json", encoding="utf-8")
    checks = {c["id"]: c for c in preflight.realm_check(r)}
    assert checks["jobs"]["ok"] is False and checks["jobs"]["severity"] == preflight.BLOCK
    assert "broken.json" in checks["jobs"]["detail"]


def test_a_folder_that_is_not_a_realm_blocks(tmp_path):
    empty = tmp_path / "random"
    empty.mkdir()
    assert preflight.realm_check(empty)[0]["ok"] is False


def test_a_healthy_realm_reports_its_counts(tmp_path):
    r = _realm(tmp_path, jobs={"a": "x", "b": "y"})
    checks = {c["id"]: c for c in preflight.realm_check(r)}
    assert checks["agents"]["ok"] and "1 readable" in checks["agents"]["detail"]
    assert checks["jobs"]["ok"] and "2 readable" in checks["jobs"]["detail"]


# --------------------------------------------------------------------------- severity

def test_telegram_is_a_warning_not_a_blocker(tmp_path):
    """Jobs still run without it; only the notification route is degraded."""
    c = preflight.telegram_check()
    assert c["ok"] is False                      # conftest hides the real credentials
    assert c["severity"] == preflight.WARN


def test_warnings_alone_do_not_block(tmp_path, monkeypatch):
    w = tmp_path / "work"
    w.mkdir()
    r = _realm(tmp_path, ws=str(w))
    monkeypatch.setattr(preflight, "engine_check",
                        lambda e="claude": preflight._check("engine", "Engine", True, "ok"))
    res = preflight.run(r)
    assert res["ok"] is True
    assert res["warnings"] and not res["blocking"]
    assert "degraded" in res["summary"]


def test_the_summary_names_what_is_broken(tmp_path, monkeypatch):
    r = _realm(tmp_path, ws=str(tmp_path / "gone"))
    monkeypatch.setattr(preflight, "engine_check",
                        lambda e="claude": preflight._check("engine", "Engine", True, "ok"))
    res = preflight.run(r)
    assert res["ok"] is False
    assert "Workspace folder" in res["summary"]


# --------------------------------------------------------------------------- the hold

def test_hold_is_off_by_default(tmp_path):
    assert preflight.held(_realm(tmp_path)) is False


def test_apply_hold_holds_a_broken_realm_and_says_why(tmp_path, monkeypatch):
    r = _realm(tmp_path, ws=str(tmp_path / "gone"))
    monkeypatch.setattr(preflight, "engine_check",
                        lambda e="claude": preflight._check("engine", "Engine", True, "ok"))
    res = preflight.apply_hold(r)
    assert res["held"] is True
    assert preflight.held(r) is True
    assert "Workspace" in preflight.hold_reason(r)


def test_apply_hold_releases_once_the_problem_is_fixed(tmp_path, monkeypatch):
    """Releasing matters as much as holding — nobody should have to remember there was a switch."""
    monkeypatch.setattr(preflight, "engine_check",
                        lambda e="claude": preflight._check("engine", "Engine", True, "ok"))
    w = tmp_path / "work"
    r = _realm(tmp_path, ws=str(w))
    assert preflight.apply_hold(r)["held"] is True

    w.mkdir()                                     # the owner points it at a real folder
    assert preflight.apply_hold(r)["held"] is False
    assert preflight.held(r) is False


def test_holding_preserves_the_rest_of_realm_json(tmp_path):
    r = _realm(tmp_path, ws="D:\\Work")
    preflight.set_hold(r, "because")
    cfg = json.loads((r / "realm.json").read_text(encoding="utf-8"))
    assert cfg["name"] == "R" and cfg["workspace"] == "D:\\Work"
    preflight.set_hold(r, "")
    assert "scheduler_hold" not in json.loads((r / "realm.json").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- the scheduler obeys

def test_the_scheduler_fires_nothing_while_held(tmp_path):
    r = _realm(tmp_path, jobs={"daily": "x"})
    j = r / "agents" / "warren" / "jobs" / "daily.json"
    j.write_text(json.dumps({"id": "daily", "prompt": "x", "schedule": "daily 00:00"}), encoding="utf-8")

    preflight.set_hold(r, "Workspace folder missing")
    fired = scheduler.tick(r, engine="mock")
    assert [f["status"] for f in fired] == ["held"]
    assert fired[0]["detail"] == "Workspace folder missing"


def test_a_released_realm_schedules_normally_again(tmp_path):
    r = _realm(tmp_path, jobs={"daily": "x"})
    preflight.set_hold(r, "broken")
    assert scheduler.tick(r, engine="mock")[0]["status"] == "held"
    preflight.set_hold(r, "")
    fired = scheduler.tick(r, engine="mock")
    assert not any(f.get("status") == "held" for f in fired)


def test_a_dry_run_still_reports_what_would_fire(tmp_path):
    """The hold stops work, not inspection — you need to see the schedule to trust the fix."""
    r = _realm(tmp_path)
    (r / "agents" / "warren" / "jobs" / "daily.json").write_text(
        json.dumps({"id": "daily", "prompt": "x", "schedule": "daily 00:00"}), encoding="utf-8")
    preflight.set_hold(r, "broken")
    assert not any(f.get("status") == "held" for f in scheduler.tick(r, engine="mock", dry_run=True))
