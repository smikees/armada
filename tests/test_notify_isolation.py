"""Running the tests must not message the owner.

Telegram credentials live in ~/.armada, outside every realm — that's what stops a realm export
carrying a bot token to another machine, and it's also why a test realm in a temp folder could
reach the real phone. notify.emit() defaults `job_failed` and `approval_needed` to telegram=on, so
a single emit() in a unit test sent a real message. It did, repeatedly, for a whole afternoon.
"""
import os

import pytest

from armada import notify, telegram


def test_the_mute_switch_closes_the_off_machine_channel(monkeypatch):
    monkeypatch.setenv(notify.MUTE_ENV, "1")
    assert notify.muted() is True
    assert notify.channel_enabled("telegram") is False


def test_muting_does_not_silence_what_stays_on_this_machine(monkeypatch):
    """Mute stops things reaching your phone. The record and the toast reach whoever is already at
    the computer, which is not the same thing — erasing those would just be a broken app."""
    monkeypatch.setenv(notify.MUTE_ENV, "1")
    assert notify.channel_enabled("inapp") is True
    assert notify.channel_enabled("desktop") is True


@pytest.mark.parametrize("val", ["", "0", "false", "no"])
def test_falsey_values_do_not_mute(monkeypatch, val):
    monkeypatch.setenv(notify.MUTE_ENV, val)
    assert notify.muted() is False


def test_mute_is_off_by_default(monkeypatch):
    monkeypatch.delenv(notify.MUTE_ENV, raising=False)
    assert notify.muted() is False


def test_the_suite_runs_muted():
    """The autouse fixture in conftest sets this for every test. If this fails, the suite has
    stopped protecting the owner's phone."""
    assert os.environ.get(notify.MUTE_ENV), "conftest is no longer muting outbound notifications"
    assert notify.muted() is True


def test_the_real_credential_store_is_not_visible_to_tests():
    """Even unmuted, a test must not be able to read the owner's token."""
    assert not telegram._store_path().exists()
    assert telegram.ready() is False


def test_an_emit_that_would_have_paged_the_owner_stays_local(tmp_path):
    """The exact shape of the bug: the event whose default is telegram=on, emitted against a
    throwaway realm. It must record and not send."""
    (tmp_path / "realm.json").write_text('{"name":"t"}', encoding="utf-8")
    notify._recent.clear()
    r = notify.emit(tmp_path, "job_failed", "Warren: job failed", "weekly scan")
    assert r["recorded"] is True
    assert r["sent"] is False, "a test just sent a real Telegram message"
    notify._recent.clear()
    r = notify.emit(tmp_path, "approval_needed", "Needs your approval", "x")
    assert r["sent"] is False


def test_reaching_the_network_fails_the_test_rather_than_sending():
    """conftest replaces the transport with a failure. Prove it's armed, so the protection can't
    quietly rot into a no-op."""
    with pytest.raises(BaseException):
        telegram.api("token", "sendMessage", {"text": "hi"})
