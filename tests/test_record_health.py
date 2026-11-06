"""Synthetic damaged records must not become permissions or block healthy siblings."""
import datetime as dt
import hashlib
import json

import pytest

from armada import reader, records, runner, scheduler, util, webui


@pytest.fixture
def realm(tmp_path):
    (tmp_path / "realm.json").write_text('{"name":"Synthetic"}', encoding="utf-8")
    for aid in ("healthy", "broken"):
        ad = tmp_path / "agents" / aid
        (ad / "jobs").mkdir(parents=True)
        (ad / "agent.json").write_text(json.dumps({"id": aid, "display": aid.title()}), encoding="utf-8")
        (ad / "jobs" / "daily.json").write_text(json.dumps({
            "id": "daily", "schedule": "daily 09:00", "prompt": "Synthetic", "allow_tools": False}), encoding="utf-8")
    return tmp_path


BAD = [b'{', b'[]', b'null', b'{"display":[]}', b'{"enabled":"yes"}',
       b'{"id":"broken","id":"broken"}', b'\xff', b'{"timeout":NaN}']


@pytest.mark.parametrize("raw", BAD)
@pytest.mark.parametrize("kind", ["agent", "job"])
def test_damaged_record_does_not_break_healthy_views(realm, raw, kind):
    path = records.target(realm, "broken", "daily" if kind == "job" else "")
    path.write_bytes(raw)
    view = reader.read(realm)
    broken = next(a for a in view.agents if a.id == "broken")
    assert (broken.record_error if kind == "agent" else broken.jobs[0].record_error)
    assert "Healthy" in webui.render_agent(view, realm, "healthy")
    assert "Needs repair" in webui.render_job(view, realm, "broken", "daily")
    assert "Needs repair" in webui.render_realm_page(view, realm, "jobs")
    for page in ("ministers", "memory", "goals", "skills", "artefacts", "inbox"):
        webui.render_realm_page(view, realm, page)
    webui.render_dashboard(view, realm)
    assert path.read_bytes() == raw


@pytest.mark.parametrize("engine", ["claude", "codex", "gemini"])
def test_damaged_agent_stops_before_engine_selection(realm, monkeypatch, engine):
    records.target(realm, "broken").write_text('{"display":[]}', encoding="utf-8")
    monkeypatch.setattr(runner, "_select_engine", lambda *a, **k: pytest.fail("engine selected"))
    from armada.capabilities import CapabilityPolicyError
    with pytest.raises(CapabilityPolicyError, match="agent.json"):
        runner._prepare_agent_run(realm, "broken", engine, False)


def test_damaged_command_owner_stops_before_process(realm, monkeypatch):
    records.target(realm, "broken").write_bytes(b'[]')
    from armada.engine import process
    monkeypatch.setattr(process, "supervise_command", lambda *a, **k: pytest.fail("command started"))
    with pytest.raises(util.StateError):
        runner._run_command(realm, "broken", "daily", {"run": ["echo", "bad"]},
                            realm / "agents" / "broken")


def test_scheduler_holds_bad_record_and_keeps_healthy_work(realm):
    records.target(realm, "broken", "daily").write_bytes(b'{')
    result = scheduler.tick(realm, at=dt.datetime(2026, 11, 5, 9), dry_run=True)
    assert any(r["agent"] == "broken" and r["status"] == "held" for r in result)
    assert any(r["agent"] == "healthy" and r["status"] == "would-fire" for r in result)


@pytest.mark.parametrize("bad", ['[]', '{"tokens":{"total":"oops"}}', '{"task":[]}', '{', '{"ts":NaN}', '{"ts":"2026-11-05garbage"}'])
def test_damaged_history_is_visible_and_never_replayed(realm, bad, monkeypatch):
    class FixedDateTime(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 5, 9, tzinfo=tz)
    monkeypatch.setattr(reader.datetime, "datetime", FixedDateTime)
    path = realm / "agents" / "broken" / "runs" / "broken.jsonl"
    path.parent.mkdir()
    raw = ('{"task":"daily","ts":"2026-11-05T08:00:00","tokens":{"total":12}}\n' + bad).encode()
    path.write_bytes(raw)
    view = reader.read(realm)
    broken = next(a for a in view.agents if a.id == "broken")
    assert broken.history_errors and broken.tokens_30d == 12
    assert any("incomplete" in g.label for g in view.gaps)
    result = scheduler.tick(realm, at=dt.datetime(2026, 11, 5, 9), dry_run=True)
    assert any(r["agent"] == "broken" and r["status"] == "held" for r in result)
    assert any(r["agent"] == "healthy" and r["status"] == "would-fire" for r in result)
    assert path.read_bytes() == raw


