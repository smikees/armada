import json
import subprocess
import sys
from pathlib import Path

import pytest

from armada import codex_usage as usage


def test_multiple_buckets_and_missing_windows_are_not_misreported():
    out = usage._normalize({"rateLimits": {"primary": {"usedPercent": 99}},
        "rateLimitsByLimitId": {
            "extra": {"limitName": "Extra models", "primary": {"usedPercent": 0, "windowDurationMins": 300}},
            "codex": {"primary": None, "secondary": {"usedPercent": 6, "windowDurationMins": 10080}}}})
    assert out["available"]
    assert out["groups"][0]["id"] == "codex"
    assert out["groups"][0]["windows"] == [{"label": "Weekly", "window_minutes": 10080,
                                           "pct": 6, "resets_at": "", "resets_in": ""}]
    assert out["groups"][1]["windows"][0]["pct"] == 0
    assert out["groups"][1]["windows"][0]["label"] == "5h window"


def test_unknown_quota_is_unavailable_not_zero():
    assert not usage._normalize({"rateLimits": {"primary": {"usedPercent": None}}})["available"]
    assert not usage._normalize({})["available"]
    assert not usage._normalize(None)["available"]
    assert usage._window({"usedPercent": float("nan")}, "Primary") is None


def test_legacy_bucket_and_reset_countdown():
    import time
    out = usage._normalize({"rateLimits": {"primary": {
        "usedPercent": 12.3, "windowDurationMins": 300, "resetsAt": time.time() + 7200}}})
    window = out["groups"][0]["windows"][0]
    assert window["pct"] == 12.3
    assert window["resets_in"] in ("2h 0m", "1h 59m")


def test_account_request_cache_coalesces_success_and_failure(monkeypatch):
    monkeypatch.setattr(usage, "_CACHE", {"at": 0, "data": None})
    calls = []
    def read():
        calls.append(1)
        raise TimeoutError("not connected")
    monkeypatch.setattr(usage, "_read_limits", read)
    assert usage.fetch()["message"]
    assert not usage.fetch()["available"]
    assert len(calls) == 1


def test_read_only_app_server_handshake_and_cleanup(tmp_path, monkeypatch):
    child = tmp_path / "server.py"
    child.write_text('''import sys,json,time
def read(): return json.loads(sys.stdin.readline())
init=read()
assert init['method']=='initialize'
print(json.dumps({'id':init['id'],'result':{}}),flush=True)
assert read()['method']=='initialized'
req=read()
assert req['method']=='account/rateLimits/read'
print(json.dumps({'method':'unrelated/notification'}),flush=True)
print(json.dumps({'id':req['id'],'result':{'rateLimits':{'primary':{'usedPercent':23}}}}),flush=True)
time.sleep(30)
''', encoding="utf-8")
    real_popen = subprocess.Popen
    children = []
    def spawn(args, **kwargs):
        assert args[-1] == "app-server" and "exec" not in args
        child_proc = real_popen([sys.executable, str(child)], **kwargs)
        children.append(child_proc)
        return child_proc
    monkeypatch.setattr(usage.CodexEngine, "_launcher", lambda self: ["codex"])
    monkeypatch.setattr(usage.subprocess, "Popen", spawn)
    out = usage._read_limits(timeout=3)
    assert out["rateLimits"]["primary"]["usedPercent"] == 23
    assert children[0].poll() is not None


def test_dashboard_renders_openai_without_calling_cli(tmp_path, monkeypatch):
    from tests.golden_support import build_fixture
    from armada import reader
    from armada.webui.pages import render_dashboard
    root = Path(build_fixture(tmp_path / "realm"))
    path = root / "realm.json"
    cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg["providers"] = ["claude", "codex"]
    path.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setattr(usage, "fetch", lambda: pytest.fail("No CLI requests on render"))
    html = render_dashboard(reader.read(root), root)
    assert html.count('id="mc-hdr-limits"') == 1
    assert 'id="mc-hdr-openai-limits"' not in html
    assert 'data-codex-enabled="true"' in html and 'Subscription limits' in html
    header = html[html.index('id="mc-ovh"'):].split('>', 1)[0]
    assert 'height:76px' in header and 'height:auto' not in header


def test_limits_timeout_terminates_silent_process(tmp_path, monkeypatch):
    real_popen = subprocess.Popen
    children = []
    def spawn(args, **kwargs):
        proc = real_popen([sys.executable, "-c", "import time; time.sleep(30)"], **kwargs)
        children.append(proc)
        return proc
    monkeypatch.setattr(usage.CodexEngine, "_launcher", lambda self: ["codex"])
    monkeypatch.setattr(usage.subprocess, "Popen", spawn)
    with pytest.raises(TimeoutError):
        usage._read_limits(timeout=0.2)
    assert children[0].poll() is not None


def test_limits_route_selects_provider_and_rejects_unknown(monkeypatch, tmp_path):
    from armada.routes.dashboard import DashboardRoutes
    from armada import provider_limits
    calls = []
    def read(provider, realm, force):
        calls.append((provider, realm, force))
        return {"available": True, "groups": []}
    monkeypatch.setattr(provider_limits, "read", read)
    class Handler(DashboardRoutes):
        provider = "codex"
        def _query(self): return {"provider": self.provider}
        def _json(self, status, data): self.response = (status, data)
    handler = Handler()
    handler.realm = str(tmp_path)
    handler._get_usage_limits()
    assert handler.response[0] == 200 and handler.response[1]["available"]
    assert calls == [("codex", str(tmp_path), False)]
    handler.provider = "unknown"
    handler._get_usage_limits()
    assert handler.response[0] == 400
