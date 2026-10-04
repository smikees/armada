"""New teams use available engines and survive a newer, unfamiliar model catalogue."""
import itertools
import json

import pytest

from armada import appconfig, setupflow
from armada.engine.defaults import PREFERENCES, choose
from armada.engine.selection import engine_for
from armada.runner import _resolve_effort, _resolve_model
from armada.setup import scaffold


CATALOGUES = {provider: [{"id": mids[0]}] for provider, mids in PREFERENCES}
COMBINATIONS = [p for n in range(1, 4) for p in itertools.combinations(CATALOGUES, n)]


@pytest.mark.parametrize("connected", COMBINATIONS)
def test_release_priority_only_considers_connected_engines(connected):
    states = {p: {"connected": p in connected} for p in CATALOGUES}
    cfg = choose(states, CATALOGUES)
    provider = next(p for p, _ in PREFERENCES if p in connected)
    assert cfg["provider"] == provider
    assert cfg["default_model"] == CATALOGUES[provider][0]["id"]
    assert cfg["default_effort"] == "medium"
    assert cfg["providers"] == list(connected)
    assert cfg["default_selection"]["release"]


@pytest.mark.parametrize("provider", CATALOGUES)
@pytest.mark.parametrize("rows", [[], [{"id": "future-model-never-seen-by-this-release"}],
    [{"id": "claude-opus-5-5", "active": False}], [None, "malformed"], {"unexpected": "shape"}])
def test_no_recognized_available_model_delegates_to_provider(provider, rows):
    cfg = choose({provider: {"connected": True}}, {provider: rows})
    assert cfg["default_model"] == provider + ":default"
    assert cfg["default_effort"] == "auto"


def test_no_login_refuses_and_does_not_confuse_installed_with_connected():
    with pytest.raises(ValueError, match="Connect a provider"):
        choose({p: {"installed": True, "connected": False} for p in CATALOGUES}, CATALOGUES)


def test_unavailable_top_model_uses_next_release_preference():
    cfg = choose({"codex": {"connected": True}}, {"codex": [
        {"slug": "gpt-6.1-sol", "visibility": "hide"},
        {"slug": "gpt-6-sol", "supported_reasoning_levels": [{"effort": "high"}]}]})
    assert cfg["default_model"] == "gpt-6-sol"
    assert cfg["default_effort"] == "high"


@pytest.mark.parametrize("provider", CATALOGUES)
def test_new_agents_inherit_defaults_without_alexander_dependency(tmp_path, provider):
    appconfig.save({"alexander": {"model": "unavailable-obsolete-model", "effort": "max"}})
    cfg = choose({provider: {"connected": True}}, {})
    root = scaffold(tmp_path / "realm", "company", defaults=cfg)
    assert setupflow.begin(root, owner="Test", defaults=cfg)["ok"]
    saved = json.loads((root / "realm.json").read_text())
    assert saved["default_model"] == cfg["default_model"]
    for path in (root / "agents").glob("*/agent.json"):
        agent = json.loads(path.read_text())
        assert not agent.get("model")
        assert engine_for(root, agent) == provider
        assert _resolve_model(root, agent) == ("" if provider == "claude" else provider + ":default")
        assert _resolve_effort(root, agent) == ""
    # A user's explicit choice still takes precedence over automatic realm defaults.
    assert engine_for(root, {"model": "gpt-explicit"}) == "codex"
    assert _resolve_model(root, {"model": "gpt-explicit"}) == "gpt-explicit"
    assert _resolve_effort(root, {"effort": "high"}) == "high"


def test_missing_live_catalogue_never_uses_the_ui_seed(monkeypatch):
    from armada import models
    monkeypatch.setattr(models, "fetch_live_result", lambda: (None, "unreachable"))
    assert choose({"claude": {"connected": True}})["default_model"] == "claude:default"
    assert choose({"gemini": {"connected": True}})["default_model"] == "gemini:default"
