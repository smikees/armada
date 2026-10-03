"""Finishing one run must never roll back another writer's memory, regardless of outcome."""
import json
from pathlib import Path
import threading

import pytest

from armada import memory, memory_boundary as M, runner
from armada.engine.base import RunResult
from armada.engine.contracts import ProviderCapabilities
from armada.threads import Thread


@pytest.fixture
def realm(tmp_path):
    root = tmp_path / "realm"
    for aid in ("a", "b"):
        ad = root / "agents" / aid
        (ad / "memory").mkdir(parents=True)
        (ad / "jobs").mkdir()
        (ad / "agent.json").write_text(json.dumps({"id": aid, "allow_tools": True}), encoding="utf-8")
        (ad / "jobs" / "work.json").write_text('{"id":"work","prompt":"Test"}', encoding="utf-8")
    (root / "memory").mkdir()
    (root / "realm.json").write_text('{"name":"Before"}', encoding="utf-8")
    return root


def invoke(root, entry, engine):
    if entry == "chat":
        return runner.chat(root, "a", "main", "Test", engine=engine)
    if entry == "stream":
        return runner.chat_stream(root, "a", "main", "Test", lambda ev: None, engine=engine)
    if entry == "job":
        return runner.run_job(root, "a", "work", engine=engine)
    return runner.run_job_prompt(root, "a", "Test", engine=engine)


class Cancelled(BaseException):
    """Exercise finally even when the engine bypasses an ordinary Exception handler."""


@pytest.mark.parametrize("provider", ["claude", "codex"])
@pytest.mark.parametrize("entry", ["chat", "stream", "job", "inbox"])
@pytest.mark.parametrize("outcome", ["success", "failure", "stopped", "exception", "cancelled"])
def test_concurrent_writers_survive_every_exit(realm, provider, entry, outcome):
    ad, bd = realm / "agents" / "a", realm / "agents" / "b"
    owner = realm / "memory" / "owner.md"
    other = bd / "memory" / "note.md"
    removed = bd / "memory" / "obsolete.md"
    for path in (owner, other, removed):
        path.write_text("Before", encoding="utf-8")
    memory.refresh_system_memory(realm, trigger="fixture")
    started, release = threading.Event(), threading.Event()
    errors, results, calls = [], [], []

    class WaitingEngine:
        name = provider
        capabilities = ProviderCapabilities(tool_denials=True)

        def run_stream(self, **kwargs):
            calls.append(kwargs)
            started.set()
            assert release.wait(15), "test did not release the engine"
            if outcome == "exception":
                raise RuntimeError("engine crashed")
            if outcome == "cancelled":
                raise Cancelled("engine cancelled")
            return RunResult(ok=outcome == "success", output="Done" if outcome == "success" else "",
                             error="" if outcome == "success" else "Stopped by owner" if outcome == "stopped" else "Failed")

    def run_a():
        try:
            results.append(invoke(realm, entry, WaitingEngine()))
        except BaseException as exc:
            errors.append(exc)

    worker = threading.Thread(target=run_a)
    worker.start()
    try:
        assert started.wait(10), errors

        class OtherEngine:
            name = provider
            capabilities = ProviderCapabilities(tool_denials=True)

            def run(self, **kwargs):
                other.write_text("B updated this", encoding="utf-8")
                (bd / "memory" / "new.md").write_text("B created this", encoding="utf-8")
                removed.unlink()
                return RunResult(ok=True, output="Saved")

        assert runner.chat(realm, "b", "main", "Remember", engine=OtherEngine())["ok"]
        owner.write_text("Owner updated this", encoding="utf-8")
        (realm / "realm.json").write_text('{"name":"After"}', encoding="utf-8")
        assert memory.refresh_system_memory(realm, trigger="concurrent")["changed"]
        expected = {p: p.read_bytes() for base in (realm / "memory", bd / "memory")
                    for p in base.rglob("*") if p.is_file()}
    finally:
        release.set()
        worker.join(15)
    assert not worker.is_alive()
    assert {p: p.read_bytes() for base in (realm / "memory", bd / "memory")
            for p in base.rglob("*") if p.is_file()} == expected
    assert not removed.exists()
    if outcome == "cancelled":
        assert len(errors) == 1 and isinstance(errors[0], Cancelled)
    else:
        assert errors == []
        assert bool(results[0].get("ok", results[0].get("status") == "ok")) == (outcome == "success")
    records = list((ad / "runs" / "memory-audits").glob("*.json"))
    assert len(records) == 1
    audit = json.loads(records[0].read_text(encoding="utf-8"))
    changed = {v["path"]: v["change"] for v in audit["changes"]}
    assert changed["agents/b/memory/note.md"] == "modified"
    assert changed["agents/b/memory/obsolete.md"] == "removed"
    assert changed["agents/b/memory/new.md"] == "added"
    assert changed["memory/owner.md"] == "modified"
    assert changed["memory/core-context.md"] == "modified"
    assert all(v["writer"] == "unknown" for v in audit["changes"])
    assert audit["write_attempts"] == []
    events = [v for v in Thread(ad, "job-run--work" if entry == "job" else "main")._messages() if v.get("type") == "memory_boundary"]
    assert len(events) == 1 and events[0]["meta"] == audit
    assert "writer is unknown" in events[0]["subtitle"]
    assert not (ad / "runs" / ".running" / "work.json").exists()
    if provider == "claude":
        assert set(M.claude_denials(realm, ad)) <= set(calls[0]["disallowed_tools"])
    else:
        assert audit["protection"] == "audit-only"
        assert not any(v.startswith("Edit(") for v in calls[0]["disallowed_tools"])


