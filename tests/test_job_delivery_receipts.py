"""Finance sender tests use fake provider responses; never contact Telegram."""
import importlib.util
import json
from pathlib import Path
import time

import pytest

from armada import job_results


@pytest.fixture
def sender(tmp_path, monkeypatch):
    path = Path(__file__).parents[1] / "tools" / "finance_telegram_sender.py"
    spec = importlib.util.spec_from_file_location("finance_sender_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "CAPITAL", tmp_path)
    monkeypatch.setattr(module, "credentials", lambda: ("fake-token", "fake-chat"))
    calls = []
    def post(_token, method, _body, _type):
        calls.append(method)
        return {"ok": True, "result": {"message_id": len(calls)}}
    monkeypatch.setattr(module, "_post", post)
    return module, calls


def test_provider_receipt_is_bound_to_run_and_document(sender, tmp_path):
    module, calls = sender
    document = tmp_path / "report.md"
    document.write_text("Report")
    started = time.time()
    assert module.main(["digest", "--document", str(document), "--job-id", "work", "--run-id", "run-new"]) == 0
    receipt_path = tmp_path / "telegram-receipts/work--run-new.json"
    receipt = json.loads(receipt_path.read_text())
    assert receipt["run_id"] == "run-new" and receipt["message_ids"] == [1, 2]
    assert receipt["document_path"] == str(document) and receipt["document_sha256"]
    assert calls == ["sendMessage", "sendDocument"]
    contract = {"schema_version": 1, "run_id": "run-new", "execution": "completed", "audit_outcome": "clear",
        "delivery": [{"destination": "telegram", "status": "sent", "receipt_path": str(receipt_path)}],
        "evidence": {"outputs": [{"path": str(document), "required": True}], "findings": [],
                     "missing_inputs": [], "risk_gates": [], "operational_errors": []}}
    result = job_results.evaluate('<armada_job_result>'+json.dumps(contract)+'</armada_job_result>',
        run_id="run-new", job={"id": "work"}, root=tmp_path, started=started)
    assert result["delivery"][0]["validated"]


def test_prior_delivery_is_not_resend_or_a_current_run_receipt(sender, tmp_path, capsys):
    module, calls = sender
    assert module.main(["digest", "--job-id", "work", "--run-id", "run-old"]) == 0
    before = len(calls)
    assert module.main(["digest", "--job-id", "work", "--run-id", "run-new"]) == 0
    assert len(calls) == before
    assert not (tmp_path / "telegram-receipts/work--run-new.json").exists()
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["matched_run"] is False


def test_same_run_resend_cannot_overwrite_receipt_or_send_again(sender, tmp_path):
    module, calls = sender
    assert module.main(["digest", "--job-id", "work", "--run-id", "run-new"]) == 0
    path = tmp_path / "telegram-receipts/work--run-new.json"
    before = path.read_bytes()
    assert module.main(["digest", "--job-id", "work", "--run-id", "run-new", "--resend"]) == 1
    assert len(calls) == 1 and path.read_bytes() == before


def test_delivery_failure_never_writes_a_success_receipt(sender, tmp_path, monkeypatch):
    module, calls = sender
    monkeypatch.setattr(module, "_post", lambda *a: (_ for _ in ()).throw(RuntimeError("Telegram returned HTTP 503")))
    assert module.main(["digest", "--job-id", "work", "--run-id", "run-new"]) == 1
    assert not (tmp_path / "telegram-receipts/work--run-new.json").exists()
