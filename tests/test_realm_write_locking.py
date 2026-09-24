"""Every realm.json read-modify-write goes through util.file_lock (Phase 2, 2.9).

realm.json is the one file both the always-on scheduler daemon and the web server write — capscan
and catalogue/realm.py already locked their read-modify-write cycles, but the capability-editing
routes, the dashboard's section editor, and workspace.migrate()/set_root() did not: a save from the
UI landing between the scheduler's own read and write (or two browser tabs racing each other) could
silently lose one side's edit. These tests spy on util.file_lock to confirm each write path now
opens a critical section around its read-modify-write, rather than re-deriving the race by hand.
"""
import json

import pytest

from armada import serve, util, workspace


class _H(serve.Handler):
    """The handler's request machinery isn't needed — only the route method under test."""
    def __init__(self, realm):
        self.realm = str(realm)


@pytest.fixture
def realm(tmp_path):
    r = tmp_path / "realm"
    r.mkdir()
    (r / "realm.json").write_text(json.dumps({"name": "R", "toolkit": {
        "connectors": [], "extensions": [], "skills": [], "plugins": []}}), encoding="utf-8")
    return r


@pytest.fixture
def lock_spy(monkeypatch):
    """Records every target util.file_lock was asked to guard, without changing its behaviour."""
    calls = []
    real = util.file_lock

    def spy(target, *a, **kw):
        calls.append(str(target))
        return real(target, *a, **kw)
    monkeypatch.setattr(util, "file_lock", spy)
    return calls


def _rj(realm):
    return str(realm / "realm.json")


# --------------------------------------------------------------------------- routes/caps.py

def test_refresh_connectors_locks_realm_json(realm, lock_spy, monkeypatch):
    from armada import capscan
    monkeypatch.setattr(capscan, "list_mcp", lambda: [{"name": "acme", "remote": True}])
    r = _H(realm)._refresh_connectors({"scope": "realm"})
    assert r["ok"] is True
    assert _rj(realm) in lock_spy


def test_save_capability_locks_realm_json(realm, lock_spy):
    r = _H(realm)._save_capability({"scope": "realm", "kind": "connectors", "name": "My thing"})
    assert r["ok"] is True
    assert _rj(realm) in lock_spy


def test_toggle_capability_locks_realm_json(realm, lock_spy):
    h = _H(realm)
    h._save_capability({"scope": "realm", "kind": "connectors", "name": "My thing"})
    lock_spy.clear()
    cid = json.loads((realm / "realm.json").read_text())["toolkit"]["connectors"][0]["id"]
    r = h._toggle_capability({"scope": "realm", "kind": "connectors", "id": cid, "enabled": False})
    assert r["ok"] is True
    assert _rj(realm) in lock_spy


def test_set_cap_permission_locks_realm_json(realm, lock_spy):
    h = _H(realm)
    h._save_capability({"scope": "realm", "kind": "connectors", "name": "My thing"})
    lock_spy.clear()
    cid = json.loads((realm / "realm.json").read_text())["toolkit"]["connectors"][0]["id"]
    r = h._set_cap_permission({"scope": "realm", "kind": "connectors", "id": cid, "permission": "ask"})
    assert r["ok"] is True
    assert _rj(realm) in lock_spy


def test_delete_capability_locks_realm_json(realm, lock_spy):
    h = _H(realm)
    h._save_capability({"scope": "realm", "kind": "connectors", "name": "My thing"})
    lock_spy.clear()
    cid = json.loads((realm / "realm.json").read_text())["toolkit"]["connectors"][0]["id"]
    r = h._delete_capability({"scope": "realm", "kind": "connectors", "id": cid})
    assert r["ok"] is True
    assert _rj(realm) in lock_spy


# ----------------------------------------------------------------------- routes/dashboard.py

def test_add_section_locks_realm_json(realm, lock_spy):
    r = _H(realm)._add_section({"name": "Notes", "src": "notes.md"})
    assert r["ok"] is True
    assert _rj(realm) in lock_spy


def test_add_widget_section_locks_realm_json(realm, lock_spy):
    r = _H(realm)._add_widget_section({"widget": "usage"})
    assert r["ok"] is True
    assert _rj(realm) in lock_spy


def test_update_section_locks_realm_json(realm, lock_spy):
    h = _H(realm)
    h._add_section({"name": "Notes", "src": "notes.md"})
    lock_spy.clear()
    r = h._update_section({"index": 0, "name": "Notes2", "src": "notes2.md"})
    assert r["ok"] is True
    assert _rj(realm) in lock_spy


def test_rename_section_locks_realm_json(realm, lock_spy):
    h = _H(realm)
    h._add_section({"name": "Notes", "src": "notes.md"})
    lock_spy.clear()
    r = h._rename_section({"index": 0, "name": "Renamed"})
    assert r["ok"] is True
    assert _rj(realm) in lock_spy


def test_delete_section_locks_realm_json(realm, lock_spy):
    h = _H(realm)
    h._add_section({"name": "Notes", "src": "notes.md"})
    lock_spy.clear()
    r = h._delete_section({"index": 0})
    assert r["ok"] is True
    assert _rj(realm) in lock_spy


def test_reorder_sections_locks_realm_json(realm, lock_spy):
    h = _H(realm)
    h._add_section({"name": "A", "src": "a.md"})
    h._add_section({"name": "B", "src": "b.md"})
    lock_spy.clear()
    r = h._reorder_sections({"order": [1, 0]})
    assert r["ok"] is True
    assert _rj(realm) in lock_spy


# ------------------------------------------------------------------------------- workspace.py

def test_set_root_locks_realm_json(realm, lock_spy):
    r = workspace.set_root(str(realm), str(realm.parent / "elsewhere"))
    assert r["ok"] is True
    assert _rj(realm) in lock_spy


def test_migrate_locks_realm_json_when_it_touches_sections(realm, lock_spy):
    (realm / "realm.json").write_text(json.dumps({
        "name": "R", "sections": [{"name": "Local", "assets": "C:\\old\\root\\assets"}]}),
        encoding="utf-8")
    r = workspace.migrate(str(realm), "C:\\old\\root", apply=True)
    assert r["ok"] is True
    assert _rj(realm) in lock_spy
