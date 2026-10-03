"""External job access is owner-approved and completion is evidence-based."""
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from armada import appconfig, job_access, runner


def _approved_job(tmp_path, monkeypatch):
    realm = tmp_path / "realm"
    folder = realm / "agents" / "steve" / "jobs"
    folder.mkdir(parents=True)
    (realm / "realm.json").write_text('{"timezone":"local"}', encoding="utf-8")
    project = tmp_path / "external"
    project.mkdir()
    job = {"id": "digest", "kind": "agent", "allow_tools": True, "prompt": "Publish today's digest"}
    (folder / "digest.json").write_text(json.dumps(job), encoding="utf-8")
    entry = {"fingerprint": job_access.fingerprint(job), "roots": [str(project)],
             "network": True, "checks": []}
    monkeypatch.setattr(appconfig, "get", lambda key, default=None:
                        {job_access.identity(realm, "steve", "digest"): entry} if key == "job_access" else default)
    return realm, project, job, entry


def test_job_grant_is_scoped_to_the_saved_approved_prompt(tmp_path, monkeypatch):
    realm, project, job, entry = _approved_job(tmp_path, monkeypatch)
    grant = job_access.grant_for(realm, "steve", job)
    assert grant.roots == (str(project),) and grant.network
    assert not job_access.grant_for(realm, "other", job).roots
    with pytest.raises(ValueError, match="no longer matches"):
        job_access.grant_for(realm, "steve", {**job, "prompt": "Do something else"})
    saved = realm / "agents" / "steve" / "jobs" / "digest.json"
    saved.write_text(json.dumps({**job, "prompt": "Changed on disk"}), encoding="utf-8")
    with pytest.raises(ValueError, match="saved job"):
        job_access.grant_for(realm, "steve", job)


def test_completion_checks_require_fresh_artifact_and_today_value(tmp_path, monkeypatch):
    realm, project, job, entry = _approved_job(tmp_path, monkeypatch)
    artifact = project / "receipt.json"
    entry["checks"] = [{"kind": "fresh_file", "path": str(artifact), "min_bytes": 10},
                       {"kind": "json_today", "path": str(artifact), "field": "date"}]
    grant = job_access.grant_for(realm, "steve", job)
    started = time.time()
    assert "not created" in job_access.verify(realm, grant, started)
    artifact.write_text(json.dumps({"date": "yesterday"}), encoding="utf-8")
    assert "does not report" in job_access.verify(realm, grant, started)
    artifact.write_text(json.dumps({"date": datetime.now().astimezone().date().isoformat()}), encoding="utf-8")
    assert job_access.verify(realm, grant, started) == ""


def test_completion_checks_expand_previous_reporting_periods(tmp_path, monkeypatch):
    import datetime as dt

    realm, project, _job, _entry = _approved_job(tmp_path, monkeypatch)
    monkeypatch.setattr(job_access.scheduler, "now_in", lambda _cfg: dt.datetime(2026, 10, 1))
    (project / "monthly-2026-09.md").write_text("September report", encoding="utf-8")
    (project / "quarterly-2026-Q3.md").write_text("Q3 report", encoding="utf-8")
    grant = job_access.Grant(checks=(
        {"kind": "fresh_file", "path": str(project / "monthly-{previous_month}.md")},
        {"kind": "fresh_file", "path": str(project / "quarterly-{previous_quarter}.md")},
    ))
    assert job_access.verify(realm, grant, time.time()) == ""


@pytest.mark.parametrize(("today", "prior"), [
    ((2026, 9, 30), "2026-Q2"),
    ((2026, 10, 1), "2026-Q3"),
    ((2027, 1, 1), "2026-Q4"),
])
def test_previous_quarter_means_last_completed_quarter(tmp_path, monkeypatch, today, prior):
    realm, project, _job, _entry = _approved_job(tmp_path, monkeypatch)
    monkeypatch.setattr(job_access.scheduler, "now_in", lambda _cfg: datetime(*today))
    (project / f"quarterly-{prior}.md").write_text("Completed quarter", encoding="utf-8")
    grant = job_access.Grant(checks=(
        {"kind": "fresh_file", "path": str(project / "quarterly-{previous_quarter}.md")},))
    assert job_access.verify(realm, grant, time.time()) == ""


def test_file_today_allows_same_day_retry_but_rejects_prior_day(tmp_path, monkeypatch):
    realm, project, _job, _entry = _approved_job(tmp_path, monkeypatch)
    zone = timezone(timedelta(hours=2))
    monkeypatch.setattr(job_access.scheduler, "now_in",
                        lambda _cfg: datetime(2026, 9, 30, 17, 30, tzinfo=zone))
    artifact = project / "monthly-2026-08.md"
    artifact.write_text("Completed audit", encoding="utf-8")
    morning = datetime(2026, 9, 30, 9, 0, tzinfo=zone).timestamp()
    os.utime(artifact, (morning, morning))
    grant = job_access.Grant(checks=({"kind": "file_today", "path": str(artifact)},))
    assert job_access.verify(realm, grant, datetime(2026, 9, 30, 17, 0, tzinfo=zone).timestamp()) == ""
    yesterday = datetime(2026, 9, 29, 23, 0, tzinfo=zone).timestamp()
    os.utime(artifact, (yesterday, yesterday))
    assert "not updated today" in job_access.verify(realm, grant, morning)


def test_manual_run_honours_the_saved_jobs_tool_grant(tmp_path, monkeypatch):
    from armada import execution
    seen = []
    monkeypatch.setattr(runner.RunContext, "capture", lambda *args: object())
    monkeypatch.setattr(execution, "TurnCoordinator", lambda request: type("Turn", (), {
        "run": lambda self: seen.append(request.allow_tools) or {"status": "ok"}})())
    job = {"id": "price", "kind": "agent", "allow_tools": True, "prompt": "Run"}
    runner._run_job_inner(tmp_path, "steve", "price", "auto", "main", False,
                          None, Path(tmp_path), {}, job)
    assert seen == [True]


def test_required_outcome_marker_prevents_a_completed_turn_from_being_success():
    job = {"require_outcome_marker": True}
    assert "did not confirm" in job_access.reported_failure(job, "I could not publish today.")
    assert job_access.reported_failure(job, "No Telegram was sent.\nARMADA_JOB_RESULT: FAILED") == "No Telegram was sent."
    assert job_access.reported_failure(job, "Live manifest verified.\nARMADA_JOB_RESULT: SUCCESS") == ""
    assert job_access.reported_failure({}, "I could not publish today.") == ""


def test_report_summary_omits_machine_outcome_marker():
    from armada.execution import _report_summary
    assert _report_summary("Started.\n\nPublished and verified.\nARMADA_JOB_RESULT: SUCCESS") == "Published and verified."
