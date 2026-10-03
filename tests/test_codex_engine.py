"""The second provider must preserve context, event capture and capability boundaries."""
import io
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from armada.engine import get_engine, engine_for
from armada.engine import codex
from armada.engine.base import RunResult, Usage
from armada import runner, models, model
from armada.util import write_json_atomic


@pytest.fixture
def realm(tmp_path):
    root = tmp_path / "realm"
    agent = root / "agents" / "dev"
    (agent / "jobs").mkdir(parents=True)
    write_json_atomic(root / "realm.json", {"name": "Test", "default_model": "claude-sonnet-5",
                                            "providers": ["claude", "codex"]})
    write_json_atomic(agent / "agent.json", {"id": "dev", "display": "Developer", "model": "gpt-test"})
    write_json_atomic(agent / "jobs" / "work.json", {"id": "work", "prompt": "Do the job", "model": "claude-sonnet-5"})
    (agent / "soul.md").write_text("Keep the shared context.", encoding="utf-8")
    return root


def test_selection_preserves_mixed_agent_and_job_models(realm):
    assert engine_for(realm) == "claude"
    assert engine_for(realm, "dev") == "codex"
    assert engine_for(realm, "dev", {"model": "claude-sonnet-5"}) == "claude"
    assert engine_for(realm, "dev", override="mock") == "mock"
    assert engine_for(realm, {"model": "codex:default"}) == "codex"
    assert isinstance(get_engine("codex"), codex.CodexEngine)
    assert runner._cli_model("gpt-test", realm) == "gpt-test"


def test_combined_picker_uses_local_catalogue_and_keeps_default(realm, monkeypatch):
    monkeypatch.setattr(codex, "cached_models", lambda: [{"slug": "gpt-test", "display_name": "GPT Test", "context_window": 272000}])
    options = dict(models.options(realm))
    assert "claude-sonnet-5" in options
    assert options["gpt-test"] == "OpenAI · GPT Test"
    assert "codex:default" in options
    assert model.context_window_tokens("gpt-test") == 272000
    write_json_atomic(realm / "realm.json", {"providers": ["codex"]})
    assert set(dict(models.options(realm))) == {"gpt-test", "codex:default"}


def test_model_cache_never_exposes_hidden_models(tmp_path, monkeypatch):
    monkeypatch.setattr(codex, "codex_home", lambda: tmp_path)
    write_json_atomic(tmp_path / "models_cache.json", {"models": [
        {"slug": "gpt-test", "visibility": "list"}, {"slug": "internal", "visibility": "hide"}]})
    assert [m["slug"] for m in codex.cached_models()] == ["gpt-test"]


def test_launcher_prefers_native_desktop_cli_over_npm_shim(tmp_path, monkeypatch):
    native = tmp_path / "OpenAI" / "Codex" / "bin" / "desktop-build" / "codex.exe"
    native.parent.mkdir(parents=True)
    native.touch()
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("CODEX_INSTALL_DIR", raising=False)
    monkeypatch.setattr(codex.shutil, "which", lambda name: str(tmp_path / "codex.cmd"))
    assert codex.CodexEngine()._launcher() == [str(native)]


def test_mcp_allowlist_covers_unlisted_and_disabled_servers(monkeypatch):
    engine = codex.CodexEngine()
    engine.allowed_mcp_ids = {"granted"}
    calls = []
    def probe(args, cwd=None):
        calls.append((args, cwd))
        return SimpleNamespace(returncode=0, stdout=json.dumps([
            {"name": "granted", "enabled": True}, {"name": "private", "enabled": True},
            {"name": "desktop-managed", "enabled": False}]))
    monkeypatch.setattr(engine, "_probe", probe)
    args = engine._args("gpt-test", True, "high", [], cwd="agent-folder")
    assert "mcp_servers.private.enabled=false" in args
    assert "mcp_servers.granted.enabled=false" not in args
    assert "mcp_servers.desktop-managed.enabled=false" not in args
    assert calls[0][1] == "agent-folder"
    assert "features.plugins=false" in calls[0][0]
    assert "mcp_servers.granted.enabled=false" in engine._args("gpt-test", True, None, ["mcp__granted"])
    args = engine._args("codex:default", False, None, [])
    assert "mcp_servers.granted.enabled=false" in args
    assert "--model" not in args
    assert "features.shell_tool=false" in args
    assert "read-only" in args
    assert "--dangerously-bypass-approvals-and-sandbox" not in args


