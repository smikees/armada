"""A realm grant and a provider connection are independent, and both apply next turn."""
import json
import subprocess
import shutil
from pathlib import Path
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


DRIVE = {"id": "claude.ai Google Drive", "name": "Google Drive",
         "command": "https://drivemcp.googleapis.com/mcp/v1", "enabled": True}


def test_portable_drive_name_is_stable_and_does_not_collide():
    sid = connector_runtime.registration_id(DRIVE['id'])
    assert sid == connector_runtime.registration_id(DRIVE['id'])
    assert connector_runtime._SERVER_ID.fullmatch(sid)
    assert sid != connector_runtime.registration_id('claude.ai Google/Drive')
    assert connector_runtime.registration_id(IBKR['id']) == IBKR['id']
    assert connector_runtime.codex_connection(DRIVE, {}) == 'missing'
    assert connector_runtime.codex_connection(DRIVE, {sid: {'name': sid, 'enabled': True,
        'transport': {'url': DRIVE['command']}, 'auth_status': 'o_auth'}}) == 'ready'


@pytest.mark.parametrize('provider', ['claude', 'codex', 'gemini'])
def test_independent_provider_actions_and_reasons(provider):
    detail = connector_runtime.connection_detail(DRIVE, provider, 'missing')
    assert detail['action'] == ('connect' if provider == 'codex' else 'setup')
    assert provider.title() in detail['reason']
    assert connector_runtime.connection_detail(DRIVE, provider, 'provider_disabled')['action'] == 'provider_settings'
    assert connector_runtime.connection_detail(DRIVE, provider, 'realm_disabled')['action'] == ''
    assert connector_runtime.connection_detail(DRIVE, provider, 'ready')['action'] == ''


def test_gemini_registration_never_claims_live_connection():
    sid = connector_runtime.registration_id(DRIVE['id'])
    assert connector_runtime.gemini_connection(DRIVE, {sid: {'serverUrl': DRIVE['command']}}) == 'configured'
    assert connector_runtime.gemini_connection(DRIVE, {sid: {'serverUrl': 'https://other.invalid/mcp'}}) == 'different'
    assert connector_runtime.gemini_connection(DRIVE, {sid: {'serverUrl': DRIVE['command'], 'disabled': True}}) == 'disabled'
    assert connector_runtime.gemini_connection(DRIVE, None) == 'unknown'
    assert connector_runtime.gemini_connection({'id': 'claude.ai private', 'command': 'https://claude.invalid/proxy'}, {}) == 'unsupported'


def test_setup_uses_correct_provider_schema_without_credentials():
    gemini = connector_runtime.connector_setup(DRIVE, 'gemini')
    sid = connector_runtime.registration_id(DRIVE['id'])
    assert json.loads(gemini['snippet']) == {'mcpServers': {sid: {'serverUrl': DRIVE['command']}}}
    assert 'OAuth' in gemini['instructions']
    assert 'service_guide_url' in gemini
    claude = connector_runtime.connector_setup(DRIVE, 'claude')
    assert claude['web_url'] == 'https://claude.ai/settings/connectors'
    assert claude['snippet'] == ''
    codex = connector_runtime.connector_setup({'id': 'claude_ai_private', 'command': 'https://proxy.invalid'}, 'codex')
    assert codex['snippet'] == '' and 'no reviewed portable endpoint' in codex['instructions']


def test_claude_sign_in_targets_existing_name_and_preserves_other_providers(monkeypatch, tmp_path):
    monkeypatch.setattr(connector_runtime, '_claude_rows', lambda root: [{'name': DRIVE['id'], 'ready': False}])
    monkeypatch.setattr(ClaudeEngine, '_launcher', lambda self: ['claude'])
    launched = []
    monkeypatch.setattr(connector_runtime.subprocess, 'Popen', lambda args, **kw: launched.append((args, kw)))
    assert connector_runtime.connect_claude(DRIVE, tmp_path) == {'ok': True, 'state': 'sign_in'}
    assert launched[0][0] == ['claude', 'mcp', 'login', DRIVE['id']]
    assert launched[0][1]['cwd'] == tmp_path
    assert launched[0][1]['stdin'] == subprocess.DEVNULL


