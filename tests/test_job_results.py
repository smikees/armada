import copy
import datetime as dt
import json
import re
import time

import pytest

from armada import job_results as jr, job_history, runner, util
from armada.engine.base import RunResult
from armada.engine.mock import MockEngine
from armada.routes._shared import _job_detail


def contract(root, *, audit="clear", execution="completed", delivery="sent", run_id="run-new"):
    report = root / "report.md"
    report.write_text("Required report", encoding="utf-8")
    receipt = root / "receipt.json"
    receipt.write_text(json.dumps({"schema_version": 1, "run_id": run_id, "status": "sent",
        "destination": "telegram", "sent_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "message_ids": [42]}), encoding="utf-8")
    data = {"schema_version": 1, "run_id": run_id, "execution": execution,
        "audit_outcome": audit, "delivery": [{"destination": "telegram", "status": delivery,
                                               "receipt_path": str(receipt)}],
        "evidence": {"outputs": [{"path": str(report), "required": True}],
                     "findings": [], "missing_inputs": [], "operational_errors": [], "risk_gates": []}}
    if audit == "findings":
        data["evidence"]["findings"] = ["Rule breached"]
    if audit == "incomplete":
        data["evidence"]["missing_inputs"] = ["Historical accounting and risk data unavailable"]
        data["evidence"]["risk_gates"] = ["Do not clear the drawdown gate"]
    if delivery == "failed":
        data["delivery"][0]["error"] = "Telegram returned HTTP 503"
    return data


def block(data):
    return "Original qualified answer.\n<armada_job_result>" + json.dumps(data) + "</armada_job_result>"


def evaluate(root, data, **kw):
    return jr.evaluate(block(data), run_id="run-new", job={"id": "work", "require_outcome_marker": True},
                       root=root, started=time.time() - 2, **kw)


@pytest.mark.parametrize("audit,expected,label", [
    ("clear", "ok", "Completed — audit clear — delivered"),
    ("findings", "warn", "Completed — audit findings — delivered"),
    ("incomplete", "warn", "Completed — audit incomplete — delivered"),
])
def test_reports_separate_execution_from_findings_and_missing_data(tmp_path, audit, expected, label):
    result = evaluate(tmp_path, contract(tmp_path, audit=audit))
    assert result["execution"] == "completed"
    assert jr.status(result) == expected and jr.label(result) == label
    assert result["delivery"][0]["validated"]
    assert result["evidence"]["outputs"][0]["validated"]


def test_required_report_write_failure_is_execution_failure(tmp_path):
    data = contract(tmp_path)
    (tmp_path / "report.md").unlink()
    result = evaluate(tmp_path, data)
    assert result["execution"] == "failed" and jr.status(result) == "error"
    assert "Report not produced" in result["app_errors"][0]
    assert jr.label(result) == "Failed — report not produced — delivered"


def test_delivery_failure_preserves_completed_execution_and_specific_error(tmp_path):
    result = evaluate(tmp_path, contract(tmp_path, audit="not_applicable", delivery="failed"))
    assert result["execution"] == "completed" and jr.status(result) == "warn"
    assert jr.label(result) == "Completed — delivery failed"
    assert result["delivery"][0]["error"] == "Telegram returned HTTP 503"


@pytest.mark.parametrize("terminal", ["timed_out", "stopped", "failed"])
def test_runtime_failure_overrides_agent_completion_but_keeps_partial_outputs(tmp_path, terminal):
    data = contract(tmp_path, audit="incomplete")
    result = evaluate(tmp_path, data, runtime_execution=terminal, runtime_error="exact runtime error")
    assert result["execution"] == terminal
    assert result["evidence"]["outputs"][0]["validated"]
    assert result["delivery"][0]["status"] == "sent"
    assert result["app_errors"][0] == "exact runtime error"


@pytest.mark.parametrize("bad", ["nothing", "<armada_job_result>{broken}</armada_job_result>",
    '<armada_job_result>{"schema_version":99}</armada_job_result>',
    '<armada_job_result>{"schema_version":1,"schema_version":1}</armada_job_result>',
    '<armada_job_result>{}', '<armada_job_result>{}</armada_job_result> trailing prose'])
def test_missing_or_malformed_contract_never_means_a_clean_audit(tmp_path, bad):
    result = jr.evaluate(bad, run_id="run-new", job={"require_outcome_marker": True},
                         root=tmp_path, started=time.time())
    assert result["execution"] == "completed"
    assert result["audit_outcome"] == "incomplete" and jr.status(result) == "warn"
    assert result["app_errors"]


@pytest.mark.parametrize("change", ["run", "date", "destination", "provider_id", "job", "version_bool", "identifier_object"])
def test_stale_or_mismatched_receipt_cannot_prove_delivery(tmp_path, change):
    data = contract(tmp_path)
    path = tmp_path / "receipt.json"
    receipt = json.loads(path.read_text())
    if change == "run":
        receipt["run_id"] = "run-old"
    elif change == "date":
        receipt["sent_at"] = "2020-01-01T00:00:00+00:00"
    elif change == "destination":
        receipt["destination"] = "other"
    elif change == "job":
        receipt["job_id"] = "other"
    elif change == "version_bool":
        receipt["schema_version"] = True
    elif change == "identifier_object":
        receipt["message_ids"] = []
        receipt["receipt_id"] = {"fake": "identifier"}
    else:
        receipt["message_ids"] = []
    path.write_text(json.dumps(receipt))
    result = evaluate(tmp_path, data)
    assert result["execution"] == "completed"
    assert result["delivery"][0]["status"] == "unknown" and jr.status(result) == "warn"


@pytest.mark.parametrize("field", ["receipt_path", "error"])
def test_malformed_delivery_fields_are_visible_validation_warnings(tmp_path, field):
    data = contract(tmp_path)
    data["delivery"][0][field] = {"invalid": "object"}
    result = evaluate(tmp_path, data)
    assert result["validation_errors"] and jr.status(result) == "warn"


def test_required_destinations_and_outputs_cannot_be_disabled_by_claim(tmp_path):
    data = contract(tmp_path, delivery="not_required")
    data["evidence"]["outputs"][0]["required"] = False
    (tmp_path / "report.md").unlink()
    result = jr.evaluate(block(data), run_id="run-new", root=tmp_path, started=time.time(),
        job={"result_contract": {"required_outputs": [str(tmp_path / "report.md")], "required_destinations": ["telegram"]}})
    assert result["execution"] == "failed" and result["delivery"][0]["status"] == "unknown"


@pytest.mark.parametrize("marker,execution", [("SUCCESS", "completed"), ("FAILED", "failed")])
def test_legacy_marker_and_explanation_are_preserved_without_inferred_pass(tmp_path, marker, execution):
    output = "Missing historical Greeks; audit not cleared.\nARMADA_JOB_RESULT: " + marker
    result = jr.evaluate(output, run_id="run-new", job={"require_outcome_marker": True}, root=tmp_path, started=time.time())
    assert result["execution"] == execution and result["audit_outcome"] == "incomplete"
    assert result["legacy_result"] == marker and result["detail_level"] == "legacy"
    assert result["legacy_explanation"] == "Missing historical Greeks; audit not cleared."
    assert jr.original_answer(output) == output


def test_final_clear_claim_with_findings_is_invalid(tmp_path):
    data = contract(tmp_path)
    data["evidence"]["findings"] = ["A breach"]
    result = evaluate(tmp_path, data)
    assert result["audit_outcome"] == "incomplete" and result["validation_errors"]


def test_prompt_example_is_a_valid_versioned_block():
    prompt = jr.instructions("run-new", {})
    data = jr._parse(jr.BLOCK.search(prompt).group(0), "run-new")
    assert data["schema_version"] == 1


def test_run_persistence_keeps_original_answer_separate_from_runtime_error(tmp_path, monkeypatch):
    ad = tmp_path / "agents/a"
    (ad / "jobs").mkdir(parents=True)
    util.write_json_atomic(tmp_path / "realm.json", {"name": "Test"})
    util.write_json_atomic(ad / "agent.json", {"id": "a"})
    util.write_json_atomic(ad / "jobs/work.json", {"id": "work", "prompt": "Write report", "require_outcome_marker": True})
    engine = MockEngine()
    def run(**kw):
        run_id = re.search(r"current run ID: (\w+)", kw["prompt"]).group(1)
        data = contract(tmp_path, audit="incomplete", run_id=run_id)
        return RunResult(ok=False, output=block(data), error="CLI timed out after 5s", timed_out=True)
    monkeypatch.setattr(engine, "run", run)
    report = runner.run_job(tmp_path, "a", "work", engine=engine)
    assert report["result"]["run_id"] == report["run_id"]
    assert report["result"]["execution"] == "timed_out"
    saved = job_history.transcript(ad, report)
    assert saved["content"] == "Original qualified answer."
    assert "CLI timed out after 5s" in saved["app_errors"]
    assert '<armada_job_result>' in saved["raw_final_answer"]
    html = _job_detail(tmp_path, "a", "work")["html"]
    assert "Armada errors / verification" in html and "Unresolved risk gates" in html


def test_historical_annotation_is_visible_and_original_run_is_immutable(tmp_path):
    ad = tmp_path / "agents/a"
    (ad / "jobs").mkdir(parents=True)
    util.write_json_atomic(tmp_path / "realm.json", {"name": "Test"})
    util.write_json_atomic(ad / "agent.json", {"id": "a"})
    util.write_json_atomic(ad / "jobs/work.json", {"id": "work", "prompt": "audit"})
    raw = {"task": "work", "run_id": "run-new", "status": "error", "summary": "Historical error",
           "ts": dt.datetime.now().isoformat(), "output": "Original answer\nARMADA_JOB_RESULT: FAILED"}
    runner._write_report(ad, "a", raw)
    log_path = ad / "runs/a.jsonl"
    before = log_path.read_bytes()
    result = evaluate(tmp_path, contract(tmp_path, audit="incomplete"))
    result.update(detail_level="historical_annotation", legacy_result="FAILED")
    job_history.annotate(ad, "run-new", result, "Report exists; incomplete audit, delivered", supporting_evidence={"receipt": "existing"})
    event = job_history.reports(ad)[0]
    assert event["original_status"] == "error" and event["status"] == "warn"
    assert log_path.read_bytes() == before
    html = _job_detail(tmp_path, "a", "work")["html"]
    assert "Historical error" in html and "ARMADA_JOB_RESULT: FAILED" in html
    assert "Completed — audit incomplete — delivered" in html
    with pytest.raises(ValueError, match="already"):
        job_history.annotate(ad, "run-new", result, "Another", supporting_evidence={"receipt": "existing"})
