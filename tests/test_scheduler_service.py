"""Scheduler status + auto-start (launch plan 5.5).

The failure these guard: scheduled jobs silently stopping because the background scheduler wasn't
running (after a reboot, or it died), with nothing on screen saying so. Now the window starts it,
every page shows a bar when it's down and the realm has scheduled jobs, and a scheduler started
before a realm existed picks that realm up instead of ignoring it until restarted.
"""
import json
import os
from pathlib import Path

import pytest

from armada import schedsvc, scheduler


def _realm(tmp: Path, jobs: dict | None = None) -> Path:
    r = tmp
    r.mkdir(parents=True, exist_ok=True)
    (r / "realm.json").write_text(json.dumps({"name": "t"}), encoding="utf-8")
    for jid, job in (jobs or {}).items():
        d = r / "agents" / "pm" / "jobs"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{jid}.json").write_text(json.dumps({"id": jid, **job}), encoding="utf-8")
    return r


def _hold_lock(r: Path, pid: int):
    (r / "scheduler.lock.json").write_text(json.dumps({"pid": pid, "started": "2026-09-24T09:00:00"}),
                                           encoding="utf-8")


@pytest.fixture(autouse=True)
def _reset_spawn(monkeypatch):
    monkeypatch.setattr(schedsvc, "_last_spawn", 0.0)


class _Popen:
    calls = []

    def __init__(self, cmd, **kw):
        _Popen.calls.append((cmd, kw))
        self.pid = 4242


@pytest.fixture
def popen(monkeypatch):
    _Popen.calls = []
    monkeypatch.setattr(schedsvc.subprocess, "Popen", _Popen)
    return _Popen


# --- status ------------------------------------------------------------------------------------

def test_status_is_not_running_without_a_live_lock(tmp_path):
    r = _realm(tmp_path / "r")
    assert schedsvc.status(r)["running"] is False
    _hold_lock(r, 0)                                    # a dead pid is a stale lock, not a scheduler
    assert schedsvc.status(r)["running"] is False


def test_status_is_running_when_a_live_process_holds_the_lock(tmp_path):
    r = _realm(tmp_path / "r")
    _hold_lock(r, os.getpid())
    st = schedsvc.status(r)
    assert st["running"] is True and st["pid"] == os.getpid() and st["started"]


def test_scheduled_counts_only_switched_on_jobs_with_a_schedule(tmp_path):
    r = _realm(tmp_path / "r", {
        "cron": {"schedule": "0 9 * * 1-5"},
        "cronfield": {"cron": "*/5 * * * *", "schedule": "manual"},
        "simple": {"schedule": "mon-fri 09:00"},
        "manual": {"schedule": "manual"},
        "blank": {"schedule": ""},
        "off": {"schedule": "0 9 * * *", "enabled": False},
    })
    assert schedsvc.status(r)["scheduled"] == 3


def test_a_realm_with_no_agents_folder_has_nothing_scheduled(tmp_path):
    assert schedsvc.scheduled_jobs(_realm(tmp_path / "r")) == 0


# --- start / ensure_running ---------------------------------------------------------------------

def test_start_launches_armada_schedule_detached_from_the_repo(popen):
    r = schedsvc.start()
    assert r["ok"] and r["pid"] == 4242
    cmd, kw = popen.calls[0]
    assert cmd[1:] == ["-m", "armada", "schedule", "--engine", "claude"]
    assert Path(kw["cwd"]) == schedsvc._REPO
    if os.name == "nt":
        assert kw["creationflags"] & 0x08000000         # CREATE_NO_WINDOW — no console flashes up


def test_a_second_start_moments_later_does_not_spawn_another(popen):
    schedsvc.start()
    r = schedsvc.start()
    assert r["ok"] and len(popen.calls) == 1


def test_start_reports_a_launch_failure_instead_of_raising(monkeypatch):
    def boom(*a, **k):
        raise OSError("no such file")
    monkeypatch.setattr(schedsvc.subprocess, "Popen", boom)
    r = schedsvc.start()
    assert r["ok"] is False and "no such file" in r["error"]


def test_ensure_running_leaves_a_running_scheduler_alone(tmp_path, popen):
    r = _realm(tmp_path / "r")
    _hold_lock(r, os.getpid())
    assert schedsvc.ensure_running(r)["already"] is True
    assert popen.calls == []


def test_ensure_running_respects_autostart_off(tmp_path, popen, monkeypatch):
    monkeypatch.setattr(schedsvc.appconfig, "get", lambda k, d=None: False if k == schedsvc.AUTOSTART_KEY else d)
    assert schedsvc.ensure_running(_realm(tmp_path / "r"))["skipped"]
    assert popen.calls == []


def test_ensure_running_starts_one_when_none_is_running(tmp_path, popen, monkeypatch):
    monkeypatch.setattr(schedsvc.appconfig, "get", lambda k, d=None: d)
    assert schedsvc.ensure_running(_realm(tmp_path / "r"))["ok"]
    assert len(popen.calls) == 1


# --- the daemon picks up realms created after it started ---------------------------------------

def test_daemon_rescan_takes_on_a_new_realm(tmp_path):
    a, b = _realm(tmp_path / "a"), _realm(tmp_path / "b")
    owned, others = [a], []
    try:
        scheduler._adopt_new_realms(lambda: [str(a), str(b)], owned, others)
        assert others == [b] and b in owned
        assert scheduler.lock_holder(b)["pid"] == os.getpid()
        scheduler._adopt_new_realms(lambda: [str(a), str(b)], owned, others)
        assert others == [b]                            # not added twice
    finally:
        scheduler._lock_release(b)


def test_daemon_rescan_skips_missing_folders_and_realms_another_process_owns(tmp_path, monkeypatch):
    a, c = _realm(tmp_path / "a"), _realm(tmp_path / "c")
    _hold_lock(c, 999999)
    monkeypatch.setattr(scheduler._util, "pid_alive", lambda pid: pid in (999999, os.getpid()))
    owned, others = [a], []
    scheduler._adopt_new_realms(lambda: [str(tmp_path / "gone"), str(c)], owned, others)
    assert others == [] and owned == [a]


def test_daemon_rescan_survives_a_broken_registry(tmp_path):
    def broken():
        raise ValueError("bad registry")
    owned, others = [tmp_path], []
    scheduler._adopt_new_realms(broken, owned, others)   # must not raise
    assert others == []


# --- wiring -------------------------------------------------------------------------------------

def test_routes_and_banner_are_wired():
    from armada import serve
    from armada.webui import layout
    assert serve.Handler._GET_EXACT["/api/scheduler-status"] == "_get_scheduler_status"
    assert serve.Handler._POST_JSON["/api/scheduler-start"] == "_scheduler_start"
    src = Path(layout.__file__).read_text(encoding="utf-8")
    assert 'id="mc-schedbar"' in src and "_SCHEDBAR_JS" in src


def test_cli_passes_a_rescan_only_when_ticking_every_realm():
    src = (Path(scheduler.__file__).parent / "cli.py").read_text(encoding="utf-8")
    assert "rescan=activerealm.every if every else None" in src
