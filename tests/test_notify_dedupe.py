"""Identical notifications collapse on the channels that interrupt you.

The desktop channel had this from the start; Telegram never did, though it is the one that follows
you out of the building. A job retrying in a loop could carpet a phone while being quiet on the
machine standing next to it.
"""
import pytest

from armada import notify


@pytest.fixture(autouse=True)
def _clean():
    notify._recent.clear()
    yield
    notify._recent.clear()


def _armed(monkeypatch):
    """Let the Telegram path run, capturing what it would send."""
    sent = []
    from armada import telegram
    monkeypatch.setattr(telegram, "ready", lambda: True)
    monkeypatch.setattr(telegram, "send", lambda text, **k: sent.append(text) or 1)
    return sent


def test_telegram_collapses_an_identical_notification(monkeypatch):
    sent = _armed(monkeypatch)
    a = notify._send_telegram(None, "job_failed", "Warren: job failed", "weekly scan", "")
    b = notify._send_telegram(None, "job_failed", "Warren: job failed", "weekly scan", "")
    assert a is True and b is False, "the second identical push should be suppressed"
    assert len(sent) == 1


def test_a_different_message_still_gets_through(monkeypatch):
    sent = _armed(monkeypatch)
    notify._send_telegram(None, "job_failed", "Warren: job failed", "weekly scan", "")
    notify._send_telegram(None, "job_failed", "Warren: job failed", "monthly wrapup", "")
    assert len(sent) == 2, "collapsing must key on the message, not just the event"


def test_a_different_agent_still_gets_through(monkeypatch):
    sent = _armed(monkeypatch)
    notify._send_telegram(None, "job_failed", "Warren: job failed", "scan", "")
    notify._send_telegram(None, "job_failed", "Galen: job failed", "scan", "")
    assert len(sent) == 2


def test_the_window_expires(monkeypatch):
    sent = _armed(monkeypatch)
    notify._send_telegram(None, "job_failed", "t", "b", "")
    # walk the clock past the window rather than sleeping through it
    base = notify.time.monotonic()
    monkeypatch.setattr(notify.time, "monotonic", lambda: base + notify._DEDUPE_SEC + 1)
    assert notify._send_telegram(None, "job_failed", "t", "b", "") is True
    assert len(sent) == 2


def test_channels_do_not_suppress_each_other(monkeypatch):
    """Scoped keys: a desktop toast must not consume the key and silence the phone."""
    sent = _armed(monkeypatch)
    monkeypatch.setattr(notify.os, "name", "nt")
    monkeypatch.setattr(notify, "_send", lambda *a, **k: None)
    notify.toast("Warren: job failed", "weekly scan", realm_root=None, event="job_failed")
    assert notify._send_telegram(None, "job_failed", "Warren: job failed", "weekly scan", "") is True
    assert len(sent) == 1


def test_the_in_app_record_is_never_collapsed(tmp_path):
    """The feed is the archive. Two real events an hour apart must both be in it, and even a
    genuine repeat is history rather than an interruption."""
    (tmp_path / "realm.json").write_text('{"name":"t"}', encoding="utf-8")
    notify.record(tmp_path, "job_failed", "Warren: job failed", "weekly scan")
    notify.record(tmp_path, "job_failed", "Warren: job failed", "weekly scan")
    assert len(notify.feed(tmp_path)) == 2


def test_an_unconfigured_telegram_is_not_an_error(monkeypatch):
    from armada import telegram
    monkeypatch.setattr(telegram, "ready", lambda: False)
    assert notify._send_telegram(None, "job_failed", "t", "b", "") is False
