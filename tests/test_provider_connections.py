"""App connections, onboarding and Alexander never depend on real CLI credentials in tests."""
import json
from types import SimpleNamespace

import pytest

from armada import appconfig, auth, models, providers, setupflow
from armada import provider_login, provider_install
from armada.alexander import config as alex
from armada.engine.codex import CodexEngine
from armada.engine.contracts import RunRequest, validate_request
from armada.engine.claude import ClaudeEngine


@pytest.fixture
def connections(monkeypatch):
    live = {"claude": False, "codex": False}
    monkeypatch.setattr(auth, "status", lambda force=False: {
        "ok": True, "logged_in": live["claude"], "version": "2.1.280", "method": "Claude"})
    monkeypatch.setattr(CodexEngine, "_launcher", lambda self: ["codex-fixture"])
    monkeypatch.setattr(CodexEngine, "_probe", lambda self, args: SimpleNamespace(stdout='codex-cli 1.2.3', returncode=0))
    monkeypatch.setattr(ClaudeEngine, "_launcher", lambda self: ["claude-fixture"])
    monkeypatch.setattr(CodexEngine, "auth_status", lambda self: {
        "ok": True, "logged_in": live["codex"], "method": "ChatGPT"})
    monkeypatch.setattr("armada.engine.codex.cached_models", lambda: [
        {"slug": "gpt-6-sol", "supported_reasoning_levels": [{"effort": "medium"}, {"effort": "high"}]}])
    monkeypatch.setattr(provider_login, "_attempts", {})
    monkeypatch.setattr(provider_install, "_states", {})
    yield live


@pytest.mark.parametrize("connected", [[], ["claude"], ["codex"], ["claude", "codex"]])
def test_picker_tracks_actual_connections(connections, connected, tmp_path):
    from armada.engine.selection import model_provider
    connections.update({p: p in connected for p in connections})
    providers.statuses()
    # App connections supersede historical per-realm provider checkboxes.
    (tmp_path / "realm.json").write_text('{"providers":["claude"]}')
    assert {model_provider(m) for m, _ in models.options(tmp_path)} == set(connected)


@pytest.mark.parametrize("provider", ["claude", "codex"])
def test_disconnect_blocks_calls_preserves_cli_login_and_agent_model(connections, provider, tmp_path):
    connections[provider] = True
    providers.statuses()
    saved = tmp_path / "agent.json"
    saved.write_text('{"model":"unchanged"}')
    assert providers.disconnect(provider)["ok"]
    assert connections[provider] is True
    assert not providers.status(provider)["connected"]
    assert json.loads(saved.read_text())["model"] == "unchanged"
    with pytest.raises(ValueError, match="disconnected"):
        validate_request(provider, ClaudeEngine.capabilities, RunRequest("", ""))
    assert providers.connect(provider)["connected"]
    assert providers.status(provider)["connected"]


@pytest.mark.parametrize("provider", ["claude", "codex"])
def test_connect_uses_owned_login_and_callback_cannot_undo_disconnect(connections, provider, monkeypatch):
    calls = []
    monkeypatch.setattr(provider_login, "begin", lambda p, cmd: calls.append((p, cmd)) or {"ok": True, "pending": True})
    assert providers.connect(provider)["pending"]
    assert calls == [(provider, [provider + "-fixture"])]
    assert not providers.connected()
    # Disconnect while OAuth is in flight: a later callback must not enable Armada.
    providers.disconnect(provider)
    connections[provider] = True
    assert not providers.status(provider)["connected"]


@pytest.mark.parametrize("connected,expected", [
    (["claude"], ("claude", "claude-opus-5-5", "medium")),
    (["codex"], ("codex", "gpt-6-sol", "medium")),
    (["claude", "codex"], ("claude", "claude-opus-5-5", "medium")),
])
def test_alexander_automatic_preferences(connections, connected, expected, tmp_path):
    connections.update({p: p in connected for p in connections})
    assert alex.resolve(tmp_path) == expected


def test_no_provider_gives_actionable_support_error(connections, tmp_path):
    with pytest.raises(ValueError, match="Connect Claude, Codex or Gemini"):
        alex.resolve(tmp_path)


def test_alexander_override_is_app_wide_and_not_silently_replaced(connections, tmp_path):
    connections.update(claude=True, codex=True)
    providers.statuses()
    alex.save(tmp_path, "gpt-6-sol", "high")
    assert alex.resolve(tmp_path / "another-realm") == ("codex", "gpt-6-sol", "high")
    providers.disconnect("codex")
    with pytest.raises(ValueError, match="selected provider is disconnected"):
        alex.resolve(tmp_path)
    assert alex.load()["model"] == "gpt-6-sol"