def test_granted_mcp_turn_prompts_for_deferred_tool_discovery(monkeypatch):
    engine = codex.CodexEngine()
    engine.app_server_streaming = False
    engine.allowed_mcp_ids = {"broker"}
    monkeypatch.setattr(engine, "_launcher", lambda: ["codex"])
    monkeypatch.setattr(engine, "_mcp_args", lambda *a, **kw: [])
    prompts = []
    def fake_supervise(*args, **kwargs):
        prompts.append(kwargs["prompt"])
        return SimpleNamespace(error="", cancelled=False)
    monkeypatch.setattr(codex, "supervise", fake_supervise)
    engine.run_stream("system", "request", allow_tools=True)
    engine.run_stream("system", "request", allow_tools=False)
    assert "Use Codex tool search if available" in prompts[0]
    assert "# Required MCP tool discovery" in prompts[0]
    assert "# Required MCP tool discovery" not in prompts[1]


def test_armada_verbosity_maps_to_codex_native_override(monkeypatch):
    engine = codex.CodexEngine()
    monkeypatch.setattr(engine, "_mcp_args", lambda *a, **kw: [])
    for level, native in (("terse", "low"), ("brief", "low"),
                          ("standard", "medium"), ("full", "high")):
        args = engine._args("gpt-6-sol", False, None, [], verbosity=level)
        assert f'model_verbosity="{native}"' in args
    assert codex._verbosity_args("codex:default", "full") == []
    assert codex._verbosity_args("gpt-6-sol", None) == []


def test_failed_inventory_and_sealed_turns_fail_closed(monkeypatch):
    engine = codex.CodexEngine()
    monkeypatch.setattr(engine, "_launcher", lambda: ["codex"])
    monkeypatch.setattr(engine, "_probe", lambda *a, **kw: SimpleNamespace(returncode=1, stdout=""))
    assert not engine.run("", "", only_tools=["WebFetch"]).ok
    assert not engine.run("", "", max_budget_usd=1).ok
    result = engine.run("", "", allow_tools=True)
    assert not result.ok and "capability gating" in result.error


def test_unsupported_effort_is_reported_instead_of_silently_changed(monkeypatch):
    monkeypatch.setattr(codex, "cached_models", lambda: [{"slug": "gpt-test",
        "supported_reasoning_levels": [{"effort": "low"}, {"effort": "high"}]}])
    engine = codex.CodexEngine()
    monkeypatch.setattr(engine, "_launcher", lambda: ["codex"])
    result = engine.run("", "", model="gpt-test", effort="max", allow_tools=True)
    assert not result.ok
    assert "does not support effort 'max'" in result.error
    assert "low, high" in result.error


def test_stream_maps_usage_and_artifacts_once(tmp_path):
    events = []
    state = codex._Stream(events.append, "gpt-test", str(tmp_path))
    message = {"type": "item.completed", "item": {"id": "reply", "type": "agent_message", "text": "Done"}}
    state.accept({"type": "thread.started", "thread_id": "abc"})
    state.accept(message)
    state.accept(message)
    state.accept({"type": "item.completed", "item": {"id": "file", "type": "file_change", "status": "completed",
                   "changes": [{"path": "report.md", "kind": "add"}]}})
    state.accept({"type": "item.started", "item": {"id": "mcp", "type": "mcp_tool_call", "server": "docs", "tool": "read", "arguments": {"id": 1}}})
    state.accept({"type": "turn.completed", "usage": {"input_tokens": 100, "cached_input_tokens": 60, "output_tokens": 20}})
    assert state.texts == ["Done"]
    assert state.usage.input == 40 and state.usage.cache_read == 60 and state.usage.total == 120
    assert any(e.get("input", {}).get("file_path") == str(tmp_path / "report.md") for e in events)
    assert any(e.get("name") == "mcp__docs__read" for e in events)
    state.accept({"type": "turn.failed", "error": {"message": "quota exhausted"}})
    assert state.error == "quota exhausted"