def test_owner_repair_preserves_exact_bytes_and_audit_receipt(realm):
    path = records.target(realm, "broken")
    raw = b'\xffbad\r\n'
    path.write_bytes(raw)
    result = records.repair(realm, "broken", "", '{"id":"broken","write_scope":[]}', hashlib.sha256(raw).hexdigest())
    assert result["ok"]
    backup = realm / result["backup"]
    assert backup.read_bytes() == raw
    assert records.read(path, "agent")["write_scope"] == []
    receipt = json.loads(backup.with_name("repair.json").read_text())
    assert receipt["actor"] == "owner"
    assert receipt["original_sha256"] == hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize("replacement", ['[]', '{"display":[]}', '{"tool_policy":[]}', '{"id":"broken","id":"broken"}', '{"schema_version":999999}'])
def test_invalid_repair_preserves_original(realm, replacement):
    path = records.target(realm, "broken")
    path.write_bytes(b'{')
    with pytest.raises((OSError, ValueError)):
        records.repair(realm, "broken", "", replacement, hashlib.sha256(b'{').hexdigest())
    assert path.read_bytes() == b'{'


def test_repair_refuses_stale_review_and_traversal(realm):
    path = records.target(realm, "broken")
    original = path.read_bytes()
    with pytest.raises(util.StateError, match="changed"):
        records.repair(realm, "broken", "", '{}', "outdated")
    with pytest.raises(ValueError):
        records.repair(realm, "../healthy", "", '{}', "outdated")
    assert path.read_bytes() == original


def test_failed_replacement_keeps_original_and_recovery_evidence(realm, monkeypatch):
    path = records.target(realm, "broken")
    path.write_bytes(b'{')
    replace = util._replace_retrying
    def fail_final(source, destination, *args, **kwargs):
        if destination == path:
            raise OSError("synthetic sharing violation")
        return replace(source, destination, *args, **kwargs)
    monkeypatch.setattr(util, "_replace_retrying", fail_final)
    with pytest.raises(OSError, match="sharing"):
        records.repair(realm, "broken", "", '{}', hashlib.sha256(b'{').hexdigest())
    assert path.read_bytes() == b'{'
    evidence = list((realm / ".armada/record-repairs").glob("*/original.bin"))
    assert len(evidence) == 1 and evidence[0].read_bytes() == b'{'
    assert evidence[0].with_name("repair.json").exists()


def test_ordinary_editor_cannot_reset_damaged_record(realm):
    path = records.target(realm, "broken")
    path.write_text('{"display":[]}', encoding="utf-8")
    original = path.read_bytes()
    with pytest.raises(util.StateError):
        util.mutate_json(path, lambda data: data.update(display="Replaced"))
    assert path.read_bytes() == original


def test_newer_schema_is_not_downgraded_by_repair(realm):
    path = records.target(realm, "broken")
    raw = b'{"schema_version":999999}'
    path.write_bytes(raw)
    with pytest.raises(util.UnsupportedSchemaError):
        records.repair(realm, "broken", "", '{}', hashlib.sha256(raw).hexdigest())
    assert path.read_bytes() == raw


def test_repair_refuses_reparse_components(realm, monkeypatch):
    from pathlib import Path
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda p: p.name == "broken" or original(p))
    with pytest.raises(ValueError, match="symlinks"):
        records.target(realm, "broken")


