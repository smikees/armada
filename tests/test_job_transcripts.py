"""Job output survives navigation and doesn't contaminate owner conversations."""
import datetime as dt
import json

import pytest

from armada import runner, reader
from armada.engine import CodexEngine, ClaudeEngine
from armada.engine.base import RunResult
from armada.job_history import thread_name, transcript
from armada.routes._shared import _job_detail
from armada.routes.jobs import JobRoutes
from armada.threads import Thread
from armada.webui.threadsview import _render_turns, thread_metrics, _ordered_threads
from armada.webui.agentbits import _job_health7


@pytest.fixture
def realm(tmp_path):
    ad = tmp_path / "agents" / "a"
    (ad / "jobs").mkdir(parents=True)
    (tmp_path / "realm.json").write_text(json.dumps({"name": "R", "default_effort": "high",
        "default_verbosity": "standard"}), encoding="utf-8")
    (ad / "agent.json").write_text(json.dumps({"id": "a", "display": "Ada", "model": "gpt-5",
        "effort": "medium", "verbosity": "brief"}), encoding="utf-8")
    (ad / "jobs" / "work.json").write_text(json.dumps({"id": "work", "name": "Work",
        "prompt": "Do the work"}), encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize("override", [False, True])
@pytest.mark.parametrize("provider", [CodexEngine, ClaudeEngine])
def test_job_settings_and_live_output_are_isolated_and_durable(realm, monkeypatch, override, provider):
    ad = realm / "agents" / "a"
    jobfile = ad / "jobs/work.json"
    jc = json.loads(jobfile.read_text())
    if provider is ClaudeEngine:
        ac = json.loads((ad / "agent.json").read_text())
        ac["model"] = "claude-sonnet-4-6"
        (ad / "agent.json").write_text(json.dumps(ac), encoding="utf-8")
    if override:
        jc.update(model="gpt-5-mini" if provider is CodexEngine else "claude-opus-4-8", effort="low", verbosity="full")
        jobfile.write_text(json.dumps(jc), encoding="utf-8")
    Thread(ad).append("My chat", "My answer")
    def stream(self, **kw):
        expected = ("gpt-5-mini" if override else "gpt-5") if provider is CodexEngine else (
            "claude-opus-4-8" if override else "claude-sonnet-4-6")
        assert kw["model"] == expected
        assert kw["effort"] == ("low" if override else "medium")
        if provider is CodexEngine:
            assert kw["verbosity"] == ("full" if override else "brief")
        assert ("How much to write (Detailed)" if override else "How much to write (Brief)") in kw["system"]
        kw["on_event"]({"kind": "text", "text": "Live **answer**"})
        detail = _job_detail(realm, "a", "work")
        assert detail["running"] and "mc-pending" in detail["html"]
        assert "Live <strong>answer</strong>" in detail["html"]
        assert "Live" not in _render_turns(realm, reader.read(realm).agents[0], "main")
        return RunResult(ok=False, output="Live **answer**", error="Specific failure reason")
    monkeypatch.setattr(provider, "run_stream", stream)
    result = runner.run_job(realm, "a", "work", engine=provider())
    assert result["status"] == "error"
    assert Thread.list_threads(ad) == ["main"]
    assert len(Thread(ad)._messages()) == 2
    assert not (ad / "threads/meta.json").exists(), "jobs must not mark a chat unread"
    saved = transcript(ad, result)
    assert "Specific failure reason" not in saved["content"]
    assert "Specific failure reason" in saved["app_errors"]
    assert result["output_file"] and "output" not in result, "large output must not inflate accounting"
    # A compacted job conversation still has its original, complete run output.
    Thread(ad, thread_name("work")).msgs.write_text("", encoding="utf-8")
    detail = _job_detail(realm, "a", "work", result["run_id"])
    assert not detail["running"] and "Specific failure reason" in detail["html"]
    assert "Live <strong>answer</strong>" in detail["html"]


def test_legacy_job_output_moves_in_presentation_without_changing_action_indexes(realm):
    ad = realm / "agents/a"
    th = Thread(ad)
    th.append("Job prompt", "Job **deliverable**")
    job_turn = th._messages()[-1]
    runner._write_report(ad, "a", {"task": "work", "kind": "job", "thread": "main",
        "ts": job_turn["ts"], "summary": "Done", "status": "ok"})
    th.append("Owner question", "Owner answer")
    # A later chat must not share the old report's second-resolution timestamp.
    ms = th._messages()
    for m in ms[2:]:
        m["ts"] = "2099-01-01T00:00:00"
    th.msgs.write_text("".join(json.dumps(m) + "\n" for m in ms), encoding="utf-8")
    raw = th.msgs.read_bytes()
    page = _render_turns(realm, reader.read(realm).agents[0], "main")
    assert "deliverable" not in page and "Owner question" in page
    assert 'data-idx="2"' in page and 'data-idx="3"' in page
    assert thread_metrics(realm, "a", "main")["messages"] == 2
    assert "Job <strong>deliverable</strong>" in _job_detail(realm, "a", "work")["html"]
    assert th.msgs.read_bytes() == raw


def test_run_picker_reads_the_selected_snapshot(realm):
    from armada.job_history import save_transcript
    ad = realm / "agents/a"
    for n in (1, 2):
        run = f"run{n}"
        filename = save_transcript(ad, run, {"content": f"Deliverable {n}"})
        runner._write_report(ad, "a", {"task": "work", "kind": "job", "thread": thread_name("work"),
            "ts": f"2026-09-30T10:00:0{n}", "run_id": run, "status": "ok", "output_file": filename})
    assert "Deliverable 2" in _job_detail(realm, "a", "work")["html"]
    assert "Deliverable 1" in _job_detail(realm, "a", "work", "run1")["html"]


def test_job_save_can_set_and_clear_overrides_without_losing_other_fields(realm):
    h = JobRoutes()
    h.realm = realm
    assert h._save_job({"agent": "a", "job": "work", "model": "gpt-5-mini",
        "effort": "low", "verbosity": "full"})["ok"]
    assert h._save_job({"agent": "a", "job": "work", "summary": "Updated"})["ok"]
    file = realm / "agents/a/jobs/work.json"
    jc = json.loads(file.read_text())
    assert jc["model"] == "gpt-5-mini" and jc["verbosity"] == "full"
    assert h._save_job({"agent": "a", "job": "work", "model": "", "effort": "", "verbosity": ""})["ok"]
    jc = json.loads(file.read_text())
    assert all(key not in jc for key in ("model", "effort", "verbosity"))
    assert jc["prompt"] == "Do the work"


def test_today_uses_latest_result_while_past_days_keep_the_worst():
    now = dt.datetime(2026, 9, 30, 12, tzinfo=dt.timezone.utc)
    runs = [{"ts": "2026-09-30T09:00:00", "status": "error"},
            {"ts": "2026-09-30T10:00:00", "status": "ok"}]
    assert _job_health7(runs, "manual", now, latest_today=True)[3][2] == "Success"
    assert _job_health7(runs, "manual", now, True, latest_today=True)[3][2] == "Running"


def test_command_output_and_failure_are_saved_in_jobs(realm):
    import sys
    ad = realm / "agents/a"
    job = {"id": "work", "kind": "command", "run": [sys.executable, "-c",
        "import sys; print('Command output'); print('Command failure', file=sys.stderr); sys.exit(2)"]}
    (ad / "jobs/work.json").write_text(json.dumps(job), encoding="utf-8")
    result = runner.run_job(realm, "a", "work")
    assert result["status"] == "error" and result["returncode"] == 2
    detail = _job_detail(realm, "a", "work")
    assert "Command output" in detail["html"] and "Command failure" in detail["html"]
    assert not Thread(ad)._messages()
