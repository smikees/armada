"""Notifications from a realm you are not looking at.

Jobs fire in every realm regardless of which one is on screen, so by default their notifications
follow you out of it — a 3am failure in the realm you are not watching is exactly the one you need
to hear about. "Notify cross-realms" off narrows a realm to speaking only while you are in it, and
only on the channels that leave the realm: the bell is inside the realm and keeps everything.
"""
import json

import pytest

from armada import activerealm, notify


def _realm(tmp_path, name, cross=None):
    r = tmp_path / name.lower().replace(" ", "-")
    r.mkdir(parents=True, exist_ok=True)
    cfg = {"name": name}
    if cross is not None:
        cfg["notifications"] = {"cross_realm": cross}
    (r / "realm.json").write_text(json.dumps(cfg), encoding="utf-8")
    return r


@pytest.fixture
def _viewing(monkeypatch):
    """Point the app at a given realm (or nowhere)."""
    def _set(path):
        monkeypatch.setattr(activerealm, "remembered", lambda: str(path) if path else "")
    return _set


def test_on_by_default(tmp_path):
    assert notify.cross_realm(_realm(tmp_path, "A")) is True


def test_an_unreadable_realm_still_notifies(tmp_path):
    missing = tmp_path / "gone"
    assert notify.cross_realm(missing) is True, "a realm we can't read must not go silent"


@pytest.mark.parametrize("channel", ["desktop", "telegram"])
def test_off_silences_the_realm_you_are_not_viewing(tmp_path, _viewing, monkeypatch, channel):
    a, b = _realm(tmp_path, "A", cross=False), _realm(tmp_path, "B")
    monkeypatch.setattr(notify, "channel_enabled", lambda c: True)
    monkeypatch.setattr(notify, "matrix", lambda r: {"job_failed": {channel: True}})
    _viewing(b)
    assert notify.wants(a, "job_failed", channel) is False
    _viewing(a)
    assert notify.wants(a, "job_failed", channel) is True, "in the realm, it speaks normally"


def test_off_does_not_silence_the_bell(tmp_path, _viewing, monkeypatch):
    a, b = _realm(tmp_path, "A", cross=False), _realm(tmp_path, "B")
    monkeypatch.setattr(notify, "channel_enabled", lambda c: True)
    monkeypatch.setattr(notify, "matrix", lambda r: {"job_failed": {"inapp": True}})
    _viewing(b)
    # The in-app feed lives inside the realm and is only ever read by someone already there.
    # Gating it would hide history from the person who came looking for it.
    assert notify.wants(a, "job_failed", "inapp") is True


def test_on_reaches_you_from_anywhere(tmp_path, _viewing, monkeypatch):
    a, b = _realm(tmp_path, "A", cross=True), _realm(tmp_path, "B")
    monkeypatch.setattr(notify, "channel_enabled", lambda c: True)
    monkeypatch.setattr(notify, "matrix", lambda r: {"job_failed": {"desktop": True}})
    _viewing(b)
    assert notify.wants(a, "job_failed", "desktop") is True


def test_no_active_realm_recorded_means_everything_speaks(tmp_path, _viewing, monkeypatch):
    a = _realm(tmp_path, "A", cross=False)
    monkeypatch.setattr(notify, "channel_enabled", lambda c: True)
    monkeypatch.setattr(notify, "matrix", lambda r: {"job_failed": {"desktop": True}})
    _viewing(None)
    # An unset preference must not silence the machine.
    assert notify.wants(a, "job_failed", "desktop") is True


# --- which realm was that? --------------------------------------------------------------------

def test_the_realm_name_is_on_off_realm_notifications(tmp_path):
    a = _realm(tmp_path, "The Cabinet")
    assert notify._titled(a, "Warren: job failed") == "The Cabinet · Warren: job failed"


def test_the_prefix_is_not_applied_twice(tmp_path):
    a = _realm(tmp_path, "The Cabinet")
    once = notify._titled(a, "Warren: job failed")
    assert notify._titled(a, once) == once


def test_a_realm_with_no_name_falls_back_to_its_folder(tmp_path):
    r = tmp_path / "scratch-realm"
    r.mkdir()
    (r / "realm.json").write_text("{}", encoding="utf-8")
    assert notify.realm_label(r) == "scratch-realm"
