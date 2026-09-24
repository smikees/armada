"""The app root: the one folder on this machine ARMADA works in, and the rule that every realm
lives inside it.

Containment you can opt out of per realm isn't containment, so the root is a property of the
install and a realm only chooses where inside it to sit.
"""
import json

import pytest

from armada import appconfig, approot, preflight


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path, monkeypatch):
    """Never read or write the developer's real ~/.armada/config.json from a test."""
    cfgdir = tmp_path / "home" / ".armada"
    cfgdir.mkdir(parents=True)
    monkeypatch.setattr(appconfig, "_path", lambda: cfgdir / "config.json")
    yield


def _root(tmp_path, name="Work2"):
    r = tmp_path / name
    r.mkdir(parents=True, exist_ok=True)
    return r


# --------------------------------------------------------------------------- setting it

def test_unset_by_default():
    assert approot.configured() is False
    assert approot.root() == ""
    assert approot.exists() is False


def test_set_and_read_back(tmp_path):
    r = _root(tmp_path)
    assert approot.set_root(str(r))["ok"] is True
    assert approot.configured() and approot.exists()
    assert approot.root() == str(r.resolve())


def test_a_path_that_is_not_a_folder_is_refused(tmp_path):
    f = tmp_path / "a-file.txt"
    f.write_text("x", encoding="utf-8")
    assert approot.set_root(str(f))["ok"] is False
    assert approot.set_root(str(tmp_path / "nope"))["ok"] is False
    assert approot.configured() is False, "a refused root must not be stored"


def test_a_trailing_separator_is_normalised(tmp_path):
    r = _root(tmp_path)
    approot.set_root(str(r) + "\\")
    assert not approot.root().endswith(("\\", "/"))


def test_it_can_be_cleared(tmp_path):
    approot.set_root(str(_root(tmp_path)))
    assert approot.set_root("")["ok"] is True
    assert approot.configured() is False


# --------------------------------------------------------------------------- containment test

def test_contains_the_root_and_its_children(tmp_path):
    r = _root(tmp_path)
    (r / "Cabinet-realm" / "agents").mkdir(parents=True)
    approot.set_root(str(r))
    assert approot.contains(r) is True
    assert approot.contains(r / "Cabinet-realm") is True
    assert approot.contains(r / "Cabinet-realm" / "agents") is True


def test_does_not_contain_a_sibling_or_the_parent(tmp_path):
    r = _root(tmp_path)
    sib = tmp_path / "Work"
    sib.mkdir()
    approot.set_root(str(r))
    assert approot.contains(sib) is False
    assert approot.contains(tmp_path) is False


def test_a_sibling_whose_name_starts_with_the_root_is_not_inside_it(tmp_path):
    """D:\\Work2 must not count D:\\Work2-backup as a child. A string prefix test would."""
    r = _root(tmp_path, "Work2")
    trap = tmp_path / "Work2-backup"
    trap.mkdir()
    approot.set_root(str(r))
    assert approot.contains(trap) is False


def test_dot_dot_cannot_walk_out(tmp_path):
    r = _root(tmp_path)
    approot.set_root(str(r))
    assert approot.contains(r / ".." / "Work") is False
    assert approot.contains(str(r) + "\\..\\..") is False


def test_nothing_is_inside_an_unset_root(tmp_path):
    assert approot.contains(tmp_path) is False


# --------------------------------------------------------------------------- the gate

def test_check_accepts_a_realm_inside_the_root(tmp_path):
    r = _root(tmp_path)
    realm = r / "Cabinet-realm"
    realm.mkdir()
    approot.set_root(str(r))
    assert approot.check(realm)["ok"] is True


def test_check_rejects_a_realm_outside_and_says_where_it_should_go(tmp_path):
    r = _root(tmp_path)
    approot.set_root(str(r))
    outside = tmp_path / "Work" / "Some-realm"
    outside.mkdir(parents=True)
    res = approot.check(outside)
    assert res["ok"] is False and res["code"] == "outside-root"
    assert str(r) in res["error"]
    assert approot.suggest_for(outside) == str(r / "Some-realm")


def test_check_explains_an_unset_root(tmp_path):
    res = approot.check(tmp_path)
    assert res["ok"] is False and res["code"] == "no-root"


def test_check_notices_a_root_that_has_gone(tmp_path):
    r = _root(tmp_path)
    approot.set_root(str(r))
    r.rmdir()
    assert approot.check(r)["code"] == "root-missing"


# --------------------------------------------------------------------------- preflight

def test_preflight_blocks_a_realm_outside_the_root(tmp_path, monkeypatch):
    r = _root(tmp_path)
    approot.set_root(str(r))
    outside = tmp_path / "elsewhere"
    (outside / "agents").mkdir(parents=True)
    (outside / "realm.json").write_text(json.dumps({"name": "X"}), encoding="utf-8")
    monkeypatch.setattr(preflight, "engine_check",
                        lambda e="claude": preflight._check("engine", "Engine", True, "ok"))
    res = preflight.run(outside)
    assert res["ok"] is False
    assert any(c["id"] == "approot" and not c["ok"] for c in res["checks"])


def test_preflight_passes_for_a_realm_inside_the_root(tmp_path, monkeypatch):
    r = _root(tmp_path)
    realm = r / "Cabinet-realm"
    (realm / "agents").mkdir(parents=True)
    (realm / "realm.json").write_text(json.dumps({"name": "X", "workspace": str(r)}), encoding="utf-8")
    approot.set_root(str(r))
    monkeypatch.setattr(preflight, "engine_check",
                        lambda e="claude": preflight._check("engine", "Engine", True, "ok"))
    assert preflight.approot_check(realm)["ok"] is True


# --------------------------------------------------------------------------- wiring

def test_adding_a_realm_goes_through_the_gate():
    """The rule is only real if the create/adopt path consults it."""
    import inspect
    from armada import serve
    src = inspect.getsource(serve.Handler._new_realm) if hasattr(serve, "Handler") else ""
    if not src:
        # handler class name differs — search the module instead
        src = inspect.getsource(serve)
        assert "approot.check" in src
    else:
        assert "approot.check" in src
