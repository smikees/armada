"""The app reopens the realm you were last in.

Switching realms used to live only in the running process, so Update & Restart kept the change but
closing the app and relaunching it from a shortcut did not — the launcher's hard-coded path won.
These tests pin the resolution order and the one thing that makes it work: a path named on the
command line still wins, and becomes what is remembered.
"""
import json

import pytest

from armada import activerealm

_REAL_REGISTERED = activerealm._registered   # kept before the autouse fixture below stubs it


def _realm(tmp_path, name="realm-a"):
    r = tmp_path / name
    (r / "agents").mkdir(parents=True)
    (r / "realm.json").write_text(json.dumps({"name": name}), encoding="utf-8")
    return r


def _legacy_realm(tmp_path, name="old-realm"):
    """The pre-realm.json layout, which ARMADA still opens."""
    r = tmp_path / name
    (r / "cabinet").mkdir(parents=True)
    (r / "cabinet" / "schedule.json").write_text("{}", encoding="utf-8")
    return r


@pytest.fixture(autouse=True)
def _empty_registry(monkeypatch, tmp_path):
    """No realms.json unless a test writes one — otherwise resolution falls through to whatever the
    developer's machine happens to have registered."""
    monkeypatch.setattr(activerealm, "_registered", lambda: [])


def test_nothing_remembered_yet(tmp_path):
    assert activerealm.remembered() == ""
    assert activerealm.resolve() == ""
    assert "armada app" in activerealm.no_realm_message()


def test_remembers_and_reopens(tmp_path):
    r = _realm(tmp_path)
    activerealm.remember(r)
    assert activerealm.remembered() == str(r.resolve())
    assert activerealm.resolve() == str(r.resolve())


def test_an_explicit_path_wins(tmp_path):
    a, b = _realm(tmp_path, "a"), _realm(tmp_path, "b")
    activerealm.remember(a)
    assert activerealm.resolve(str(b)) == str(b), "naming a folder must beat the remembered one"


def test_a_folder_that_is_not_a_realm_is_not_remembered(tmp_path):
    plain = tmp_path / "just-a-folder"
    plain.mkdir()
    activerealm.remember(plain)
    assert activerealm.remembered() == ""


def test_the_legacy_layout_counts_as_a_realm(tmp_path):
    r = _legacy_realm(tmp_path)
    activerealm.remember(r)
    assert activerealm.remembered() == str(r.resolve())


def test_a_remembered_realm_that_moved_is_forgotten_not_fatal(tmp_path):
    r = _realm(tmp_path)
    activerealm.remember(r)
    (r / "realm.json").unlink()
    # It must read as "nothing remembered" rather than raising or handing back a dead path: a
    # preference that no longer resolves is not a reason for the app to refuse to start.
    assert activerealm.remembered() == ""
    assert activerealm.resolve() == ""


def test_falls_back_to_a_single_registered_realm(tmp_path, monkeypatch):
    r = _realm(tmp_path)
    monkeypatch.setattr(activerealm, "_registered", lambda: [str(r)])
    assert activerealm.resolve() == str(r)


def test_several_registered_and_none_remembered_is_ambiguous(tmp_path, monkeypatch):
    a, b = _realm(tmp_path, "a"), _realm(tmp_path, "b")
    monkeypatch.setattr(activerealm, "_registered", lambda: [str(a), str(b)])
    # Picking one would put the app somewhere arbitrary. Say which are available instead.
    assert activerealm.resolve() == ""
    msg = activerealm.no_realm_message()
    assert str(a) in msg and str(b) in msg


def test_registry_reading_survives_a_corrupt_file(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".armada").mkdir(parents=True)
    (home / ".armada" / "realms.json").write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(activerealm.Path, "home", staticmethod(lambda: home))
    # _REAL_REGISTERED, not the module attribute — the autouse fixture above stubs that one.
    assert _REAL_REGISTERED() == [], "a corrupt registry must not stop the app starting"