@pytest.mark.parametrize("model,effort", [("gpt-secret", "high"), ("gpt-6-sol", "max"), ("auto", "ultra")])
def test_invalid_alexander_settings_do_not_save(connections, tmp_path, model, effort):
    connections["codex"] = True
    providers.statuses()
    with pytest.raises(ValueError):
        alex.save(tmp_path, model, effort)
    assert alex.load() == {"model": "auto", "effort": "auto", "verbosity": "standard"}


def test_alexander_verbosity_is_validated_and_preserved(connections, tmp_path):
    alex.save(tmp_path, "auto", "auto", "brief")
    assert alex.load()["verbosity"] == "brief"
    alex.save(tmp_path, "auto", "high")  # older clients omit verbosity
    assert alex.load()["verbosity"] == "brief"
    with pytest.raises(ValueError, match="verbosity"):
        alex.save(tmp_path, "auto", "auto", "invalid")
    assert alex.load()["verbosity"] == "brief"


def test_codex_only_wizard_sets_executable_defaults(connections, tmp_path):
    from armada.setup import scaffold
    scaffold(str(tmp_path / "realm"), "company", "Test")
    root = tmp_path / "realm"
    setupflow.begin(root, connected_providers=["codex"])
    cfg = json.loads((root / "realm.json").read_text())
    assert cfg["provider"] == "codex" and cfg["default_model"] == "gpt-6-sol"
    from armada.engine.selection import engine_for
    assert engine_for(root, "cfo") == "codex"


@pytest.mark.parametrize('connected', [['claude'], ['codex'], ['claude', 'codex']])
def test_new_realm_defaults_match_alexander(connections, tmp_path, connected):
    from armada.setup import scaffold
    connections.update({p: p in connected for p in connections})
    root = scaffold(tmp_path / 'realm', 'company', 'Home')
    expected = alex.resolve(root)
    assert setupflow.begin(root, owner='Alex', connected_providers=connected)['ok']
    cfg = json.loads((root / 'realm.json').read_text())
    assert (cfg['provider'], cfg['default_model'], cfg['default_effort']) == expected


def test_new_realm_uses_explicit_alexander_preference(connections, tmp_path):
    from armada.setup import scaffold
    connections.update(claude=True, codex=True)
    appconfig.save({'alexander': {'model': 'gpt-6-sol', 'effort': 'high'}})
    root = scaffold(tmp_path / 'realm', 'company', 'Home')
    setupflow.begin(root, connected_providers=['claude', 'codex'])
    cfg = json.loads((root / 'realm.json').read_text())
    assert cfg['default_model'] == 'gpt-6-sol' and cfg['default_effort'] == 'high'


def test_codex_status_includes_cli_version(connections):
    assert providers.status('codex')['version'] == '1.2.3'


def test_provider_probe_failure_removes_available_models(connections, tmp_path, monkeypatch):
    connections["codex"] = True
    providers.statuses()
    monkeypatch.setattr(CodexEngine, "auth_status", lambda self: {"ok": False, "logged_in": False})
    providers.statuses()
    assert models.options(tmp_path) == []


def test_connection_updates_do_not_lose_other_app_preferences(connections):
    appconfig.save({"theme": "test", "alexander": {"model": "auto", "effort": "high"}})
    providers.statuses()
    providers.disconnect("claude")
    appconfig.save({"theme": "changed"})
    assert not providers.allowed("claude")
    assert alex.load()["effort"] == "high" and appconfig.get("theme") == "changed"


def test_outdated_claude_must_be_updated_before_login(connections, monkeypatch):
    monkeypatch.setattr(auth, "status", lambda **kw: {"ok": True, "logged_in": False, "version": "2.1.263"})
    assert "Update Claude Code" in providers.connect("claude")["error"]
    assert providers.status("claude")["installed"]


def test_failed_login_reports_retry_without_marking_connected(connections):
    provider_login._attempts["codex"] = {"pending": False, "error": "Please retry."}
    state = providers.status("codex")
    assert not state["connected"] and not state["pending"]
    assert "retry" in state["login_error"]


def test_explicit_codex_home_is_created_before_login_probe(connections, monkeypatch, tmp_path):
    target = tmp_path / "new-codex-home"
    monkeypatch.setenv("CODEX_HOME", str(target))
    def begin(*args):
        assert target.is_dir()
        return {"ok": True, "pending": True}
    monkeypatch.setattr(provider_login, "begin", begin)
    assert providers.connect("codex")["pending"]


def test_missing_cli_cannot_be_connected_even_if_auth_cache_says_yes(connections, monkeypatch):
    connections["claude"] = True
    monkeypatch.setattr(ClaudeEngine, "_launcher", lambda self: None)
    state = providers.status("claude")
    assert not state["installed"] and not state["connected"]