def test_large_unicode_prompt_uses_stdin_and_rejects_incomplete_exit(tmp_path, monkeypatch):
    engine = codex.CodexEngine()
    # A real local child process exercises pipe feeding/draining; no model or network call.
    child = tmp_path / "child.py"
    child.write_text('import sys,json\np=sys.stdin.read()\n'
                     'sys.stderr.write("x"*100000)\n'
                     'print(json.dumps({"type":"item.completed","item":{"id":"r","type":"agent_message","text":str(len(p))}}))\n', encoding="utf-8")
    monkeypatch.setattr(engine, "_launcher", lambda: [sys.executable, str(child)])
    monkeypatch.setattr(engine, "_args", lambda *a, **kw: [])
    system = "Agent memory αβγ\n" * 12000
    result = engine.run(system, "owner message", allow_tools=True, timeout=10)
    assert not result.ok and "before completing" in result.error
    assert int(result.output) > len(system)


def test_timeout_works_even_without_stdout(tmp_path, monkeypatch):
    engine = codex.CodexEngine()
    child = tmp_path / "child.py"
    child.write_text('import time\ntime.sleep(30)\n', encoding="utf-8")
    monkeypatch.setattr(engine, "_launcher", lambda: [sys.executable, str(child)])
    monkeypatch.setattr(engine, "_args", lambda *a, **kw: [])
    result = engine.run("", "", allow_tools=True, timeout=0.2)
    assert not result.ok and "timed out" in result.error


def test_runner_uses_agent_model_and_preserves_history(realm, monkeypatch):
    calls = []
    class Fake:
        name = "codex"
        def run_stream(self, **kwargs):
            calls.append(kwargs)
            return RunResult(ok=True, output="Reply", model=kwargs.get("model") or "gpt-test", usage=Usage(output=3))
    chosen = []
    def factory(name):
        chosen.append(name)
        engine = Fake()
        engine.name = name
        return engine
    monkeypatch.setattr(runner, "get_engine", factory)
    runner.chat_stream(realm, "dev", "main", "First request", lambda e: None)
    runner.chat_stream(realm, "dev", "main", "Second request", lambda e: None)
    assert chosen == ["codex", "codex"]
    assert calls[1]["model"] == "gpt-test"
    assert calls[1]["verbosity"] == "standard"
    assert "First request" in calls[1]["prompt"] and "Second request" in calls[1]["prompt"]
    assert "Keep the shared context." in calls[1]["system"]
    runner.run_job(realm, "dev", "work", engine="auto")
    assert chosen[-1] == "claude"
    assert calls[-1]["model"] == "claude-sonnet-5"


def test_compaction_failure_keeps_history(tmp_path):
    from armada.threads import Thread
    thread = Thread(tmp_path, "main")
    for i in range(8):
        thread.append(f"Question {i}", f"Answer {i}")
    before = thread.render()
    engine = SimpleNamespace(run=lambda **kw: RunResult(ok=False, error="signed out"))
    assert not thread.compact_if_needed(engine, threshold_chars=1)
    assert thread.render() == before


def test_one_disconnected_provider_does_not_block_the_other(realm, monkeypatch):
    from armada import preflight
    monkeypatch.setattr(preflight, "engine_check", lambda name: preflight._check(
        "engine", name, name == "codex", "connected" if name == "codex" else "signed out"))
    report = preflight.run(realm)
    assert not any(c["id"] == "engine" for c in report["blocking"])
    assert any(c["id"] == "engine" and c["label"] == "claude" for c in report["warnings"])


def test_settings_show_both_login_controls_without_probing(tmp_path, monkeypatch):
    from tests.golden_support import build_fixture
    from armada import reader, webui
    root = build_fixture(tmp_path / "fixture")
    monkeypatch.setattr(codex.CodexEngine, "_probe", lambda *a, **kw: pytest.fail("render must not probe CLI"))
    html = webui.render_settings(reader.read(root), root, False, "", [])
    assert 'id="provider-codex-status"' in html and 'id="provider-claude-status"' in html
    assert 'value="codex"  disabled' not in html


def test_unknown_mcp_key_fails_instead_of_leaking_access(monkeypatch):
    engine = codex.CodexEngine()
    monkeypatch.setattr(engine, "_probe", lambda *a, **kw: SimpleNamespace(
        returncode=0, stdout='[{"name":"server.with.dots", "enabled":true}]'))
    with pytest.raises(ValueError, match="Rename Codex MCP"):
        engine._mcp_args(False, [])