def test_connector_actions_validate_realm_provider_and_enabled_state(tmp_path, monkeypatch):
    from armada import providers
    (tmp_path/'realm.json').write_text(json.dumps({'toolkit': {'connectors': [DRIVE]}}))
    handler = CapabilityRoutes(); handler.realm = tmp_path
    calls = []
    monkeypatch.setattr(providers, 'status', lambda p, force=False: {'connected': True})
    monkeypatch.setattr(connector_runtime, 'connect_codex', lambda cap, root: calls.append(cap['id']) or {'ok': True})
    assert handler._connector_action({'provider': 'codex', 'action': 'connect', 'capability': DRIVE['id']})['ok']
    assert calls == [DRIVE['id']]
    assert not handler._connector_action({'provider': 'unknown', 'action': 'connect', 'capability': DRIVE['id']})['ok']
    assert not handler._connector_action({'provider': 'codex', 'action': 'connect', 'capability': 'ambient'})['ok']
    (tmp_path/'realm.json').write_text(json.dumps({'toolkit': {'connectors': [{**DRIVE, 'enabled': False}]}}))
    assert not handler._connector_action({'provider': 'codex', 'action': 'connect', 'capability': DRIVE['id']})['ok']
    assert calls == [DRIVE['id']]


def test_recheck_only_refreshes_requested_provider(tmp_path, monkeypatch):
    from armada import providers
    connector_runtime._connection_checks.clear()
    (tmp_path/'realm.json').write_text(json.dumps({'toolkit': {'connectors': [DRIVE]}}))
    calls = []
    monkeypatch.setattr(providers, 'status', lambda p, force=False: calls.append(p) or {'connected': True})
    monkeypatch.setattr(connector_runtime, 'claude_inventory', lambda: {'claudeaigoogledrive': True})
    monkeypatch.setattr(connector_runtime, 'codex_live_inventory', lambda root: {})
    monkeypatch.setattr(connector_runtime, 'gemini_inventory', lambda: {})
    snapshot = connector_runtime.connection_snapshot(tmp_path)
    assert not snapshot['pending']
    assert snapshot['connectors'][DRIVE['id']]['claude'] == 'ready'
    assert snapshot['connectors'][DRIVE['id']]['codex'] == 'missing'
    calls.clear()
    snapshot = connector_runtime.connection_snapshot(tmp_path, force=True, provider='codex')
    assert calls == ['codex']
    assert snapshot['connectors'][DRIVE['id']]['claude'] == 'ready'


def test_targeted_recheck_with_empty_cache_does_not_probe_other_providers(tmp_path, monkeypatch):
    from armada import providers
    connector_runtime._connection_checks.clear()
    (tmp_path/'realm.json').write_text(json.dumps({'toolkit': {'connectors': [DRIVE]}}))
    calls = []
    monkeypatch.setattr(providers, 'status', lambda p, force=False: calls.append(p) or {'connected': True})
    monkeypatch.setattr(connector_runtime, 'codex_live_inventory', lambda root: {})
    snapshot = connector_runtime.connection_snapshot(tmp_path, force=True, provider='codex')
    assert calls == ['codex']
    assert snapshot['providers']['claude'] == snapshot['providers']['gemini'] == 'unknown'


def test_claude_ambiguous_registration_is_not_connected(monkeypatch):
    monkeypatch.setattr(connector_runtime, '_claude_rows', lambda: [
        {'name': 'claude.ai Google Drive', 'ready': True}, {'name': 'claude_ai_Google_Drive', 'ready': True}])
    assert connector_runtime.claude_connection(DRIVE, connector_runtime.claude_inventory()) == 'different'


def test_timed_out_check_can_be_replaced(tmp_path, monkeypatch):
    from concurrent.futures import Future
    from armada import providers
    connector_runtime._connection_checks.clear()
    (tmp_path/'realm.json').write_text(json.dumps({'toolkit': {'connectors': [DRIVE]}}))
    monkeypatch.setattr(providers, 'status', lambda *a, **kw: {'connected': True})
    monkeypatch.setattr(connector_runtime, 'codex_live_inventory', lambda root: {})
    connector_runtime.connection_snapshot(tmp_path, provider='codex')
    key = next(k for k in connector_runtime._connection_checks if k[1] == 'codex')
    hung = Future()
    connector_runtime._connection_checks[key] = {'future': hung, 'started': -1000, 'finished': -1000}
    snapshot = connector_runtime.connection_snapshot(tmp_path, force=True, provider='codex')
    assert snapshot['connectors'][DRIVE['id']]['codex'] == 'missing'
    assert connector_runtime._connection_checks[key]['future'] is not hung


@pytest.mark.skipif(shutil.which('node') is None, reason='Node required for UI action checks')
def test_provider_controls_in_browser_script():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([shutil.which('node'), str(root/'tests/connector_controls_harness.js'),
        str(root/'armada/webui/static/js/connmodal.js')], capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr
