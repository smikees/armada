"""Draft jobs cannot mutate production settings/files or inherit publication tools."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest

from armada import dry_runs, inspection, job_history, util
from armada.engine.base import EngineAdapter, RunResult, Usage
from armada.engine.contracts import ProviderCapabilities
from armada.managed_tools import ManagedTools


@pytest.fixture
def realm(tmp_path, monkeypatch):
    root = tmp_path / "realm"
    root.mkdir()
    util.write_json_atomic(root / "realm.json", {"name": "Synthetic crew", "workspace": str(root), "timezone": "local"})
    for agent in ("writer", "inspector"):
        ad = root / "agents" / agent
        (ad / "jobs").mkdir(parents=True)
        util.write_json_atomic(ad / "agent.json", {"id": agent, "display": agent, "model": "gpt-6-sol"})
        (ad / "mandate.md").write_text("Review synthetic test data.")
    util.write_json_atomic(root / "agents/writer/jobs/digest.json", {
        "id": "digest", "name": "Synthetic digest", "model": "gpt-6-sol", "enabled": False,
        "prompt": "Read input.json. Write and publish today's report.", "cron": "0 9 * * *"})
    (root / "input.json").write_text('{"amount":"12.34"}')
    monkeypatch.setattr("armada.models.options", lambda root: [("gpt-6-sol", "OpenAI · Sol"), ("claude-sonnet-5", "Anthropic · Sonnet")])
    return root


class DraftEngine(EngineAdapter):
    name = "mock"
    capabilities = ProviderCapabilities(streaming=True, raw_tool_results=True)

    def doctor(self):
        return True, "Synthetic engine"

    def run(self, **kwargs):
        return self.run_stream(**kwargs)

    def run_stream(self, system, prompt, *, model=None, env=None, on_event=None, on_proc=None, **kwargs):
        assert not self.allowed_mcp_ids and not self.writable_roots and not self.network_access
        assert "DRY RUN" in system
        assert "required_destinations\": []" in prompt
        assert env["ARMADA_DRY_RUN"] == "1"
        self.managed_tools.call("read_input", {"path": str(self.managed_tools.root / "input.json")})
        for tool in ("send", "publish", "run_command", "start_dry_run"):
            with pytest.raises(ValueError):
                self.managed_tools.call(tool, {})
        with pytest.raises(ValueError):
            self.managed_tools.call("write_draft", {"path": str(self.managed_tools.root / "input.json"), "content": "changed"})
        path = self.managed_tools.call("write_draft", {"path": "report.md", "content": "Draft: 12.34"})["path"]
        data = {"schema_version": 1, "run_id": env["ARMADA_RUN_ID"], "execution": "completed",
            "audit_outcome": "clear", "delivery": [], "evidence": {"outputs": [{"path": path, "required": True}],
                "findings": [], "missing_inputs": [], "operational_errors": [], "risk_gates": []}}
        return RunResult(ok=True, output="Synthetic draft.\n<armada_job_result>" + json.dumps(data) + "</armada_job_result>",
                         model=model, usage=Usage(input=10, output=5, cost_usd=0.01))


def finished(root, run):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        info = dry_runs.read(root, run["agent"], run["job"], run["run_id"])
        if info["status"] not in ("queued", "running"):
            # Wait for accounting and admission cleanup, not just the terminal metadata write.
            with dry_runs._LOCK:
                if (str(root.resolve()), run["run_id"]) not in dry_runs._ACTIVE:
                    return info
        time.sleep(.025)
    pytest.fail("Synthetic dry run did not finish")


def test_dry_run_is_separate_disabled_job_explicit_model_and_temporary_outputs(realm):
    jp = realm / "agents/writer/jobs/digest.json"
    before = jp.read_bytes()
    run = dry_runs.start(realm, "writer", "digest", "claude-sonnet-5", engine=DraftEngine())
    info = finished(realm, run)
    assert info["status"] == "completed" and info["actual_model"] == "claude-sonnet-5"
    assert jp.read_bytes() == before
    assert (realm / "input.json").read_text() == '{"amount":"12.34"}'
    assert not job_history.reports(realm / "agents/writer", "digest")
    accounting = job_history.reports(realm / "agents/writer")
    assert len(accounting) == 1 and accounting[0]["kind"] == "dry_run"
    from armada import reader
    assert next(a for a in reader.read(realm).agents if a.id == "writer").status == "green"
    assert info["keep_days"] == 7
    for file in info["files"]:
        assert Path(file["path"]).is_relative_to(Path(run["output_dir"]))
        assert hashlib.sha256(Path(file["path"]).read_bytes()).hexdigest() == file["sha256"]
    assert {f["name"] for f in info["files"]} == {"report.md", "final-answer.md"}


def test_invalid_model_does_not_create_a_run(realm):
    with pytest.raises(ValueError, match="available model"):
        dry_runs.start(realm, "writer", "digest", "made-up")
    assert dry_runs.listing(realm, "writer", "digest") == []


def test_history_retries_transient_windows_sharing_but_preserves_persistent_errors(realm, monkeypatch):
    run = dry_runs.start(realm, "writer", "digest", "gpt-6-sol", engine=DraftEngine())
    finished(realm, run)
    original = util.read_json_state
    denied = [True, True, False]
    def read(path, **kwargs):
        if Path(path).name == "run.json" and denied and denied.pop(0):
            raise util.StateError("Temporary sharing violation") from PermissionError("synthetic sharing")
        return original(path, **kwargs)
    monkeypatch.setattr(util, "read_json_state", read)
    assert dry_runs.read(realm, "writer", "digest", run["run_id"])["status"] == "completed"
    denied[:] = [True] * 8
    with pytest.raises(util.StateError, match="sharing"):
        dry_runs.read(realm, "writer", "digest", run["run_id"])
    def corrupt(*args, **kwargs):
        raise util.StateError("Corrupt state")
    monkeypatch.setattr(util, "read_json_state", corrupt)
    with pytest.raises(util.StateError, match="Corrupt state"):
        dry_runs.read(realm, "writer", "digest", run["run_id"])


@pytest.mark.parametrize("path", ["../production.txt", "nested/../../production.txt", "NUL", "draft.txt:stream", "draft. "])
def test_draft_paths_are_contained_and_reject_windows_aliases(realm, path):
    tools = ManagedTools(realm, "writer", output=realm / "drafts")
    with pytest.raises(ValueError):
        tools.call("write_draft", {"path": path, "content": "unsafe"})
    assert not (realm / "production.txt").exists()


def test_atomic_draft_write_preserves_existing_data_when_replace_fails(realm, monkeypatch):
    tools = ManagedTools(realm, "writer", output=realm / "drafts")
    tools.call("write_draft", {"path": "draft.md", "content": "old"})
    def fail(*args):
        raise OSError("synthetic rename failure")
    monkeypatch.setattr("os.replace", fail)
    with pytest.raises(OSError, match="rename failure"):
        tools.call("write_draft", {"path": "draft.md", "content": "new"})
    assert (realm / "drafts/draft.md").read_text() == "old"


def approve_inspector(root):
    util.mutate_json(root / "agents/inspector/agent.json", lambda cfg: cfg.update(is_inspector=True))
    inspection.approve(root, "inspector", True)


def test_inspector_cannot_self_authorize_and_revocation_is_immediate(realm):
    util.mutate_json(realm / "agents/inspector/agent.json", lambda cfg: cfg.update(is_inspector=True))
    tools = ManagedTools(realm, "inspector", inspector=True)
    with pytest.raises(ValueError, match="disabled"):
        tools.call("list_jobs", {})
    inspection.approve(realm, "inspector", True)
    assert tools.call("list_jobs", {})[0]["job"] == "digest"
    assert {m["id"] for m in tools.call("list_models", {})} == {"gpt-6-sol", "claude-sonnet-5"}
    inspection.approve(realm, "inspector", False)
    with pytest.raises(ValueError, match="disabled"):
        tools.call("list_models", {})
    inspection.approve(realm, "inspector", True)
    with tools:
        assert tools.call("list_jobs", {})
    with pytest.raises(ValueError, match="expired"):
        tools.call("list_jobs", {})


def test_inspector_reads_registered_artifacts_without_generic_foreign_file_access(realm):
    approve_inspector(realm)
    from armada.threads import Thread
    artifact = realm / "approved-report.txt"
    artifact.write_text("Production result")
    th = Thread(realm / "agents/writer", "main")
    turn = th.begin_turn("Make a report")
    th.complete_turn(turn, "Done", outputs=[{"path": str(artifact), "name": artifact.name}])
    tools = ManagedTools(realm, "inspector", inspector=True)
    items = tools.call("list_artifacts", {})
    assert len(items) == 1 and items[0]["agent"] == "writer"
    assert tools.call("read_artifact", {"id": items[0]["id"]})["content"] == "Production result"
    for name in ("read_input", "run_command", "publish", "run_job", "save_job"):
        with pytest.raises(ValueError):
            tools.call(name, {"path": str(artifact)})
    with pytest.raises(ValueError):
        tools.call("write_draft", {"path": str(artifact), "content": "changed"})
    tools.call("write_draft", {"path": "review.md", "content": "Compare model outputs"})
    assert artifact.read_text() == "Production result"


def test_inspector_can_trigger_foreign_disabled_jobs_but_only_dry_runs(realm, monkeypatch):
    approve_inspector(realm)
    monkeypatch.setattr("armada.engine.get_engine", lambda name: DraftEngine())
    tools = ManagedTools(realm, "inspector", inspector=True)
    run = tools.call("start_dry_run", {"agent": "writer", "job": "digest", "model": "gpt-6-sol"})
    finished(realm, run)
    result = tools.call("get_dry_run", {"agent": "writer", "job": "digest", "run_id": run["run_id"]})
    assert result["run"]["requested_by"] == "inspector"
    assert any(f["name"] == "report.md" for f in result["files"])
    assert tools.call("read_dry_run_file", {"agent": "writer", "job": "digest", "run_id": run["run_id"],
                       "path": "report.md"})["content"] == "Draft: 12.34"


def test_retention_removes_whole_finished_run_after_its_own_keep_period(realm):
    run = dry_runs.start(realm, "writer", "digest", "gpt-6-sol", engine=DraftEngine())
    info = finished(realm, run)
    folder = Path(run["output_dir"]).parent
    finish = dt.datetime.fromisoformat(info["finished"])
    assert dry_runs.prune(realm, now=finish+dt.timedelta(days=6))["removed"] == 0
    assert dry_runs.prune(realm, now=finish+dt.timedelta(days=8))["removed"] == 1
    assert not folder.exists() and (realm / "input.json").exists()


def test_command_dry_run_needs_owner_approval_and_preserves_production_command(realm):
    jp = realm / "agents/writer/jobs/digest.json"
    script = realm / "safe-draft.py"
    script.write_text("import os,pathlib\nassert os.environ['ARMADA_DRY_RUN']=='1'\n"
        "pathlib.Path(os.environ['ARMADA_DRY_RUN_DIR'],'draft.txt').write_text('command draft')\nprint('draft only')\n")
    job = {"id": "digest", "kind": "command", "run": ["do-not-run-production"], "dry_run_command": [sys.executable, str(script)]}
    util.write_json_atomic(jp, job)
    with pytest.raises(ValueError, match="explicit"):
        dry_runs.start(realm, "writer", "digest")
    inspection.approve_command(realm, "writer", job)
    before = jp.read_bytes()
    run = dry_runs.start(realm, "writer", "digest")
    info = finished(realm, run)
    assert info["status"] == "completed" and jp.read_bytes() == before
    assert (Path(run["output_dir"]) / "draft.txt").read_text() == "command draft"
    util.mutate_json(jp, lambda j: j.update(dry_run_command=["different-command"]))
    with pytest.raises(ValueError, match="explicit"):
        dry_runs.start(realm, "writer", "digest")


def test_stop_cancels_owned_process_and_never_retries(realm):
    started = threading.Event()
    killed = threading.Event()
    class Slow(DraftEngine):
        def run_stream(self, **kwargs):
            class Process:
                def kill(self):
                    killed.set()
            kwargs["on_proc"](Process())
            started.set()
            assert killed.wait(5)
            return RunResult(ok=False, cancelled=True, error="Stopped")
    run = dry_runs.start(realm, "writer", "digest", "gpt-6-sol", engine=Slow())
    assert started.wait(5)
    assert dry_runs.stop(realm, "writer", "digest", run["run_id"])["ok"]
    assert finished(realm, run)["status"] == "stopped"
    assert len(dry_runs.listing(realm, "writer", "digest")) == 1


@pytest.mark.parametrize("required,status", [(False, "warning"), (True, "failed")])
def test_command_capture_is_reported_as_unsupported_without_interrupting_drafts(realm, required, status):
    script = realm / "command-draft.py"
    script.write_text("import os,pathlib\npathlib.Path(os.environ['ARMADA_DRY_RUN_DIR'],'draft.txt').write_text('draft')\n")
    job = {"id": "digest", "kind": "command", "run": ["production-must-not-run"],
           "dry_run_command": [sys.executable, str(script)], "capture_tools": ["mcp__*"], "require_capture": required}
    util.write_json_atomic(realm / "agents/writer/jobs/digest.json", job)
    inspection.approve_command(realm, "writer", job)
    run = dry_runs.start(realm, "writer", "digest")
    info = finished(realm, run)
    assert info["status"] == status
    assert info["capture"]["status"] == "incomplete" and "unsupported" in info["capture"]["errors"][0]
    assert (Path(run["output_dir"]) / "draft.txt").read_text() == "draft"


def test_stdio_mcp_bridge_reads_and_writes_only_scoped_drafts(realm):
    from armada import managed_mcp
    with ManagedTools(realm, "writer", output=realm / "drafts") as tools:
        requests = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "write_draft", "arguments": {"path": "résumé-测试.txt", "content": "exact 12.34 · Проба · 测试"}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "write_draft", "arguments": {"path": "../outside", "content": "x"}}}]
        import os
        result = subprocess.run([sys.executable, managed_mcp.__file__], input="\n".join(json.dumps(r) for r in requests)+"\n",
            text=True, encoding="utf-8", capture_output=True, timeout=10, env={**os.environ, **tools.server_config["env"]})
        replies = [json.loads(line) for line in result.stdout.splitlines()]
        assert result.returncode == 0 and len(replies) == 4
        assert len(replies[1]["result"]["tools"]) == 3
        assert not replies[2]["result"]["isError"] and replies[3]["result"]["isError"]
        assert (realm / "drafts/résumé-测试.txt").read_text(encoding="utf-8") == "exact 12.34 · Проба · 测试"


def test_managed_provider_configuration_excludes_ambient_tools_and_codex_argv_secrets(realm, monkeypatch):
    from armada.engine import get_engine
    from armada.managed_tools import claude_args, codex_args
    with ManagedTools(realm, "writer", output=realm / "drafts") as tools:
        claude = tools.configure(get_engine("claude"))
        monkeypatch.setattr(claude, "_direct", lambda: True)
        args = claude_args(claude)
        assert args[args.index("--tools")+1] == ""
        assert "--strict-mcp-config" in args and "--dangerously-skip-permissions" not in args
        assert "--bare" not in args and "--safe-mode" not in args
        assert args[args.index("--setting-sources")+1] == ""
        codex = tools.configure(get_engine("codex"))
        monkeypatch.setattr(codex, "_mcp_args", lambda allow, denied, cwd=None: ["-c", "mcp_servers.publisher.enabled=false"])
        args = codex_args(codex)
        assert tools.token not in " ".join(args)
        assert "mcp_servers.publisher.enabled=false" in args
        assert codex._turn_mcp_ids == ("armada_managed",)
        launch = codex._args("gpt-6-sol", True, None, (), cwd=str(realm))
        assert launch[launch.index("--sandbox")+1] == "read-only"
        assert "features.shell_tool=false" in launch and "features.unified_exec=false" in launch
        gemini = tools.configure(get_engine("gemini"))
        config = json.loads(gemini._agent("Synthetic context", True, []).split("---",2)[1])
        assert config["tools"] == [] and config["inheritMcp"] is False
        assert config["commandExecutionPolicy"] == "off"
        assert [server["name"] for server in config["mcpServers"]] == ["armada_managed"]


def test_cross_process_liveness_and_stop_request_are_durable(realm, monkeypatch):
    folder = dry_runs.directory(realm, "writer", "digest", "foreign-process")
    (folder / "output").mkdir(parents=True)
    import os
    info = {"schema_version": 1, "run_id": "foreign-process", "agent": "writer", "job": "digest",
            "status": "running", "owner_pid": os.getpid(), "started": dt.datetime.now(dt.timezone.utc).isoformat(), "keep_days": 1}
    util.write_json_atomic(folder / "run.json", info)
    from armada.request_context import RunContext
    context = RunContext.capture(realm, "writer", "dryrun-foreign-process", run_id="foreign-process")
    util.write_json_atomic(context.marker, {"run_id": "foreign-process", "owner_pid": os.getpid()})
    assert dry_runs.read(realm, "writer", "digest", "foreign-process")["status"] == "running"
    assert dry_runs.prune(realm, now=dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=5))["removed"] == 0
    assert dry_runs.stop(realm, "writer", "digest", "foreign-process")["ok"]
    assert (folder / "stop.json").is_file()
    context.marker.unlink()
    assert dry_runs.read(realm, "writer", "digest", "foreign-process")["status"] == "interrupted"
    assert dry_runs.prune(realm, now=dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=5))["removed"] == 1


def test_inspector_job_uses_the_managed_broker_and_records_its_review_files(realm, monkeypatch):
    from armada import runner
    from armada.execution import TurnCoordinator, TurnRequest
    from armada.request_context import RunContext
    approve_inspector(realm)
    class Review(DraftEngine):
        def run_stream(self, **kwargs):
            assert "ARMADA inspector" in kwargs["system"]
            assert kwargs["allow_tools"] is True
            assert not self.allowed_mcp_ids and not self.writable_roots
            self.managed_tools.call("list_jobs", {})
            self.managed_tools.call("write_draft", {"path": "review.md", "content": "Synthetic review"})
            return RunResult(ok=True, output="Review saved.")
    monkeypatch.setattr(runner, "_select_engine", lambda *args, **kw: Review())
    def compact_without_actions(self, engine, **kwargs):
        assert not getattr(engine, "managed_tools", None)
        return False
    monkeypatch.setattr("armada.threads.Thread.compact_if_needed", compact_without_actions)
    result = TurnCoordinator(TurnRequest(RunContext.capture(realm, "inspector", "main"), "Compare job models",
        task='review', job={'id': 'review', 'inspector': True})).run()
    assert result["status"] == 'ok'
    from armada.threads import Thread
    outputs = Thread(realm / "agents/inspector", "main")._messages()[-1]["outputs"]
    assert any(o["name"] == "review.md" for o in outputs)


def test_tool_capture_in_a_dry_run_stays_temporary_and_preserves_result_bytes(realm):
    util.mutate_json(realm / "agents/writer/jobs/digest.json", lambda j: j.update(
        capture_tools=["mcp__armada_managed__*"], require_capture=True))
    class Captured(DraftEngine):
        def run_stream(self, **kwargs):
            emit = kwargs["on_event"]
            emit({"kind": "tool", "id": "read", "name": "mcp__armada_managed__read_input", "input": {"path": "input.json"}})
            emit({"kind": "tool_result", "id": "read", "content": "12.34", "raw_result": {
                "event": '{"result": { "amount": 12.3400, "currency":"EUR" }}', "path": ["result"]}})
            return super().run_stream(**kwargs)
    run = dry_runs.start(realm, "writer", "digest", "gpt-6-sol", engine=Captured())
    info = finished(realm, run)
    assert info["status"] == "completed" and info["capture"]["count"] == 1
    manifest = Path(info["capture"]["manifest"])
    assert manifest.is_relative_to(Path(run["output_dir"]).parent)
    row = json.loads(manifest.read_text().strip())
    raw = (manifest.parent / row["file"]).read_bytes()
    assert raw == b'{ "amount": 12.3400, "currency":"EUR" }'
    assert hashlib.sha256(raw).hexdigest() == row["sha256"]
    assert not (realm / "Finance").exists() and not (realm / "capture-index").exists()


def test_require_capture_fails_only_the_test_and_does_not_stop_execution(realm, monkeypatch):
    util.mutate_json(realm / "agents/writer/jobs/digest.json", lambda j: j.update(
        capture_tools=["mcp__*"], require_capture=True))
    def failure(*args):
        raise OSError("Synthetic capture failure")
    monkeypatch.setattr("armada.tool_capture.ToolCapture._checked", failure)
    run = dry_runs.start(realm, "writer", "digest", "gpt-6-sol", engine=DraftEngine())
    info = finished(realm, run)
    assert info["status"] == "failed" and info["capture"]["status"] == "incomplete"
    assert (Path(run["output_dir"]) / "report.md").read_text() == "Draft: 12.34"
    assert not job_history.reports(realm / "agents/writer", "digest")
