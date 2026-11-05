"""Native probe ordering without a desktop, CLR or live application."""
import threading
from types import SimpleNamespace

import pytest

from armada.tray import Tray
from tools.startup_recovery_probe import open_tray_and_wait


def fixture_tray(show):
    queued, posted = [], threading.Event()
    def post(callback):
        queued.append(callback)
        posted.set()
    tray = SimpleNamespace(show=show, _dispatcher=SimpleNamespace(BeginInvoke=post))
    item = SimpleNamespace(PerformClick=lambda: Tray._dispatch(tray.show))
    tray._icon = SimpleNamespace(ContextMenuStrip=SimpleNamespace(Items=[item]))
    return tray, queued, posted


def test_open_waits_for_its_callback_to_finish_before_close_can_follow():
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    failures = []
    def show():
        entered.set()
        assert release.wait(2)
    tray, queued, posted = fixture_tray(show)
    def open_then_close():
        try:
            open_tray_and_wait(tray, lambda callback: callback)
        except Exception as exc:
            failures.append(exc)
        finally:
            finished.set()
    worker = threading.Thread(target=open_then_close)
    worker.start()
    try:
        assert posted.wait(1)
        assert not finished.is_set()  # A queued Open is not a completed Open.
        queued.pop()()
        assert entered.wait(1)
        assert not finished.is_set()  # Delivery alone is insufficient until show returns.
    finally:
        release.set()
        worker.join(timeout=4)
    assert finished.is_set() and not failures
    assert tray.show is show


def test_missing_callback_is_a_failure_and_restores_the_real_callback():
    show = lambda: None
    tray, _, _ = fixture_tray(show)
    with pytest.raises(AssertionError, match='not delivered'):
        open_tray_and_wait(tray, lambda callback: callback, timeout=.02)
    assert tray.show is show


def test_callback_failure_cannot_be_mistaken_for_success():
    def show():
        raise RuntimeError('Synthetic restore failure')
    tray, _, _ = fixture_tray(show)
    tray._dispatcher.BeginInvoke = lambda callback: callback()
    with pytest.raises(AssertionError, match='callback failed') as failure:
        open_tray_and_wait(tray, lambda callback: callback)
    assert isinstance(failure.value.__cause__, RuntimeError)
    assert tray.show is show
