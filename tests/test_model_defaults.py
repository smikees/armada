"""A confirmed team-wide change must preserve unrelated state and recover from a failed save."""
import pytest

from armada import modeldefaults, reader, serve, util
from armada.engine import codex
from armada.webui import pages


@pytest.fixture
def realm(tmp_path, monkeypatch):
    root = tmp_path / "realm"
    root.mkdir()
    util.write_json_atomic(root / "realm.json", {
        "name": "Test realm", "default_model": "opus", "timezone": "Europe/Madrid",
        "notifications": {"job_failed": True},
    })
    for aid in ("hand", "finance"):
        util.write_json_atomic(root / "agents" / aid / "agent.json", {
            "id": aid, "coordinator": aid == "hand", "model": "opus", "effort": "high",
            "verbosity": "full", "toolkit": {"connectors": ["ibkr"]},
        })
    util.write_json_atomic(root / "agents" / "finance" / "jobs.json", {
        "jobs": [{"id": "daily", "model": "opus", "effort": "high", "enabled": True}],
    })
    util.write_json_atomic(root / "retired" / "old" / "agent.json", {"model": "opus"})
    monkeypatch.setattr(modeldefaults.models, "options", lambda r: [
        ("opus", "Claude Opus"), ("gpt-6-sol", "OpenAI GPT-6 Sol"),
    ])
    monkeypatch.setattr(codex, "cached_models", lambda: [{
        "slug": "gpt-6-sol", "supported_reasoning_levels": [{"effort": "medium"}, {"effort": "high"}],
    }])
    return root


def originals(root):
    return {p: p.read_bytes() for p in root.rglob("*.json")}


def test_bulk_updates_coordinator_and_members_preserving_jobs_and_grants(realm):
    before = originals(realm)
    assert modeldefaults.apply_to_agents(realm, "gpt-6-sol", "medium", "standard") == {
        "ok": True, "agents": 2,
    }
    for aid in ("hand", "finance"):
        cfg = util.read_json_state(realm / "agents" / aid / "agent.json")
        assert (cfg["model"], cfg["effort"], cfg["verbosity"]) == ("gpt-6-sol", "medium", "standard")
        assert cfg["toolkit"] == {"connectors": ["ibkr"]}
        assert cfg["coordinator"] == (aid == "hand")
    cfg = util.read_json_state(realm / "realm.json")
    assert (cfg["default_model"], cfg["default_effort"], cfg["default_verbosity"]) == (
        "gpt-6-sol", "medium", "standard")
    assert cfg["name"] == "Test realm" and cfg["timezone"] == "Europe/Madrid"
    assert cfg["notifications"] == {"job_failed": True}
    for path, content in before.items():
        if path.name == "jobs.json" or "retired" in path.parts:
            assert path.read_bytes() == content
    backups = list((realm / ".armada" / "backups").glob("*.json"))
    assert len(backups) == 1
    saved = util.read_json_state(backups[0])["files"]
    for relative, text in saved.items():
        assert text.encode("utf-8") == before[realm / relative]


@pytest.mark.parametrize("model,effort,level", [
    ("unlisted-model", "medium", "standard"), ("gpt-6-sol", "bogus", "standard"),
    ("gpt-6-sol", "max", "standard"), ("gpt-6-sol", "medium", "bogus"),
    ("gpt-6-sol", "medium", []),
])
def test_invalid_combination_changes_nothing(realm, model, effort, level):
    before = originals(realm)
    with pytest.raises(ValueError):
        modeldefaults.apply_to_agents(realm, model, effort, level)
    assert originals(realm) == before


def test_corrupt_agent_prevents_all_changes(realm):
    (realm / "agents" / "hand" / "agent.json").write_text("{broken", encoding="utf-8")
    before = originals(realm)
    with pytest.raises(util.StateError):
        modeldefaults.apply_to_agents(realm, "gpt-6-sol", "medium", "standard")
    assert originals(realm) == before


@pytest.mark.parametrize("fail_target", ["hand", "realm"])
def test_mid_save_failure_restores_exact_original_files(realm, monkeypatch, fail_target):
    # Include a BOM and CRLF to ensure rollback does not reserialize the original settings.
    path = realm / "agents" / "finance" / "agent.json"
    path.write_bytes(b'\xef\xbb\xbf{\r\n  "id": "finance", "model": "opus"\r\n}\r\n')
    before = originals(realm)
    target = realm / "realm.json" if fail_target == "realm" else realm / "agents" / "hand" / "agent.json"
    write = util.write_json_atomic
    def failing_write(path, cfg):
        if path == target:
            raise OSError("disk failure")
        write(path, cfg)
    monkeypatch.setattr(util, "write_json_atomic", failing_write)
    with pytest.raises(util.StateError, match="All changes were restored"):
        modeldefaults.apply_to_agents(realm, "gpt-6-sol", "medium", "standard")
    for path, content in before.items():
        assert path.read_bytes() == content


def test_route_updates_only_its_selected_realm(realm, tmp_path):
    other = tmp_path / "other" / "realm.json"
    util.write_json_atomic(other, {"name": "Other", "default_model": "opus"})
    original = other.read_bytes()
    handler = object.__new__(serve.Handler)
    handler.realm = str(realm)
    assert handler._set_all_agent_defaults({
        "model": "gpt-6-sol", "effort": "medium", "verbosity": "standard",
    })["ok"]
    assert other.read_bytes() == original
    assert not handler._set_all_agent_defaults({"model": "gpt-6-sol"})["ok"]


def test_settings_owns_defaults_and_leaves_realm_selection_to_header(realm):
    html = pages.render_settings(reader.read(realm), realm, False, "", [])
    assert 'id="st-realm"' not in html
    assert 'id="st-realmname"' in html
    assert "Model defaults" in html and "AI provider &amp; defaults" not in html
    assert 'See connected providers in <a href="/settings?tab=app">App settings</a>.' in html
    group = html.split('class="mc-realm-model-defaults"')[1].split('id="st-cons"')[0]
    for field in ("st-model", "st-effort", "st-verbosity"):
        assert f'id="{field}"' in group
    assert 'onclick="mcSetAllAgentDefaults(this)"' in html
