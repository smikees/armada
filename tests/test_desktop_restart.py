"""Restart must drain the desktop before releasing listeners or replacing a process."""
import threading
from types import SimpleNamespace
from unittest.mock import Mock

from armada import app, desktop_launch, serve, updater


def test_restart_keeps_server_until_the_desktop_finishes(monkeypatch):
    callbacks = []
    sock = Mock()
    replace = Mock()
    monkeypatch.setattr(serve, 'RESTARTING', threading.Event())
    monkeypatch.setattr(serve, '_content_httpd', None)
    monkeypatch.setattr(serve, '_launch_mode', lambda: 'app')
    monkeypatch.setattr(serve.time, 'sleep', lambda _: None)
    monkeypatch.setattr(updater, 'installed', lambda: False)
    monkeypatch.setattr(app, '_main_window', object())
    monkeypatch.setattr(app, 'restart_desktop', callbacks.append)
    monkeypatch.setattr(desktop_launch, 'replace_process', replace)
    handler = SimpleNamespace(realm='', server=SimpleNamespace(socket=sock, server_address=('127.0.0.1', 8870)))
    serve.Handler._restart(handler)
    sock.close.assert_not_called()
    replace.assert_not_called()
    assert serve.RESTARTING.is_set() and len(callbacks) == 1
    callbacks[0]()
    sock.close.assert_called_once()
    replace.assert_called_once()


def test_monitored_restart_returns_normally_without_hard_exit(monkeypatch):
    monkeypatch.setattr(serve, 'RESTARTING', threading.Event())
    monkeypatch.setattr(serve, '_content_httpd', None)
    hard_exit, replace = Mock(), Mock()
    monkeypatch.setattr(serve.os, '_exit', hard_exit)
    monkeypatch.setattr(desktop_launch, 'replace_process', replace)
    handler = SimpleNamespace(realm='', server=SimpleNamespace(socket=Mock(), server_address=('127.0.0.1', 8870)))
    serve.Handler._finish_restart(handler, {'nonce': 'synthetic-monitor'})
    hard_exit.assert_not_called()
    replace.assert_not_called()
    handler.server.socket.close.assert_called_once()


def test_restart_records_continuation_before_requesting_native_close(monkeypatch):
    window, after = object(), Mock()
    monkeypatch.setattr(app, '_main_window', window)
    monkeypatch.setattr(app, '_restart_after_close', None)
    observed = []
    monkeypatch.setattr(app, '_quit_windows', lambda target: observed.append((target, app._restart_after_close)))
    assert app.restart_desktop(after)
    assert observed == [(window, after)]
    after.assert_not_called()


def test_stalled_browser_cannot_hold_restart_snapshot(monkeypatch, caplog):
    release = threading.Event()
    monkeypatch.setattr(app, 'save_window_state', lambda: release.wait(5))
    try:
        app.save_before_close(timeout=.01)
        assert 'continuing to quit' in caplog.text
    finally:
        release.set()
