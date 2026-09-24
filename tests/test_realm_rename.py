"""Renaming a realm.

The name is a label, not an identity: everything is keyed on the folder, so no job, memory or run
report refers to a realm by name and renaming breaks nothing. The one thing that can go wrong is
the two stores drifting — realm.json carries the name anywhere the realm goes, while the switcher
and the realm menu read ~/.armada/realms.json — so a rename has to reach both or the same realm
shows two names on one screen.
"""
import json

import pytest

from armada import reader, serve
from armada.routes import _shared


@pytest.fixture
def realm(tmp_path, monkeypatch):
    (tmp_path / "realm.json").write_text(json.dumps({"name": "Old Name", "timezone": "local"}),
                                         encoding="utf-8")
    (tmp_path / "agents").mkdir()
    reg = tmp_path / "registry.json"
    # _save_realm_settings (armada/routes/realm.py) reaches the registry through _shared's own
    # module-level _reg_path — that's the name it actually resolves at call time, so that's what
    # has to be patched (patching armada.serve's copy of the name wouldn't reach it).
    monkeypatch.setattr(_shared, "_reg_path", lambda: reg)
    _shared._reg_save([{"name": "Old Name", "path": str(tmp_path.resolve())},
                       {"name": "Somewhere Else", "path": str(tmp_path / "other")}])
    return tmp_path


def _save(realm_root, body):
    h = serve.Handler.__new__(serve.Handler)
    h.realm = str(realm_root)
    return serve.Handler._save_realm_settings(h, body)


def test_renaming_writes_realm_json(realm):
    assert _save(realm, {"name": "The Cabinet"})["ok"] is True
    assert json.loads((realm / "realm.json").read_text(encoding="utf-8"))["name"] == "The Cabinet"
    assert reader.read(realm).name == "The Cabinet"


def test_renaming_also_updates_the_switcher(realm):
    _save(realm, {"name": "The Cabinet"})
    items = _shared._reg_load()
    assert items[0]["name"] == "The Cabinet"
    assert items[1]["name"] == "Somewhere Else", "only this realm's entry moves"


def test_a_blank_name_falls_back_to_the_folder(realm):
    """A realm with no name at all renders as a gap in the switcher."""
    _save(realm, {"name": "   "})
    assert json.loads((realm / "realm.json").read_text(encoding="utf-8"))["name"] == realm.name


def test_the_name_is_bounded(realm):
    _save(realm, {"name": "x" * 500})
    assert len(json.loads((realm / "realm.json").read_text(encoding="utf-8"))["name"]) == 60


def test_not_sending_a_name_leaves_it_alone(realm):
    """Every other settings save posts the whole form; a payload without the field must not wipe
    the name."""
    _save(realm, {"timezone": "Europe/Bucharest"})
    assert json.loads((realm / "realm.json").read_text(encoding="utf-8"))["name"] == "Old Name"


def test_renaming_a_realm_the_registry_does_not_know(realm, monkeypatch):
    """Adding a realm registers it, but a realm opened by path alone may not be in the list. That
    is not a reason to refuse the rename."""
    _shared._reg_save([{"name": "Somewhere Else", "path": str(realm / "other")}])
    assert _save(realm, {"name": "Unlisted"})["ok"] is True
    assert json.loads((realm / "realm.json").read_text(encoding="utf-8"))["name"] == "Unlisted"
    assert [i["name"] for i in _shared._reg_load()] == ["Somewhere Else"]


def test_the_settings_page_offers_the_field(realm):
    from armada.webui import pages
    html = pages.render_settings(reader.read(realm), realm, True, "ok",
                                 [{"name": "Old Name", "path": str(realm)}])
    assert 'id="st-realmname"' in html and 'value="Old Name"' in html
