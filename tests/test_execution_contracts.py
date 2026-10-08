"""Shared execution behavior at the public boundaries, with no live providers."""
import json
from dataclasses import FrozenInstanceError

import pytest

from armada import execution, runner, util
from armada.engine import ClaudeEngine, CodexEngine, MockEngine
from armada.engine.gemini import GeminiEngine
from armada.engine.base import RunResult, Usage
from armada.engine.contracts import ExecutionPolicy, RunRequest, execute_request
from armada.request_context import RunContext
from armada.threads import Thread
from armada.job_history import thread_name


@pytest.fixture
def realm(tmp_path):
    ad = tmp_path / "agents" / "a"
    (ad / "jobs").mkdir(parents=True)
    (tmp_path / "realm.json").write_text('{"name":"Test"}', encoding="utf-8")
    (ad / "agent.json").write_text('{"id":"a"}', encoding="utf-8")
    (ad / "jobs" / "work.json").write_text('{"id":"work","prompt":"hello"}', encoding="utf-8")
    return tmp_path


def invoke(path, realm, engine, **kw):
    if path == "chat":
        return runner.chat(realm, "a", "main", "hello", engine=engine, **kw)
    if path == "stream":
        return runner.chat_stream(realm, "a", "main", "hello", lambda ev: None, engine=engine, **kw)
    if path == "job":
        return runner.run_job(realm, "a", "work", engine=engine, **kw)
    return runner.run_job_prompt(realm, "a", "hello", engine=engine, **kw)


