"""Same adversarial real-child contract for both CLI adapters; no provider/network required."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import pytest

@pytest.fixture(autouse=True)
def existing_realm(tmp_path):
    (tmp_path / "realm.json").write_text('{"name":"Test"}', encoding="utf-8")


from armada.engine import claude, codex
from armada.engine.base import RunResult
from armada.engine import process


def events(provider):
    if provider.startswith("claude"):
        return ({"type": "assistant", "message": {"content": [{"type": "text", "text": "partial reply"}]}},
                {"type": "result", "subtype": "success", "result": "complete reply", "usage": {}})
    return ({"type": "item.completed", "item": {"id": "one", "type": "agent_message", "text": "partial reply"}},
            {"type": "turn.completed", "usage": {}})


def output(event):
    return f"print({json.dumps(event)!r}, flush=True)\n"


def adapter(tmp_path, monkeypatch, provider, script):
    child = tmp_path / (provider + ".py")
    child.write_text("import sys,json,time,os,subprocess\n" + script, encoding="utf-8")
    engine = claude.ClaudeEngine() if provider.startswith("claude") else codex.CodexEngine()
    monkeypatch.setattr(engine, "_launcher", lambda: [sys.executable, "-u", str(child)])
    if provider.startswith("claude"):
        monkeypatch.setattr(engine, "_direct", lambda: True)
        monkeypatch.setattr(engine, "_mcp_args", lambda *args: [])
    else:
        monkeypatch.setattr(engine, "_args", lambda *args, **kwargs: [])
        engine.app_server_streaming = False  # This fixture speaks codex exec JSON, not app-server RPC.
    return engine


@pytest.mark.parametrize("provider", ["claude", "codex", "claude-json"])
@pytest.mark.parametrize("case", ["success", "missing", "malformed", "bad-terminal", "nonzero", "stderr", "silent", "closed-stdout"])
def test_terminal_and_deadline_contract(tmp_path, monkeypatch, provider, case):
    partial, terminal = events(provider)
    script = "" if provider == "claude-json" else output(partial)
    expected = case in ("success", "stderr")
    if case == "stderr": script += "sys.stderr.write('x'*2000000);sys.stderr.flush()\n"
    if case in ("success", "stderr", "nonzero"):
        script += output(terminal)
    elif case == "malformed":
        script += "print('not JSON',flush=True)\n"
    elif case == "bad-terminal":
        terminal["usage"] = ["invalid"]
        script += output(terminal)
    elif case == "closed-stdout":
        script += "os.close(1)\ntime.sleep(30)\n"
    elif case == "silent":
        script = "time.sleep(30)\n"
    if case == "nonzero": script += "sys.exit(7)\n"
    engine = adapter(tmp_path, monkeypatch, provider, script)
    started = time.monotonic()
    result = (engine.run if provider == "claude-json" else engine.run_stream)(
        "memory", "request", allow_tools=True, timeout=1.2 if case in ("silent", "closed-stdout") else 5)
    assert result.ok is expected, result
    if not expected: assert result.error
    if case in ("silent", "closed-stdout"):
        assert "timed out" in result.error and time.monotonic() - started < 5
    if provider != "claude-json" and case not in ("silent", "success", "stderr", "nonzero"):
        assert "partial reply" in result.output
    assert not [t for t in threading.enumerate() if t.name.startswith("armada-cli-")]


@pytest.mark.parametrize("provider", ["claude", "codex"])
@pytest.mark.parametrize("failure", ["nonzero-after-text", "nonobject", "after-terminal", "provider-error", "oversized"])
def test_protocol_failures_preserve_partial_output(tmp_path, monkeypatch, provider, failure):
    partial, terminal = events(provider)
    script = output(partial)
    if failure == "nonzero-after-text": script += "sys.exit(4)\n"
    elif failure == "nonobject": script += "print('[]')\n"
    elif failure == "after-terminal": script += output(terminal) + output(partial)
    elif failure == "provider-error": script += output({"type": "error", "message": "provider rejected"}) + output(terminal)
    elif failure == "oversized": script += f"print('x' * {process.MAX_LINE + 10}, flush=True)\n"
    engine = adapter(tmp_path, monkeypatch, provider, script)
    result = engine.run_stream("", "", allow_tools=True, timeout=5)
    assert not result.ok and result.error and result.output


def test_large_connector_line_within_transport_limit_is_accepted(tmp_path):
    child = tmp_path / "large_event.py"
    child.write_text("print('x' * 1100000, flush=True)\n", encoding="utf-8")
    lengths = []
    result = process.supervise([sys.executable, "-u", str(child)], prompt="",
                               on_line=lambda line: lengths.append(len(line)), timeout=5)
    assert result.error == ""
    assert lengths == [1100001]


def alive(pid):
    if os.name == "nt":
        import ctypes as C
        from ctypes import wintypes as W
        api = C.WinDLL("kernel32", use_last_error=True)
        api.OpenProcess.argtypes, api.OpenProcess.restype = [W.DWORD, W.BOOL, W.DWORD], W.HANDLE
        api.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
        api.CloseHandle.argtypes = [W.HANDLE]
        handle = api.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE
        if not handle: return False
        try: return api.WaitForSingleObject(handle, 0) == 258  # WAIT_TIMEOUT = still running
        finally: api.CloseHandle(handle)
    from armada.util import pid_alive
    return pid_alive(pid)


@pytest.mark.parametrize("provider", ["claude", "codex"])
@pytest.mark.parametrize("ending", ["cancel", "timeout", "parent-exit", "callback-error"])
def test_owned_descendant_cleanup(tmp_path, monkeypatch, provider, ending):
    partial, terminal = events(provider)
    child_pid = tmp_path / "descendant.txt"
    script = (f"p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])\n"
              f"with open({str(child_pid.with_suffix('.tmp'))!r},'w') as f: f.write(str(p.pid))\n"
              f"os.replace({str(child_pid.with_suffix('.tmp'))!r}, {str(child_pid)!r})\n" + output(partial))
    script += output(terminal) if ending == "parent-exit" else "time.sleep(60)\n"
    engine = adapter(tmp_path, monkeypatch, provider, script)
    handles = []
    def register(handle):
        handles.append(handle)
        # The timeout measures process startup too. Wait for the fixture's descendant before
        # allowing the supervisor to enforce it, so a busy CI host still tests tree cleanup.
        until = time.monotonic() + 5
        while not child_pid.exists() and time.monotonic() < until: time.sleep(0.01)
        assert child_pid.exists(), "fixture CLI did not start its descendant"
        if ending == "callback-error":
            raise RuntimeError("registration failed")
    def event(event):
        if ending == "cancel" and event.get("kind") == "text": handles[0].kill()
    started = time.monotonic()
    result = engine.run_stream("", "", allow_tools=True, timeout=0.7 if ending == "timeout" else 6,
                               on_event=event, on_proc=register)
    assert time.monotonic() - started < 6
    assert result.ok is (ending == "parent-exit"), result
    assert result.cancelled is (ending == "cancel")
    # The supervisor waits on the original process. Its numeric PID can already have been
    # recycled on Windows after the owned handle closes, so don't reopen an unrelated process.
    assert handles and handles[0].poll() is not None
    pid = int(child_pid.read_text())
    until = time.monotonic() + 2
    while alive(pid) and time.monotonic() < until: time.sleep(0.01)
    assert not alive(pid), f"descendant {pid} survived {ending}"
    assert not [t for t in threading.enumerate() if t.name.startswith("armada-cli-")]


@pytest.mark.parametrize("provider", ["claude", "codex"])
def test_broken_observer_does_not_abandon_process(tmp_path, monkeypatch, provider):
    partial, terminal = events(provider)
    engine = adapter(tmp_path, monkeypatch, provider, output(partial) + output(terminal))
    def broken(event): raise RuntimeError("browser disconnected")
    result = engine.run_stream("", "", allow_tools=True, timeout=5, on_event=broken)
    assert result.ok and result.output
    assert not [t for t in threading.enumerate() if t.name.startswith("armada-cli-")]


@pytest.mark.parametrize("entry", ["chat", "stream", "job"])
@pytest.mark.parametrize("cancelled", [False, True, None], ids=["failed", "stopped", "empty-success"])
def test_partial_output_and_terminal_status_are_persisted(tmp_path, entry, cancelled):
    from armada import runner, util
    from armada.threads import Thread
    root = tmp_path / "realm"
    adir = root / "agents/dev"
    (adir / "jobs").mkdir(parents=True)
    util.write_json_atomic(root / "realm.json", {"name": "Test"})
    util.write_json_atomic(adir / "agent.json", {"id": "dev", "display": "Dev"})
    util.write_json_atomic(adir / "jobs/work.json", {"prompt": "work"})
    class Engine:
        name = "mock"
        def run_stream(self, **kwargs):
            if cancelled is None:
                return RunResult(True)
            return RunResult(False, "partial answer", error="interrupted", cancelled=cancelled)
        run = run_stream
    if entry == "chat": result = runner.chat(root, "dev", "main", "ping", engine=Engine())
    elif entry == "stream": result = runner.chat_stream(root, "dev", "main", "ping", lambda e: None, engine=Engine())
    else: result = runner.run_job(root, "dev", "work", engine=Engine())
    status = "ok" if cancelled is None else ("stopped" if cancelled else "error")
    assert result["status"] == status
    from armada import status as statuses
    assert statuses.normalize(status) == (statuses.SUCCESS if cancelled is None else
                                          statuses.WARN if cancelled else statuses.FAILED)
    from armada.job_history import thread_name
    transcript = Thread(adir, thread_name("work") if entry == "job" else "main")
    messages = transcript.snapshot()[1]
    assert messages[-1].get("status", "ok") == status
    if cancelled is None:
        assert messages[-1]["content"] == "Completed without a text reply."
    else:
        assert "partial answer" in messages[-1]["content"]
        if entry == "job":
            assert "interrupted" not in messages[-1]["content"]
            assert "interrupted" in result["app_errors"]
        else:
            assert "interrupted" in messages[-1]["content"]
    assert transcript.open_turn() is None


def test_on_proc_failure_clears_route_activity(tmp_path, monkeypatch):
    from armada.routes.agents import AgentRoutes
    from armada import runner
    class Handler(AgentRoutes):
        realm = str(tmp_path)
        _streams = {}
        wfile = io.BytesIO()
        send_response = send_header = end_headers = lambda *args: None
    def failed(*args, **kwargs): raise RuntimeError("callback failed")
    monkeypatch.setattr(runner, "chat_stream", failed)
    Handler()._chat_stream({"agent": "dev", "message": "ping", "tid": "failed"})
    assert not Handler._streams
    assert not list((tmp_path / "agents/dev/runs/.running").glob("_chat-*.json"))


@pytest.mark.parametrize("provider", ["claude", "codex"])
def test_stdout_volume_is_bounded(tmp_path, monkeypatch, provider):
    partial, _ = events(provider)
    engine = adapter(tmp_path, monkeypatch, provider, "for i in range(10000):\n " + output(partial))
    monkeypatch.setattr(process, "MAX_STDOUT", 1024)
    result = engine.run_stream("", "", allow_tools=True, timeout=5)
    assert not result.ok and "turn limit" in result.error


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object failure injection")
def test_tree_cleanup_failure_is_retried_without_losing_reply(tmp_path, monkeypatch):
    from armada.engine.windows_job import WindowsJob
    partial, terminal = events("claude")
    engine = adapter(tmp_path, monkeypatch, "claude", output(partial) + output(terminal))
    original = WindowsJob.close
    attempts = []
    def fail_once(job):
        attempts.append(True)
        if len(attempts) == 1: raise OSError("transient cleanup failure")
        original(job)
    monkeypatch.setattr(WindowsJob, "close", fail_once)
    handles = []
    result = engine.run_stream("", "", allow_tools=True, timeout=5, on_proc=handles.append)
    assert not result.ok and "cleanup failure" in result.error and result.output
    assert len(attempts) >= 2 and not alive(handles[0].pid)
    assert not [t for t in threading.enumerate() if t.name.startswith("armada-cli-")]


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object admission failure")
def test_tree_assignment_failure_never_executes_child(tmp_path, monkeypatch):
    from armada.engine.windows_job import WindowsJob
    executed = tmp_path / "must-not-exist"
    engine = adapter(tmp_path, monkeypatch, "claude", f"open({str(executed)!r},'w').write('ran')\n")
    def fail(*args): raise OSError("cannot establish process ownership")
    monkeypatch.setattr(WindowsJob, "attach_and_resume", fail)
    result = engine.run_stream("", "", allow_tools=True, timeout=5)
    assert not result.ok and "ownership" in result.error and not executed.exists()


def test_locked_marker_becomes_terminal_instead_of_staying_busy(tmp_path, monkeypatch):
    from armada.routes.agents import AgentRoutes
    from armada import runner, util
    from armada.webui.agentbits import _agent_busy
    class Handler(AgentRoutes):
        realm = str(tmp_path)
        _streams = {}
        wfile = io.BytesIO()
        send_response = send_header = end_headers = lambda *args: None
    marker = tmp_path / "agents/dev/runs/.running/_chat-locked.json"
    original = Path.unlink
    def unlink(path, *args, **kwargs):
        if path == marker: raise PermissionError("in use")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", unlink)
    monkeypatch.setattr(runner, "chat_stream", lambda *args, **kwargs: {"ok": False})
    Handler()._chat_stream({"agent": "dev", "message": "ping", "tid": "locked"})
    assert not Handler._streams and not _agent_busy(tmp_path, "dev")
    assert util.read_json_state(marker)["status"] == "finished"


def test_codex_temp_cleanup_failure_preserves_result(tmp_path, monkeypatch):
    partial, terminal = events("codex")
    engine = adapter(tmp_path, monkeypatch, "codex", output(partial) + output(terminal))
    class Temp:
        name = str(tmp_path)
        def cleanup(self): raise PermissionError("in use")
    monkeypatch.setattr(codex.tempfile, "TemporaryDirectory", lambda **kwargs: Temp())
    result = engine.run_stream("", "", allow_tools=False, timeout=5)
    assert not result.ok and "partial reply" in result.output and "cleanup failed" in result.error


@pytest.mark.parametrize("provider", ["claude", "codex"])
def test_large_stdin_and_stderr_do_not_deadlock_each_other(tmp_path, monkeypatch, provider):
    partial, terminal = events(provider)
    script = "sys.stderr.write('x'*2000000);sys.stderr.flush()\np=sys.stdin.read()\n"
    script += f"assert len(p) >= 300000\n" + output(partial) + output(terminal)
    engine = adapter(tmp_path, monkeypatch, provider, script)
    result = engine.run_stream("memory", "Ω" * 300000, allow_tools=True, timeout=8)
    assert result.ok and result.output


@pytest.mark.parametrize("provider", ["claude", "codex"])
@pytest.mark.parametrize("usage", [[], None, ""])
def test_empty_but_invalid_terminal_usage_is_not_success(tmp_path, monkeypatch, provider, usage):
    partial, terminal = events(provider)
    terminal["usage"] = usage
    engine = adapter(tmp_path, monkeypatch, provider, output(partial) + output(terminal))
    result = engine.run_stream("", "", allow_tools=True, timeout=5)
    assert not result.ok and "partial reply" in result.output and result.error


@pytest.mark.parametrize("provider", ["claude", "codex"])
def test_invalid_utf8_protocol_bytes_fail_closed(tmp_path, monkeypatch, provider):
    partial, terminal = events(provider)
    data = (json.dumps(partial).replace("partial reply", "BAD_BYTE") + "\n").encode().replace(b"BAD_BYTE", b"\xff")
    engine = adapter(tmp_path, monkeypatch, provider, f"os.write(1,{data!r})\n" + output(terminal))
    result = engine.run_stream("", "", allow_tools=True, timeout=5)
    assert not result.ok and "stdout read failed" in result.error
