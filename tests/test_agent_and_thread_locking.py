"""agent.json, thread meta.json and dashboard.json read-modify-writes hold the file lock (4.3 L4/L5).

2.9 audited realm.json. The architecture doc (2.10) found three more shared files written without a
lock: agent.json from the Configure tab (while capabilities.py writes grants into the same file
under a lock — a save racing a grant could drop the grant), thread meta.json (rewritten by the
thread routes, by a run posting a reply, and during a render), and dashboard.json (a one-time
migration written by a render, racing a save of the layout).
"""
import json

import pytest

from armada import serve, util
from armada.webui import threadsview, _core


class _H(serve.Handler):
    def __init__(self, realm):
        self.realm = str(realm)


@pytest.fixture
def realm(tmp_path):
    r = tmp_path / "realm"
    (r / "agents" / "warren" / "threads" / "main").mkdir(parents=True)
    (r / "realm.json").write_text(json.dumps({"name": "R"}), encoding="utf-8")
    (r / "agents" / "warren" / "agent.json").write_text(
        json.dumps({"id": "warren", "display": "Warren", "toolkit": {"connectors": ["ibkr"]}}), encoding="utf-8")
    return r


@pytest.fixture
def lock_spy(monkeypatch):
    calls = []
    real = util.file_lock

    def spy(target, *a, **kw):
        calls.append(str(target))
        return real(target, *a, **kw)

    monkeypatch.setattr(util, "file_lock", spy)
    return calls


def _meta(realm):
    return realm / "agents" / "warren" / "threads" / "meta.json"


def test_saving_an_agent_locks_agent_json_and_keeps_fields_it_did_not_touch(realm, lock_spy):
    r = _H(realm)._save_agent({"agent": "warren", "display": "Warren B."})
    assert r["ok"] is True
    aj = realm / "agents" / "warren" / "agent.json"
    assert str(aj) in lock_spy
    saved = json.loads(aj.read_text(encoding="utf-8"))
    assert saved["display"] == "Warren B." and saved["toolkit"] == {"connectors": ["ibkr"]}


@pytest.mark.parametrize("body", [
    {"action": "rename", "thread": "t1", "title": "Taxes"},
    {"action": "pin", "thread": "t1"},
    {"action": "reorder", "order": ["t2", "t1"]},
])
def test_thread_actions_lock_meta_json(realm, lock_spy, body):
    r = _H(realm)._thread_action({"agent": "warren", **body})
    assert r["ok"] is True
    assert str(_meta(realm)) in lock_spy


def test_a_new_thread_locks_meta_json(realm, lock_spy):
    r = _H(realm)._new_thread({"agent": "warren"})
    assert r["ok"] is True
    assert str(_meta(realm)) in lock_spy
    assert json.loads(_meta(realm).read_text(encoding="utf-8"))["order"][0] == r["thread"]


def test_render_path_meta_writes_lock_only_when_they_change_something(realm, lock_spy):
    adir = realm / "agents" / "warren"
    threadsview._touch_last_thread(adir, "t1")
    assert lock_spy == [str(_meta(realm))]
    lock_spy.clear()
    threadsview._touch_last_thread(adir, "t1")          # nothing to change → no lock, no write
    assert lock_spy == []
    threadsview._mark_thread_unread(adir, "t1")
    threadsview._clear_thread_unread(adir, "t1")
    assert lock_spy == [str(_meta(realm))] * 2
    m = json.loads(_meta(realm).read_text(encoding="utf-8"))
    assert m["last"] == "t1" and m["unread"]["t1"] is False


def test_the_dashboard_migration_never_overwrites_a_newer_saved_layout(realm, lock_spy):
    dj = realm / "dashboard.json"
    dj.write_text(json.dumps({"spans": {"register": 2}}), encoding="utf-8")   # legacy 4-col scale
    real_read = _core.Path.read_text
    raced = {"done": False}

    def racing_read(self, *a, **kw):
        # First read (the load) sees the legacy file; then a Save lands before the migration writes.
        out = real_read(self, *a, **kw)
        if self == dj and not raced["done"]:
            raced["done"] = True
            dj.write_text(json.dumps({"spans": {"register": 12}, "span_scale": 20}), encoding="utf-8")
        return out

    import pathlib
    orig = pathlib.Path.read_text
    pathlib.Path.read_text = racing_read
    try:
        d = _core._load_dashboard(realm)
    finally:
        pathlib.Path.read_text = orig
    assert d["spans"]["register"] == 10                  # this render's migrated view
    assert str(dj) in lock_spy
    saved = json.loads(dj.read_text(encoding="utf-8"))
    assert saved == {"spans": {"register": 12}, "span_scale": 20}   # the save survived


def test_saving_the_dashboard_locks_it(realm, lock_spy):
    _H(realm)._save_dashboard({"order": ["register"]})
    assert str(realm / "dashboard.json") in lock_spy