@pytest.mark.parametrize("path", ["chat", "stream", "job", "inbox"])
@pytest.mark.parametrize("provider", [ClaudeEngine, CodexEngine])
@pytest.mark.parametrize("ending", ["ok", "raise", "error", "cancel", "empty"])
def test_every_path_has_one_durable_terminal_outcome(realm, monkeypatch, path, provider, ending):
    engine = provider()
    ad = realm / "agents" / "a"
    transcript = Thread(ad, thread_name("work") if path == "job" else "main")
    outputs = []
    def stream(**kw):
        th = transcript
        assert th.open_turn(), "owner request must exist before invocation"
        kw["on_event"]({"kind": "text", "text": "partial"})
        assert th.progress(th.open_turn()["turn"])["content"] == "partial"
        assert "partial" not in th.render(), "progress is not extra conversation history"
        assert kw["timeout"] == runner._DEFAULT_RUN_TIMEOUT
        (ad / "answer.txt").write_text("artifact", encoding="utf-8")
        kw["on_event"]({"kind": "tool", "name": "Write", "id": "w",
                          "input": {"file_path": str(ad / "answer.txt")}})
        if ending == "raise":
            raise RuntimeError("provider crashed")
        return RunResult(ok=ending in ("ok", "empty"), output="" if ending == "empty" else "partial",
            error="stopped" if ending == "cancel" else "failed" if ending == "error" else "",
            cancelled=ending == "cancel", usage=Usage(input=3, output=2, cost_usd=None))
    monkeypatch.setattr(engine, "run_stream", stream)
    if isinstance(engine, CodexEngine):
        # This test supplies a synthetic provider turn; readiness has its own RPC tests.
        monkeypatch.setattr(engine, "_execution_probe", lambda *a: {"ok": True, "reason": ""})
    result = invoke(path, realm, engine)
    assert result["status"] == ("ok" if ending in ("ok", "empty") else "stopped" if ending == "cancel" else "error")
    messages = [m for m in transcript.snapshot()[1] if m.get("role") in ("user", "assistant")]
    assert len(messages) == 2 and transcript.open_turn() is None
    reply = messages[-1]
    assert ("Completed without a text reply" in reply["content"]
            if ending == "empty" and path in ("chat", "stream", "inbox") else "partial" in reply["content"])
    assert reply.get("outputs"), "all paths preserve observed artifacts"
    reports = [json.loads(line) for line in (ad / "runs" / "a.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(reports) == 1 and reports[0]["status"] == result["status"]
    assert reports[0]["realm_id"] == RunContext.capture(realm, "a").realm.realm_id
    assert reports[0]["run_id"] and reports[0]["tokens"]["api_equiv_usd"] is None
    assert not list((ad / "runs" / ".running").glob("*.json")) and not execution.ACTIVE_RUNS


@pytest.mark.parametrize("provider", [ClaudeEngine, CodexEngine])
@pytest.mark.parametrize("settings", [dict(max_budget_usd=-1), dict(max_budget_usd=float("nan")),
                                      dict(max_budget_usd="invalid"), dict(max_budget_usd=True)])
def test_invalid_requirements_never_reach_cli(provider, settings, monkeypatch):
    engine = provider()
    monkeypatch.setattr(engine, "_launcher", lambda: pytest.fail("launched invalid request"))
    assert not engine.run("", "", **settings).ok
    assert not engine.run_stream("", "", **settings).ok


@pytest.mark.parametrize("settings", [dict(max_budget_usd=1), dict(fallback_model="gpt-5"),
                                      dict(only_tools=[]), dict(disallowed_tools=["Bash"])])
def test_codex_unsupported_settings_fail_before_probe(settings, monkeypatch):
    engine = CodexEngine()
    monkeypatch.setattr(engine, "_launcher", lambda: pytest.fail("launched unsupported request"))
    result = engine.run("", "", **settings)
    assert not result.ok and result.error


def test_cross_provider_fallback_is_not_silently_dropped(monkeypatch):
    engine = ClaudeEngine()
    monkeypatch.setattr(engine, "_launcher", lambda: pytest.fail("cross-provider fallback launched"))
    assert not engine.run("", "", fallback_model="gpt-5").ok


@pytest.mark.parametrize("path", ["chat", "stream", "job", "inbox"])
def test_unsupported_request_is_recorded_before_any_compaction(realm, monkeypatch, path):
    (realm / "agents/a/agent.json").write_text('{"model":"gpt-5","max_budget_usd":2}', encoding="utf-8")
    monkeypatch.setattr(Thread, "compact_if_needed", lambda *a, **k: pytest.fail("paid helper before validation"))
    result = invoke(path, realm, CodexEngine())
    assert result["status"] == "error"
    th = Thread(realm / "agents/a", thread_name("work") if path == "job" else "main")
    if path == "job":
        assert "budget" not in th.snapshot()[1][-1]["content"]
        assert "budget" in result["result"]["app_errors"][0]
    else:
        assert "budget" in th.snapshot()[1][-1]["content"]


@pytest.mark.parametrize("provider", [ClaudeEngine, CodexEngine])
def test_invocation_grants_do_not_mutate_shared_adapter(provider):
    original = provider()
    first = original.configure(ExecutionPolicy(frozenset({"first"}), ("one",), True))
    second = original.configure(ExecutionPolicy(frozenset({"second"}), ("two",)))
    assert first.allowed_mcp_ids == {"first"} and second.allowed_mcp_ids == {"second"}
    assert first.writable_roots == ("one",) and second.writable_roots == ("two",)
    assert first.network_access is True and second.network_access is False
    assert not original.allowed_mcp_ids


def test_typed_request_is_immutable_and_unknown_usage_stays_null():
    request = RunRequest("memory", "hello")
    with pytest.raises(FrozenInstanceError):
        request.timeout = 5
    assert Usage().as_dict()["total"] is None
    assert Usage().as_dict()["api_equiv_usd"] is None
    assert Usage(input=0, output=0, cost_usd=0).as_dict()["total"] == 0
    assert Usage(input=0, output=0, cost_usd=0).as_dict()["api_equiv_usd"] == 0


@pytest.mark.parametrize("provider", [ClaudeEngine, CodexEngine, GeminiEngine, MockEngine])
def test_production_entrypoints_accept_the_complete_shared_request(provider):
    import inspect
    engine = provider()
    kwargs = RunRequest("memory", "hello", verbosity="brief", only_tools=()).kwargs()
    inspect.signature(engine.run).bind(**kwargs)
    if engine.capabilities.streaming:
        inspect.signature(engine.run_stream).bind(**kwargs, on_event=None, on_proc=None)


def test_observer_failure_cannot_abandon_turn(realm, monkeypatch):
    def broken(ev):
        raise ConnectionError("browser gone")
    result = runner.chat_stream(realm, "a", "main", "hello", broken, engine=MockEngine())
    assert result["ok"] and Thread(realm / "agents/a").open_turn() is None
    assert not execution.ACTIVE_RUNS


def test_capture_cleanup_failure_still_closes_turn(realm, monkeypatch):
    monkeypatch.setattr(runner._TurnCapture, "finish", lambda self: (_ for _ in ()).throw(OSError("capture failed")))
    result = runner.chat(realm, "a", "main", "hello", engine=MockEngine())
    assert result["status"] == "error" and "capture failed" in result["error"]
    assert Thread(realm / "agents/a").open_turn() is None and not execution.ACTIVE_RUNS


def test_cancel_before_model_call_saves_stopped_outcome(realm, monkeypatch):
    context = RunContext.capture(realm, "a")
    with execution.RunSession(context) as session:
        execution.RunSession.cancel(context.key)
        engine = MockEngine()
        monkeypatch.setattr(engine, "run", lambda **kw: pytest.fail("cancelled run started"))
        result = runner.chat_stream(realm, "a", "main", "hello", lambda ev: None,
                                    engine=engine, context=context, session=session)
    assert result["status"] == "stopped" and not context.marker.exists()


def test_unknown_cost_is_not_added_as_zero_in_totals(realm):
    import datetime as dt
    from armada import reader
    from armada.webui._core import _totals_30d, _usage_data
    now = dt.date.today().isoformat()
    ad = realm / "agents/a"
    for tokens in ({"total": 100, "api_equiv_usd": 1.0}, {"total": 10, "api_equiv_usd": None}):
        runner._write_report(ad, "a", {"ts": now, "model": "gpt-5", "tokens": tokens})
    model = reader.read(realm)
    assert model.cost_30d is None
    assert _totals_30d(model, realm, dt.date.today()) == (110, 1.0)
    assert _totals_30d(model, realm, dt.date.today(), details=True)['unknown_cost_runs_30d'] == 1
    assert _usage_data(model, realm, "line", "today")["usd"] is None


def test_routes_do_not_call_private_renderers_to_mutate_thread_state():
    import inspect
    from armada.routes.agents import AgentRoutes
    source = inspect.getsource(AgentRoutes)
    assert "webui._mark_thread_unread" not in source
    assert "RunSession" in source


@pytest.mark.parametrize("mode", ["line", "graph"])
def test_unknown_token_runs_are_distinguished_from_zero(realm, mode):
    import datetime as dt
    from armada import reader
    from armada.webui._core import _usage_data
    now = dt.date.today().isoformat()
    for total in (100, None, 0):
        runner._write_report(realm / "agents/a", "a", {
            "ts": now, "model": "gpt-5", "tokens": {"total": total, "api_equiv_usd": None}})
    result = _usage_data(reader.read(realm), realm, mode, "today")
    assert result["total"] == 100  # Only reported tokens may be charted.
    assert result["unknown_runs"] == 1
    assert result["total_30d"] == 100 and result["usd_30d"] is None
    assert result['unknown_token_runs_30d'] == 1


def test_incomplete_claude_model_usage_does_not_fabricate_zero():
    from armada.engine.claude import _usage_from_event
    usage = _usage_from_event({"modelUsage": {"sonnet": {"inputTokens": 5}}})
    assert usage.input == 5 and usage.output is None and usage.total is None
