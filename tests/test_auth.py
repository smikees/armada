"""Claude sign-in detection and the in-app re-auth launch.

The boundary under test: ARMADA must be able to tell you it's signed out and start the official
flow — without ever handling a credential itself.
"""
import json
import re
import subprocess
from pathlib import Path

import pytest

from armada import auth


@pytest.fixture(autouse=True)
def _clear_cache():
    auth._CACHE["data"] = None
    auth._CACHE["at"] = 0.0
    yield
    auth._CACHE["data"] = None


def _fake_run(stdout, rc=0):
    def run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, rc, stdout=stdout, stderr="")
    return run


def test_signed_out_is_detected_despite_nonzero_exit(monkeypatch):
    """`claude auth status` exits non-zero when signed out — the payload is the truth, not the
    return code. Trusting returncode would report 'unknown' instead of 'signed out'."""
    monkeypatch.setattr(auth, "_launcher", lambda: ["claude"])
    monkeypatch.setattr(auth.subprocess, "run",
                        _fake_run(json.dumps({"loggedIn": False, "authMethod": "none"}), rc=1))
    s = auth.status(force=True)
    assert s["ok"] is True and s["logged_in"] is False


def test_signed_in_is_detected(monkeypatch):
    monkeypatch.setattr(auth, "_launcher", lambda: ["claude"])
    monkeypatch.setattr(auth.subprocess, "run",
                        _fake_run(json.dumps({"loggedIn": True, "authMethod": "claudeai"}), rc=0))
    s = auth.status(force=True)
    assert s["logged_in"] is True and s["method"] == "claudeai"


def test_missing_cli_is_reported_not_raised(monkeypatch):
    monkeypatch.setattr(auth, "_launcher", lambda: None)
    s = auth.status(force=True)
    assert s["logged_in"] is False and s["reason"] == "cli-missing"


@pytest.mark.parametrize("stdout", ["", "not json", "{", "null"])
def test_unreadable_status_never_raises(monkeypatch, stdout):
    monkeypatch.setattr(auth, "_launcher", lambda: ["claude"])
    monkeypatch.setattr(auth.subprocess, "run", _fake_run(stdout))
    s = auth.status(force=True)
    assert s["logged_in"] is False and isinstance(s.get("reason"), str)


def test_probe_failure_never_raises(monkeypatch):
    def boom(*a, **k):
        raise OSError("cli exploded")
    monkeypatch.setattr(auth, "_launcher", lambda: ["claude"])
    monkeypatch.setattr(auth.subprocess, "run", boom)
    assert auth.status(force=True)["logged_in"] is False


def test_status_is_cached_then_refreshed_on_force(monkeypatch):
    calls = {"n": 0}

    def run(cmd, **kw):
        calls["n"] += 1
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps({"loggedIn": True}), stderr="")
    monkeypatch.setattr(auth, "_launcher", lambda: ["claude"])
    monkeypatch.setattr(auth.subprocess, "run", run)
    auth.status(force=True)
    auth.status()               # served from cache
    assert calls["n"] == 1
    auth.status(force=True)     # explicit refresh after a sign-in attempt
    assert calls["n"] == 2


def test_login_invokes_the_official_flow(monkeypatch):
    seen = {}

    def popen(cmd, **kw):
        seen["cmd"] = cmd
        seen["kw"] = kw
        return object()
    monkeypatch.setattr(auth, "_launcher", lambda: ["claude"])
    monkeypatch.setattr(auth.subprocess, "Popen", popen)
    assert auth.start_login()["ok"] is True
    assert seen["cmd"] == ["claude", "auth", "login", "--claudeai"]


def test_login_invalidates_cached_status(monkeypatch):
    monkeypatch.setattr(auth, "_launcher", lambda: ["claude"])
    monkeypatch.setattr(auth.subprocess, "Popen", lambda *a, **k: object())
    auth._CACHE["data"] = {"logged_in": False}
    auth.start_login()
    assert auth._CACHE["data"] is None        # next poll must re-ask, not serve a stale "no"


def test_login_without_cli_reports_cleanly(monkeypatch):
    monkeypatch.setattr(auth, "_launcher", lambda: None)
    r = auth.start_login()
    assert r["ok"] is False and r["error"]


def test_login_failure_never_raises(monkeypatch):
    def boom(*a, **k):
        raise OSError("nope")
    monkeypatch.setattr(auth, "_launcher", lambda: ["claude"])
    monkeypatch.setattr(auth.subprocess, "Popen", boom)
    assert auth.start_login()["ok"] is False


def test_armada_never_touches_credentials():
    """The load-bearing boundary: ARMADA starts Claude Code's flow and asks about the result. It
    must never read, write, or transport a token itself."""
    src = Path(auth.__file__).read_text(encoding="utf-8")
    code = re.sub(r"#[^\n]*|\"\"\".*?\"\"\"", "", src, flags=re.S)   # ignore comments/docstrings
    for forbidden in ("accessToken", "refreshToken", "credentials.json", "setup-token"):
        assert forbidden not in code, f"auth.py must not deal in {forbidden}"


def test_banner_js_only_asks_and_launches():
    js = (Path(auth.__file__).parent / "webui" / "static" / "js" / "authbar.js").read_text(encoding="utf-8")
    assert "/api/auth-status" in js and "/api/auth-login" in js
    code = re.sub(r"//[^\n]*", "", js)          # prose about tokens is fine; code touching them isn't
    for forbidden in ("token", "password", "apiKey", "api_key"):
        assert forbidden not in code, f"the banner must not handle {forbidden}"