def test_owner_http_repair_is_authenticated_and_bound_to_reviewed_record(realm):
    import urllib.error
    import urllib.request
    from golden_support import ServedRealm
    path = records.target(realm, "broken", "daily")
    raw = b'{'
    path.write_bytes(raw)
    with ServedRealm(str(realm)) as server:
        assert "Needs repair" in server.get("/job/broken/daily")
        assert "Healthy" in server.get("/agent/healthy")
        body = {"agent": "broken", "job": "daily", "replacement": '{"id":"daily","enabled":false}',
                "expected_sha256": hashlib.sha256(raw).hexdigest(), "reviewed": True}
        request = urllib.request.Request(server.base + "/api/repair-record", data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"}, method="POST")
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request, timeout=5)
        assert error.value.code == 401
        for extra, status in (({"Origin": "https://untrusted.invalid"}, 403),
                              ({"X-Armada-Realm": "wrong-realm"}, 409)):
            request = urllib.request.Request(server.base + "/api/repair-record", data=json.dumps(body).encode(),
                headers={**server.auth_headers(), "Content-Type": "application/json", **extra}, method="POST")
            with pytest.raises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(request, timeout=5)
            assert error.value.code == status
            assert path.read_bytes() == raw
        assert not server.post("/api/repair-record", {**body, "reviewed": False})["ok"]
        assert server.post("/api/repair-record", body)["ok"]
        assert "Record needs repair" not in server.get("/job/broken/daily")
        assert not server.post("/api/repair-record", body)["ok"]
    assert records.read(path, "job")["enabled"] is False


def test_legacy_free_text_budget_and_default_timeout_are_valid(realm):
    path = records.target(realm, "healthy", "daily")
    path.write_text('{"budget":"10K token","timeout":0}', encoding="utf-8")
    assert records.read(path, "job")["budget"] == "10K token"


@pytest.mark.parametrize("value", ["bad", None, True, 4])
def test_invalid_retry_configuration_shows_repair_instead_of_breaking_detail(realm, value):
    path = records.target(realm, "broken", "daily")
    raw = json.dumps({"id": "daily", "retries": value}).encode()
    path.write_bytes(raw)
    view = reader.read(realm)
    assert "Needs repair" in webui.render_job(view, realm, "broken", "daily")
    assert "Healthy" in webui.render_agent(view, realm, "healthy")
    assert path.read_bytes() == raw


def test_bad_inbox_recipient_does_not_consume_mail_or_block_siblings(realm, monkeypatch):
    from armada import inbox
    records.target(realm, "broken").write_bytes(b'{')
    monkeypatch.setattr(inbox, "enabled", lambda *a: True)
    monkeypatch.setattr(inbox, "has_mail", lambda *a: True)
    monkeypatch.setattr(inbox, "due", lambda *a: True)
    monkeypatch.setattr(inbox, "next_batch", lambda *a: pytest.fail("damaged recipient read a batch"))
    assert runner.run_inbox(realm, "broken")["reason"] == "record-hold"
    called = []
    def run(root, agent, **kw):
        called.append(agent)
        return {"ok": True, "handled": 1}
    monkeypatch.setattr(runner, "run_inbox", run)
    result = runner.dispatch_inboxes(realm)
    assert called == ["healthy"] and result["handled"] == 1
    assert result["blocked"][0]["agent"] == "broken"


@pytest.mark.parametrize("failure", ["encoding", "access"])
def test_unreadable_history_is_not_treated_as_no_previous_run(realm, monkeypatch, failure):
    from pathlib import Path
    path = realm / "agents/broken/runs/broken.jsonl"
    path.parent.mkdir()
    path.write_bytes(b'\xff')
    if failure == "access":
        read = Path.read_text
        def denied(p, *args, **kwargs):
            if p == path:
                raise PermissionError("synthetic denial")
            return read(p, *args, **kwargs)
        monkeypatch.setattr(Path, "read_text", denied)
    view = reader.read(realm)
    assert next(a for a in view.agents if a.id == "broken").history_errors
    with pytest.raises(util.StateError, match="held"):
        scheduler.ran_today(realm, "broken", "daily", "2026-11-05")
    assert path.read_bytes() == b'\xff'
