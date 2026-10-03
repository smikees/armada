"""Realm lifecycle must prevent dispatch from every Armada process, retaining history."""
import json
import os
from pathlib import Path

import pytest

from armada import realmops, scheduler, sysjobs, runner, util


@pytest.fixture
def realm(tmp_path):
    root = tmp_path / "Disposable"
    util.write_json_atomic(root / "realm.json", {"name": "Disposable"})
    util.write_json_atomic(root / "agents" / "finance" / "agent.json", {"name": "Finance"})
    util.write_json_atomic(root / "agents" / "finance" / "jobs" / "daily.json",
                           {"enabled": True, "schedule": "daily 09:00", "prompt": "Report"})
    (root / "reports").mkdir()
    (root / "reports" / "report.md").write_text("Existing report", encoding="utf-8")
    return root


def test_archive_disables_every_job_and_does_not_toggle_machine_settings(realm, monkeypatch):
    from armada import appconfig
    monkeypatch.setattr(appconfig, "save", lambda *a: pytest.fail("No other realm's settings may change"))
    assert realmops.archive(realm)["ok"]
    assert realmops.archived(realm)
    assert not util.read_json_state(realm / "agents/finance/jobs/daily.json")["enabled"]
    assert all(not sysjobs.is_enabled(realm, job["id"]) for job in sysjobs.JOBS)
    assert (realm / "reports/report.md").read_text() == "Existing report"
    assert scheduler.tick(realm, dry_run=True)[0]["job"] == "realm-archived"
    with pytest.raises(util.StateError, match="archived"):
        runner.run_job(realm, "finance", "daily")
    assert sysjobs.run_one(realm, sysjobs.JOBS[0]["id"], manual=True)["status"] == "skipped"
    realmops.restore(realm)
    assert not realmops.archived(realm)
    assert not util.read_json_state(realm / "agents/finance/jobs/daily.json")["enabled"]
    assert all(not sysjobs.is_enabled(realm, job["id"]) for job in sysjobs.JOBS)


@pytest.mark.parametrize("activity", ["chat", "system"])
def test_archive_and_delete_refuse_live_cross_process_activity(realm, activity):
    record = {"owner_pid": os.getpid(), "state": "claimed", "attempt_id": "test"}
    if activity == "chat":
        util.write_json_atomic(realm / "agents/finance/runs/.running/turn.json", record)
    else:
        util.write_json_atomic(realm / "system_jobs.json", {"test": {"attempt": record}})
    assert not realmops.archive(realm)["ok"]
    assert not realmops.delete(realm, permanent=True)["ok"]
    assert not realmops.archived(realm)
    assert (realm / "reports/report.md").exists()


def test_delete_removes_whole_realm_and_stale_scheduler_cannot_recreate_it(realm):
    assert realmops.delete(realm, permanent=True)["ok"]
    assert not realm.exists()
    assert scheduler.tick(realm)[0]["job"] == "realm-missing"
    assert not realm.exists()


def test_archive_preserves_guard_if_a_job_definition_is_corrupt(realm):
    (realm / "agents/finance/jobs/daily.json").write_text("not json", encoding="utf-8")
    result = realmops.archive(realm)
    assert not result["ok"] and result["error"]
    assert realmops.archived(realm)
    assert scheduler.tick(realm, dry_run=True)[0]["status"] == "held"


def test_legacy_system_claim_uses_live_lock_not_the_old_record(realm):
    state = {"test": {"attempt": {"attempt_id": "old", "state": "claimed", "started": "2026-09-30"}}}
    util.write_json_atomic(realm / "system_jobs.json", state)
    assert not realmops.busy(realm)
    with util.file_lock(realm / ".scheduler/system/test.json"):
        assert realmops.busy(realm)
    assert util.read_json_state(realm / "system_jobs.json") == state