@pytest.mark.parametrize("entry", ["chat", "stream", "job", "inbox"])
@pytest.mark.parametrize("performed", [False, True])
def test_protected_write_attempts_are_reported_without_rollback_or_artifacts(realm, entry, performed):
    target = realm / "memory" / "note.md"
    target.write_text("Original", encoding="utf-8")

    class Engine:
        name = "claude"
        capabilities = ProviderCapabilities(tool_denials=True)

        def run_stream(self, on_event, **kwargs):
            # Models can request a file edit that the provider then refuses.
            on_event({"kind": "tool", "name": "Edit", "input": {"file_path": str(target)}})
            if performed:
                target.write_text("Changed", encoding="utf-8")
            return RunResult(ok=True, output="Done")

    invoke(realm, entry, Engine())
    assert target.read_text(encoding="utf-8") == ("Changed" if performed else "Original")
    ad = realm / "agents" / "a"
    messages = Thread(ad, "job-run--work" if entry == "job" else "main")._messages()
    assert all(not m.get("outputs") for m in messages)
    event = next(m for m in messages if m.get("type") == "memory_boundary")
    assert event["meta"]["write_attempts"] == ["memory/note.md"]
    assert event["meta"]["change_count"] == int(performed)
    assert "execution is not confirmed" in event["subtitle"]
    report = json.loads((ad / "runs" / "a.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert report["memory_boundary"] == event["meta"]


def test_own_memory_is_exempt_and_audit_is_idempotent(realm):
    ad = realm / "agents" / "a"
    th = Thread(ad, "main")
    audit = M.MemoryAudit(realm, ad, "claude")
    own = ad / "memory" / "own.md"
    own.write_text("Private memory contents", encoding="utf-8")
    audit.observe({"kind": "tool", "name": "Write", "input": {"file_path": str(own)}})
    (realm / "memory" / "other.md").write_text("Other private contents", encoding="utf-8")
    first = audit.record(th)
    assert audit.record(th) is first
    assert first["write_attempts"] == [] and first["change_count"] == 1
    assert len(th._messages()) == 1
    assert "contents" not in json.dumps(first)


def test_missing_and_new_memory_folders_are_observed(realm):
    ad = realm / "agents" / "a"
    (realm / "agents" / "empty").mkdir()
    assert realm / "agents" / "empty" / "memory" in M.protected_roots(realm, ad)
    audit = M.MemoryAudit(realm, ad)
    target = realm / "agents" / "new" / "memory" / "note.md"
    target.parent.mkdir(parents=True)
    target.write_text("New", encoding="utf-8")
    assert audit.protects(target)
    assert audit.protects("../new/memory/note.md")
    assert not audit.protects("../new/memory-like/note.md")
    assert audit.finish()["changes"] == [{"path": "agents/new/memory/note.md", "change": "added", "writer": "unknown"}]


def test_memory_path_comparison_follows_platform_case_rules(realm):
    ad = realm / "agents" / "a"
    audit = M.MemoryAudit(realm, ad)
    if Path("a") == Path("A"):
        assert not audit.protects(realm / "AGENTS" / "A" / "MEMORY" / "own.md")
        assert audit.protects(realm / "AGENTS" / "NEW" / "MEMORY" / "other.md")
    else:
        assert not audit.protects(realm / "AGENTS" / "NEW" / "MEMORY" / "other.md")


def test_incomplete_scan_reports_uncertainty_without_fabricating_deletion(realm, monkeypatch):
    target = realm / "memory" / "note.md"
    target.write_text("Keep", encoding="utf-8")
    audit = M.MemoryAudit(realm, realm / "agents" / "a")
    original = Path.open

    def denied(path, *args, **kwargs):
        if path == target:
            raise PermissionError("fixture")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", denied)
    report = audit.finish()
    assert report["changes"] == []
    assert report["scan_issues"] == ["Could not inspect memory path: memory/note.md"]


def test_bounded_scan_is_explicit_about_incomplete_coverage(realm, monkeypatch):
    monkeypatch.setattr(M, "_MAX_FILES", 1)
    report = M.MemoryAudit(realm, realm / "agents" / "a").finish()
    assert report["scan_issues"] and "incomplete" in report["scan_issues"][0]


def test_linked_memory_is_not_followed_and_coverage_is_reported(realm, monkeypatch):
    target = realm / "memory" / "linked"
    target.mkdir()
    (target / "secret.md").write_text("Private", encoding="utf-8")
    # Simulate the Windows junction API without requiring symlink privileges on this host.
    original = getattr(Path, "is_junction", lambda self: False)
    monkeypatch.setattr(Path, "is_junction", lambda p: p == target or original(p), raising=False)
    monkeypatch.setattr(M.os, "readlink", lambda p: "elsewhere")
    audit = M.MemoryAudit(realm, realm / "agents" / "a")
    assert "memory/linked/secret.md" not in audit.before
    assert audit.finish()["scan_issues"] == ["Linked memory path was not traversed: memory/linked"]


def test_claude_rules_use_absolute_paths_and_literal_globs(realm):
    special = realm / "agents" / "b[1]"
    special.mkdir()
    rules = M.claude_denials(realm, realm / "agents" / "a")
    root = realm.as_posix()
    if len(root) > 1 and root[1] == ":":
        root = "/" + root[0].lower() + root[2:]
    assert f"Edit(/{root}/memory/**)" in rules
    assert f"Edit(/{root}/agents/b/memory/**)" in rules
    assert f"Edit(/{root}/agents/b[[]1]/memory/**)" in rules
    assert not any("/agents/a/memory" in r for r in rules)
    assert all(r.startswith("Edit(//") for r in rules)


def test_failed_restriction_resolution_prevents_provider_execution(realm, monkeypatch):
    def fail(*args):
        raise PermissionError("cannot inspect other memories")

    class Engine:
        name = "claude"

        def run(self, **kwargs):
            pytest.fail("provider launched without required denials")

    monkeypatch.setattr(runner, "claude_denials", fail)
    result = invoke(realm, "chat", Engine())
    assert not result["ok"] and "memory restrictions" in result["output"]


def test_audit_records_are_never_output_artifacts(realm):
    ad = realm / "agents" / "a"
    cap = runner._TurnCapture(realm, ad, True)
    path = ad / "runs" / "memory-audits" / "other.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}", encoding="utf-8")
    cap.on_event({"kind": "tool", "name": "Write", "input": {"file_path": str(path)}})
    cap.finish()
    assert cap.outputs == []


def test_memory_observation_card_explains_evidence_and_escapes_paths():
    from armada.webui.threadsview import _event_card
    html = _event_card({"type": "memory_boundary", "title": "Memory observation", "subtitle": "Files preserved",
                       "meta": {"changes": [{"path": "<script>alert(1)</script>", "change": "modified"}],
                                "write_attempts": ['<img src=x onerror="alert(1)">'],
                                "scan_issues": ["Incomplete scan"], "limitation": "Shell not contained"}})
    assert "<details" in html and "<summary" in html
    assert "writer unknown" in html and "execution not confirmed" in html
    assert "Incomplete scan" in html and "Shell not contained" in html
    assert "<script>" not in html and "<img" not in html


def test_audit_write_failure_preserves_memory_and_engine_error(realm, monkeypatch, caplog):
    target = realm / "memory" / "note.md"

    class Engine:
        name = "codex"

        def run(self, **kwargs):
            target.write_text("Preserve this", encoding="utf-8")
            raise RuntimeError("original engine error")

    original = M.util.write_json_atomic

    def write(path, *args, **kwargs):
        if Path(path).parent.name == "memory-audits":
            raise PermissionError("audit fixture")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(M.util, "write_json_atomic", write)
    result = invoke(realm, "chat", Engine())
    assert not result["ok"] and "original engine error" in result["output"]
    assert target.read_text(encoding="utf-8") == "Preserve this"
    assert "Could not persist memory audit" in caplog.text
    event = next(m for m in Thread(realm / "agents" / "a", "main")._messages()
                 if m.get("type") == "memory_boundary")
    assert "audit file could not be saved" in event["subtitle"]
