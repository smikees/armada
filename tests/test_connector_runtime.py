"""A realm grant and a provider connection are independent, and both apply next turn."""
import json
import subprocess
import pytest
from types import SimpleNamespace

from armada import capabilities, connector_runtime
from armada.engine.codex import CodexEngine
from armada.engine.claude import ClaudeEngine
from armada.routes.caps import CapabilityRoutes
from armada.webui.capabilities import _cap_card


IBKR = {"id": "claude_ai_Interactive_Brokers_IBKR",
        "catalogue_key": "mcp-registry/connectors/com.ibkr/interactive-brokers-ibkr",
        "command": "https://api.ibkr.com/v1/api/mcp", "status": "connected"}


def test_ibkr_claude_connection_is_not_codex_connection():
    assert connector_runtime.codex_endpoint(IBKR) == "https://api.ibkr.com/v1/api/mcp-public"
    assert connector_runtime.codex_connection(IBKR, {}) == "missing"
    configured = {IBKR["id"]: {"name": IBKR["id"], "enabled": True,
                              "transport": {"url": connector_runtime.codex_endpoint(IBKR)},
                              "auth_status": "not_logged_in"}}
    assert connector_runtime.codex_connection(IBKR, configured) == "sign_in"
    configured[IBKR["id"]]["auth_status"] = "o_auth"
    assert connector_runtime.codex_connection(IBKR, configured) == "ready"


def test_unknown_claude_proxy_cannot_be_registered_in_codex(monkeypatch):
    cap = {"id": "claude_ai_private", "command": "https://claude.example/proxy"}
    assert connector_runtime.codex_endpoint(cap) == ""
    assert not connector_runtime.connect_codex(cap)["ok"]


def test_capability_card_waits_for_provider_specific_status(tmp_path):
    (tmp_path / "realm.json").write_text(json.dumps({"toolkit": {"connectors": [IBKR]}}), encoding="utf-8")
    card = _cap_card(IBKR, kind="connectors", realm=SimpleNamespace(agents=[], members=[]),
                     realm_root=tmp_path)
    assert "Connected in Claude" not in card
    assert 'data-provider="claude"' in card
    assert 'data-provider="codex"' in card
    assert "Checking connection" in card
    assert 'style="display:none"' in card  # actions stay hidden until the async status arrives


def test_connection_snapshot_never_promotes_stale_realm_status(tmp_path, monkeypatch):
    from armada import providers
    (tmp_path / "realm.json").write_text(json.dumps({"toolkit": {"connectors": [IBKR]}}), encoding="utf-8")
    monkeypatch.setattr(providers, "status", lambda provider, force=False:
                        {"connected": provider == "codex", "enabled": True})
    monkeypatch.setattr(connector_runtime, "codex_live_inventory", lambda root, engine=None: {
        IBKR["id"]: {"name": IBKR["id"], "enabled": True,
                     "transport": {"url": connector_runtime.codex_endpoint(IBKR)},
                     "auth_status": "o_auth"}})
    monkeypatch.setattr(connector_runtime, "claude_inventory", lambda: None)
    snapshot = connector_runtime.connection_snapshot(tmp_path)
    assert snapshot["providers"] == {"claude": "unavailable", "codex": "ready", "gemini": "unavailable"}
    assert snapshot["connectors"][IBKR["id"]]["claude"] == "unavailable"
    assert snapshot["connectors"][IBKR["id"]]["codex"] == "ready"


def test_live_startup_error_overrides_saved_oauth_label():
    inventory = {IBKR["id"]: {"name": IBKR["id"], "enabled": True,
        "transport": {"url": connector_runtime.codex_endpoint(IBKR)}, "auth_status": "o_auth",
        "runtime_state": "sign_in", "runtime_error": "invalid_grant: Refresh token is not active"}}
    assert connector_runtime.codex_connection(IBKR, inventory) == "sign_in"


def test_provider_placeholder_is_neither_user_capability_nor_grant(tmp_path):
    phantom = {"id": "codex", "name": "codex", "scope": "MCP server (Claude)",
               "status": "connected", "discovered": True}
    (tmp_path / "realm.json").write_text(json.dumps({"toolkit": {"connectors": [phantom]}}), encoding="utf-8")
    agent = tmp_path / "agents" / "alexander"
    agent.mkdir(parents=True)
    (agent / "agent.json").write_text(json.dumps({"id": "alexander", "coordinator": True}), encoding="utf-8")
    assert capabilities.catalogue(tmp_path)["connectors"] == []
    assert capabilities.execution_policy(tmp_path, "alexander").allowed_mcp_ids == frozenset()


