"""Unattended checks may capture output but must never allocate a Windows console."""
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from armada import background, preflight
from armada.engine.claude import ClaudeEngine
from armada.engine.codex import CodexEngine
from armada.engine.gemini import GeminiEngine


def assert_hidden(kwargs):
    if os.name == "nt":
        assert kwargs["creationflags"] & subprocess.CREATE_NO_WINDOW
        assert kwargs["startupinfo"].dwFlags & subprocess.STARTF_USESHOWWINDOW
        assert kwargs["startupinfo"].wShowWindow == subprocess.SW_HIDE


@pytest.mark.parametrize("provider,cls", [("claude", ClaudeEngine), ("codex", CodexEngine), ("gemini", GeminiEngine)])
def test_realm_engine_checks_hide_every_probe(monkeypatch, provider, cls):
    # Undo the global test launcher stubs, then intercept only the process boundary.
    from armada.engine import gemini
    calls = []
    monkeypatch.setattr(cls, "_launcher", lambda self: ["fixture"])
    if provider == "gemini":
        monkeypatch.setattr(cls, "auth_status", _REAL_GEMINI_AUTH)
        gemini.invalidate_auth()
    def run(args, **kwargs):
        assert_hidden(kwargs)
        calls.append(args)
        text = ("gemini-3.8-flash-medium\tGemini 3.8 Flash (Medium)" if args[-1] == "models"
                else "Logged in using ChatGPT" if args[-1] == "status" else "2.1.280")
        return SimpleNamespace(returncode=0, stdout=text, stderr="")
    monkeypatch.setattr(subprocess, "run", run)
    # preflight's actual doctor path, without a real provider or account request.
    monkeypatch.setattr("armada.engine.get_engine", lambda name: cls())
    assert preflight.engine_check(provider)["ok"]
    assert calls


_REAL_GEMINI_AUTH = GeminiEngine.auth_status


def test_background_git_check_and_pull_hide_all_processes(monkeypatch):
    from armada.serve import Handler
    replies = iter(["", "origin/main", "1", "v0.99.76", "updated"])
    calls = []
    def run(args, **kwargs):
        assert_hidden(kwargs)
        assert kwargs["stdin"] == subprocess.DEVNULL
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout=next(replies), stderr="")
    monkeypatch.setattr(subprocess, "run", run)
    handler = object.__new__(Handler)
    assert handler._git_check()["newer"]
    assert handler._git_pull()["ok"]
    assert len(calls) == 5


@pytest.mark.skipif(os.name != "nt", reason="Windows console allocation")
def test_real_background_child_has_no_console():
    result = subprocess.run([sys.executable, "-c",
        "import ctypes; print(bool(ctypes.windll.kernel32.GetConsoleWindow()))"],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=10,
        **background.process_options())
    assert result.returncode == 0 and result.stdout.strip() == "False"


@pytest.mark.skipif(os.name != 'nt', reason='Windows environment probe')
def test_system_memory_refresh_never_launches_platform_shell_fallback(monkeypatch, tmp_path):
    import platform
    from armada import memory
    # WMI failures in Python's platform helper previously fell back to `ver`.
    # Reject both that helper and any child launch, rather than simulating a healthy WMI.
    def forbidden(*args, **kwargs):
        pytest.fail('Environment refresh must use native APIs, never WMI/shell probes')
    monkeypatch.setattr(platform, 'uname', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    (tmp_path/'realm.json').write_text('{"name":"Environment fixture"}', encoding='utf-8')
    result = memory.refresh_system_memory(tmp_path, trigger='test-periodic-refresh')
    assert result['changed']
    env = memory.default_env()
    assert env['Operating system'].startswith('Windows') and env['Machine'] and env['CPU']


@pytest.mark.skipif(os.name != 'nt', reason='Windows supervised launch')
@pytest.mark.parametrize('rpc', [False, True])
def test_supervised_streams_hide_windows_and_keep_suspended_job_assignment(monkeypatch, rpc):
    from armada.engine import process
    real_popen = subprocess.Popen
    calls = []
    def checked(args, **kwargs):
        assert_hidden(kwargs)
        assert kwargs['creationflags'] & 0x4
        calls.append(args)
        return real_popen(args, **kwargs)
    monkeypatch.setattr(subprocess, 'Popen', checked)
    args = [sys.executable, '-c', 'import ctypes,json; print(json.dumps({"console":bool(ctypes.windll.kernel32.GetConsoleWindow())}),flush=True)']
    seen = []
    if rpc:
        result = process.supervise_rpc(args, start=lambda send: None,
            on_message=lambda item, send: seen.append(item) or True, timeout=10)
    else:
        import json
        result = process.supervise(args, prompt='', on_line=lambda line: seen.append(json.loads(line)), timeout=10)
    assert not result.error and seen == [{'console': False}] and calls
