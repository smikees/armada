"""The scheduler fires every realm, not just the one you're viewing.

Which realm is active decides what the app SHOWS. It must not decide whose jobs run — a realm's
schedule is its own commitment, and a job that silently stops firing because you opened a different
realm is indistinguishable from a broken scheduler.
"""
import json

import pytest

from armada import activerealm


def _realm(tmp_path, name):
    r = tmp_path / name
    r.mkdir(parents=True, exist_ok=True)
    (r / "realm.json").write_text(json.dumps({"name": name}), encoding="utf-8")
    return r


def test_every_lists_all_known_realms(tmp_path, monkeypatch):
    a, b, c = (_realm(tmp_path, n) for n in ("a", "b", "c"))
    monkeypatch.setattr(activerealm, "_registered", lambda: [str(a), str(b), str(c)])
    monkeypatch.setattr(activerealm, "remembered", lambda: "")
    assert activerealm.every() == [str(a), str(b), str(c)]


def test_the_active_realm_goes_first(tmp_path, monkeypatch):
    a, b, c = (_realm(tmp_path, n) for n in ("a", "b", "c"))
    monkeypatch.setattr(activerealm, "_registered", lambda: [str(a), str(b), str(c)])
    monkeypatch.setattr(activerealm, "remembered", lambda: str(c))
    # Order matters for exactly one thing: the Telegram listener attaches to the head of the list,
    # and a reply typed on a phone should land in the realm you are actually working in.
    assert activerealm.every() == [str(c), str(a), str(b)]


def test_the_active_realm_is_not_listed_twice(tmp_path, monkeypatch):
    a, b = _realm(tmp_path, "a"), _realm(tmp_path, "b")
    monkeypatch.setattr(activerealm, "_registered", lambda: [str(a), str(b)])
    monkeypatch.setattr(activerealm, "remembered", lambda: str(a))
    assert activerealm.every() == [str(a), str(b)]


def test_one_bad_realm_does_not_stop_the_others(tmp_path, monkeypatch):
    """A folder moved or deleted since startup must not take the other realms' jobs down."""
    from armada import scheduler
    a, b = _realm(tmp_path, "a"), _realm(tmp_path, "b")
    calls = []

    def _tick(root, **kw):
        calls.append(str(root))
        if str(root) == str(a):
            raise OSError("realm folder vanished")
        return [{"agent": "x", "job": "y", "kind": "agent", "status": "ok"}]

    monkeypatch.setattr(scheduler, "tick", _tick)
    # Drive one pass of the daemon loop, then stop it.
    monkeypatch.setattr(scheduler.time, "sleep", lambda *_: (_ for _ in ()).throw(KeyboardInterrupt))
    assert scheduler.run_daemon(a, also=[b], interval=5) == 0
    assert calls == [str(a), str(b)], "the failing realm must not skip the one after it"


def test_a_realm_named_on_the_command_line_is_the_only_one_ticked(tmp_path, monkeypatch):
    """Naming a folder still means that folder — the default is the broad one, not the override."""
    from armada import cli
    a, b = _realm(tmp_path, "a"), _realm(tmp_path, "b")
    monkeypatch.setattr(activerealm, "_registered", lambda: [str(a), str(b)])
    monkeypatch.setattr(activerealm, "remembered", lambda: str(a))
    seen = []
    from armada import scheduler
    monkeypatch.setattr(scheduler, "tick", lambda root, **kw: seen.append(str(root)) or [])
    cli.main(["schedule", str(b), "--dry-run"])
    assert seen == [str(b)]


def test_with_no_realm_named_every_realm_is_ticked(tmp_path, monkeypatch):
    from armada import cli, scheduler
    a, b = _realm(tmp_path, "a"), _realm(tmp_path, "b")
    monkeypatch.setattr(activerealm, "_registered", lambda: [str(a), str(b)])
    monkeypatch.setattr(activerealm, "remembered", lambda: str(b))
    seen = []
    monkeypatch.setattr(scheduler, "tick", lambda root, **kw: seen.append(str(root)) or [])
    cli.main(["schedule", "--dry-run"])
    assert seen == [str(b), str(a)]