@pytest.mark.parametrize('health', ['Connected', '✓ Connected', '✔ Connected', '√ Connected', '\x1b[32m√ Connected\x1b[0m'])
def test_claude_connector_health_comes_from_live_inventory(monkeypatch, health):
    monkeypatch.setattr(ClaudeEngine, "_launcher", lambda self: ["claude"])
    output = ("Checking MCP server health…\n"
              f"claude.ai Interactive Brokers (IBKR): https://api.ibkr.com/mcp - {health}\n"
              "claude.ai Google Drive: https://drive.example/mcp - ✗ Failed to connect\n")
    monkeypatch.setattr(connector_runtime.subprocess, "run", lambda *a, **kw:
                        SimpleNamespace(returncode=0, stdout=output))
    inventory = connector_runtime.claude_inventory()
    assert connector_runtime.claude_connection(IBKR, inventory) == "ready"
    assert connector_runtime.claude_connection({"id": "claude_ai_Google_Drive"}, inventory) == "failed"


@pytest.mark.parametrize('health', ['Not connected', '√ Failed to connect', '✓ Needs authentication', '✔', '√'])
def test_claude_health_icon_does_not_prove_connection(monkeypatch, health):
    monkeypatch.setattr(ClaudeEngine, '_launcher', lambda self: ['claude'])
    monkeypatch.setattr(connector_runtime.subprocess, 'run', lambda *a, **kw: SimpleNamespace(
        returncode=0, stdout=f'claude.ai Interactive Brokers (IBKR): https://broker.invalid - {health}\n'))
    assert connector_runtime.claude_connection(IBKR, connector_runtime.claude_inventory()) == 'failed'


def test_add_timeout_after_config_write_continues_to_sign_in(monkeypatch):
    class FakeEngine:
        def _launcher(self):
            return ["codex"]
        def _probe(self, args):
            raise subprocess.TimeoutExpired("codex mcp add", 25)
    fake = FakeEngine()
    calls = []
    monkeypatch.setattr(connector_runtime, "CodexEngine", lambda: fake)
    monkeypatch.setattr(connector_runtime, "codex_inventory", lambda engine=None:
        {} if not calls else {IBKR["id"]: {"name": IBKR["id"], "enabled": True,
                                      "transport": {"url": connector_runtime.codex_endpoint(IBKR)},
                                      "auth_status": "not_logged_in"}})
    original_probe = fake._probe
    def probe(args):
        calls.append(args)
        return original_probe(args)
    fake._probe = probe
    launched = []
    monkeypatch.setattr(connector_runtime.subprocess, "Popen", lambda args, **kwargs:
                        launched.append(args))
    assert connector_runtime.connect_codex(IBKR) == {"ok": True, "state": "sign_in"}
    assert launched == [["codex"] + connector_runtime._feature_args() + ["mcp", "login", IBKR["id"]]]


def test_new_grant_reaches_codex_on_the_next_turn(tmp_path, monkeypatch):
    realm = tmp_path / "realm"
    agent = realm / "agents" / "warren"
    agent.mkdir(parents=True)
    (realm / "realm.json").write_text(json.dumps({"toolkit": {"connectors": [IBKR]}}), encoding="utf-8")
    (agent / "agent.json").write_text(json.dumps({"id": "warren", "toolkit": {"connectors": []}}), encoding="utf-8")
    engine = CodexEngine()
    monkeypatch.setattr(engine, "_probe", lambda *a, **kw: SimpleNamespace(returncode=0,
        stdout=json.dumps([{"name": IBKR["id"], "enabled": True}])))
    engine.allowed_mcp_ids = capabilities.execution_policy(realm, "warren").allowed_mcp_ids
    assert f'mcp_servers.{IBKR["id"]}.enabled=false' in engine._mcp_args(True, [])
    assert capabilities.grant(realm, "warren", IBKR["id"])["ok"]
    engine.allowed_mcp_ids = capabilities.execution_policy(realm, "warren").allowed_mcp_ids
    assert f'mcp_servers.{IBKR["id"]}.enabled=false' not in engine._mcp_args(True, [])
    assert capabilities.revoke(realm, "warren", IBKR["id"])["ok"]
    engine.allowed_mcp_ids = capabilities.execution_policy(realm, "warren").allowed_mcp_ids
    assert f'mcp_servers.{IBKR["id"]}.enabled=false' in engine._mcp_args(True, [])


def test_grant_reports_when_codex_sign_in_is_still_needed(tmp_path, monkeypatch):
    realm = tmp_path / "realm"
    agent = realm / "agents" / "warren"
    agent.mkdir(parents=True)
    (realm / "realm.json").write_text(json.dumps({"toolkit": {"connectors": [IBKR]}}), encoding="utf-8")
    (agent / "agent.json").write_text(json.dumps({"id": "warren", "model": "gpt-6-astra",
                                                  "toolkit": {"connectors": []}}), encoding="utf-8")
    monkeypatch.setattr(connector_runtime, "codex_inventory", lambda engine=None: {})
    handler = CapabilityRoutes()
    handler.realm = realm
    result = handler._cap_grant({"agent": "warren", "capability": IBKR["id"]})
    assert result["ok"] and result["provider_connection"] == "missing"
    assert capabilities.may_use(realm, "warren", IBKR["id"])
