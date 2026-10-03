"""Execution permission failures must be durable and must never start a model turn."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from armada import capabilities as C, runner, util
from armada.engine import claude, codex
from armada.engine.base import RunResult
from armada.threads import Thread


@pytest.fixture
def realm(tmp_path):
    root = tmp_path / "realm"
    agent = root / "agents" / "dev"
    (agent / "jobs").mkdir(parents=True)
    (root / "realm.json").write_text(json.dumps({"name": "Test", "toolkit": {
        "extensions": [{"id": "granted"}, {"id": "revoked", "enabled": False}]}}), encoding="utf-8")
    (agent / "agent.json").write_text(json.dumps({"id": "dev", "allow_tools": True,
        "toolkit": {"extensions": ["granted", "revoked", "unknown"]}}), encoding="utf-8")
    (agent / "jobs" / "work.json").write_text(json.dumps({"id": "work", "prompt": "Test job"}), encoding="utf-8")
    return root


def test_policy_resolves_enabled_grants_and_ignores_unknown(realm):
    policy = C.execution_policy(realm, "dev")
    assert policy.allowed_mcp_ids == {"granted"}
    assert policy.denied_tools == ("mcp__revoked",)


@pytest.mark.parametrize("filename,contents", [
    ("realm.json", "{"),
    ("realm.json", '[]'),
    ("realm.json", '{"toolkit": {}, "toolkit": {}}'),
    ("realm.json", '{"toolkit": null}'),
    ("realm.json", '{"toolkit":{"extensions": "all"}}'),
    ("realm.json", '{"toolkit":{"extensions": [7]}}'),
    ("realm.json", '{"toolkit":{"extensions": [{"id":"x", "enabled":"false"}]}}'),
    ("realm.json", '{"toolkit":{"extensions": [{"id":"*"}]}}'),
    ("agent.json", '{"coordinator":"false"}'),
    ("agent.json", '{"toolkit":{"extensions": [7]}}'),
    ("agent.json", '{"toolkit":{"extensions": [{"id": "x"}, {"id": "X"}]}}'),
    ("agent.json", '{"allow_tools":"false"}'),
])
@pytest.mark.parametrize("entry", ["chat", "stream", "job", "inbox"])
@pytest.mark.parametrize("provider", ["claude", "codex"])
def test_invalid_policy_is_durable_without_any_engine_call(realm, monkeypatch, filename, contents, entry, provider):
    target = realm / filename if filename == "realm.json" else realm / "agents" / "dev" / filename
    target.write_text(contents, encoding="utf-8")
    monkeypatch.setattr(runner, "get_engine", lambda *a: pytest.fail("invalid policy reached engine selection"))
    events = []
    try:
        if entry == "chat":
            result = runner.chat(realm, "dev", "main", "Test", engine=provider, allow_tools=True)
        elif entry == "stream":
            result = runner.chat_stream(realm, "dev", "main", "Test", events.append, engine=provider, allow_tools=True)
            assert events[-1]["kind"] == "error"
        elif entry == "job":
            result = runner.run_job(realm, "dev", "work", engine=provider, allow_tools=True)
        else:
            result = runner.run_job_prompt(realm, "dev", "Test", engine=provider, allow_tools=True)
    except util.StateError as exc:
        # Realm lifecycle admission rejects malformed/unreadable state before creating a run.
        assert filename == "realm.json" and contents in ('{', '[]', '{"toolkit": {}, "toolkit": {}}', '{"toolkit": null}')
        assert "realm.json" in str(exc)
        assert target.read_text(encoding="utf-8") == contents
        assert not list((realm / "agents/dev/runs/.running").glob("*.json"))
        return
    assert result.get("ok") is False or result.get("status") == "error"
    adir = realm / "agents" / "dev"
    report = json.loads((adir / "runs" / "dev.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert report["status"] == "error" and "Capability policy" in report["summary"]
    if entry == "job":
        assert "Capability policy" in " ".join(report["app_errors"])
        assert Thread(adir, "main").render() == ""
    else:
        assert "Capability policy" in Thread(adir, report["thread"]).render()
    assert target.read_text(encoding="utf-8") == contents
    assert not (adir / "runs" / ".running" / "work.json").exists()


def test_unreadable_policy_is_not_empty_policy(realm, monkeypatch):
    original = Path.read_text
    def read(path, *args, **kwargs):
        if path == realm / "realm.json":
            raise PermissionError("fixture permission failure")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", read)
    monkeypatch.setattr(runner, "get_engine", lambda *a: pytest.fail("unreadable policy reached an engine"))
    with pytest.raises(util.StateError, match="realm.json"):
        runner.chat(realm, "dev", "main", "Test", allow_tools=True)


def test_revocation_during_context_assembly_is_applied_at_launch(realm, monkeypatch):
    class Fake:
        name = "claude"
        capabilities = claude.ClaudeEngine.capabilities
        def run(self, **kwargs):
            assert self.allowed_mcp_ids == frozenset()
            assert "mcp__granted" in kwargs["disallowed_tools"]
            return RunResult(ok=True, output="Denied connector stayed unavailable")
    original = runner.memory.assemble_core
    def core(*args):
        text = original(*args)
        (realm / "agents" / "dev" / "agent.json").write_text('{"id":"dev", "allow_tools":true}', encoding="utf-8")
        return text
    monkeypatch.setattr(runner.memory, "assemble_core", core)
    assert runner.chat(realm, "dev", "main", "Test", engine=Fake())["ok"]


@pytest.mark.parametrize("allowed", [frozenset(), frozenset({"granted"})])
def test_claude_gates_actual_inventory_including_new_servers(monkeypatch, allowed):
    engine = claude.ClaudeEngine()
    engine.allowed_mcp_ids = allowed
    monkeypatch.setattr(engine, "_launcher", lambda: ["claude"])
    calls = []
    def process(args, **kwargs):
        calls.append((args, kwargs))
        text = "2.1.263 (Claude Code)" if args[-1] == "--version" else (
            "Checking MCP server health…\n"
            "granted: command - ✓ Connected\n"
            "new-server: command - ✗ Failed to connect\n"
            "claude.ai Mail: https://private.invalid/?credential=secret - ✓ Connected\n")
        return SimpleNamespace(returncode=0, stdout=text, stderr="")
    monkeypatch.setattr(claude.subprocess, "run", process)
    args = engine._mcp_args([], cwd="agent-folder")
    blocked = json.loads(args[args.index("--settings") + 1])["deniedMcpServers"]
    assert {"serverName": "new-server"} in blocked
    assert {"serverName": "claude.ai Mail"} in blocked
    assert ({"serverName": "granted"} in blocked) == (not allowed)
    assert "mcp__new-server" in args
    assert ("mcp__*" in args) == (not allowed)
    assert "secret" not in " ".join(args)
    assert all(kwargs["cwd"] == "agent-folder" for _, kwargs in calls)


@pytest.mark.parametrize("inventory", ["", "Warning: failed config", "[]", "Checking MCP server health...",
    "x: command - Connected\nx: command - Connected", "No MCP servers configured.\nx: command - Connected"])
@pytest.mark.parametrize("stream", [False, True])
def test_claude_unverifiable_inventory_never_launches_model(monkeypatch, inventory, stream):
    engine = claude.ClaudeEngine()
    monkeypatch.setattr(engine, "_launcher", lambda: ["claude"])
    def process(args, **kwargs):
        assert "-p" not in args, "invalid inventory started a model turn"
        return SimpleNamespace(returncode=0, stdout="2.1.263" if args[-1] == "--version" else inventory, stderr="")
    monkeypatch.setattr(claude.subprocess, "run", process)
    monkeypatch.setattr(claude.subprocess, "Popen", lambda *a, **kw: pytest.fail("invalid inventory started a model"))
    result = (engine.run_stream if stream else engine.run)(system="", prompt="Test", allow_tools=True)
    assert not result.ok and "inventory" in result.error


@pytest.mark.parametrize("inventory", ["", "null", "{}", '[7]', '[{}]', '[{"name":"x", "enabled":"false"}]',
    '[{"name":"x"},{"name":"x"}]', '[{"name":42}]'])
def test_codex_unverifiable_inventory_never_launches_model(monkeypatch, inventory):
    engine = codex.CodexEngine()
    monkeypatch.setattr(engine, "_launcher", lambda: ["codex"])
    monkeypatch.setattr(engine, "_probe", lambda *a, **kw: SimpleNamespace(returncode=0, stdout=inventory))
    monkeypatch.setattr(codex.subprocess, "Popen", lambda *a, **kw: pytest.fail("invalid inventory started a model"))
    result = engine.run_stream(system="", prompt="Test", allow_tools=True)
    assert not result.ok and "inventory" in result.error


def test_codex_without_grants_blocks_every_effective_server(monkeypatch):
    engine = codex.CodexEngine()
    monkeypatch.setattr(engine, "_probe", lambda *a, **kw: SimpleNamespace(returncode=0,
        stdout='[{"name":"new-server"}, {"name":"revoked"}]'))
    args = engine._mcp_args(True, [])
    assert "mcp_servers.new-server.enabled=false" in args
    assert "mcp_servers.revoked.enabled=false" in args


@pytest.mark.parametrize("provider", ["claude", "codex"])
@pytest.mark.parametrize("entry", ["chat", "stream", "job", "inbox"])
def test_inventory_failure_reaches_the_user_and_run_record(realm, monkeypatch, provider, entry):
    engine = claude.ClaudeEngine() if provider == "claude" else codex.CodexEngine()
    monkeypatch.setattr(engine, "_launcher", lambda: [provider])
    def unavailable(*args, **kwargs):
        raise ValueError("Could not validate provider inventory; refusing a tool turn.")
    monkeypatch.setattr(engine, "_mcp_args", unavailable)
    monkeypatch.setattr(claude.subprocess, "Popen", lambda *a, **kw: pytest.fail("inventory failure launched a model"))
    if entry == "chat":
        result = runner.chat(realm, "dev", "main", "Test", engine=engine)
    elif entry == "stream":
        result = runner.chat_stream(realm, "dev", "main", "Test", lambda e: None, engine=engine)
    elif entry == "job":
        result = runner.run_job(realm, "dev", "work", engine=engine)
    else:
        result = runner.run_job_prompt(realm, "dev", "Test", engine=engine)
    assert result.get("ok") is False or result.get("status") == "error"
    adir = realm / "agents" / "dev"
    report = json.loads((adir / "runs" / "dev.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert report["status"] == "error" and "inventory" in report["summary"]
    if entry == "job":
        assert "inventory" in " ".join(report["app_errors"])
    else:
        assert "inventory" in Thread(adir, report["thread"]).render()


def test_claude_shell_shim_cannot_lose_permission_arguments(monkeypatch):
    engine = claude.ClaudeEngine()
    monkeypatch.setattr(engine, "_launcher", lambda: ["cmd", "/c", "claude.cmd"])
    monkeypatch.setattr(claude.subprocess, "run", lambda *a, **kw: pytest.fail("unsafe launcher used"))
    result = engine.run("", "Test", allow_tools=True)
    assert not result.ok and "launcher" in result.error
