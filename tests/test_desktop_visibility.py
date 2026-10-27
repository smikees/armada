"""Exercise lifecycle races without needing WinForms or the owner's desktop."""
import threading
import time
from types import SimpleNamespace

from armada.desktop_visibility import DesktopVisibility
from armada.tray import Tray


def wait_for(predicate):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.005)
    raise AssertionError('worker did not finish')


def controller(save=lambda: None, **kwargs):
    queued, applied = [], []
    return DesktopVisibility(None, save, post=queued.append, apply=applied.append,
                             save_timeout=.02, **kwargs), queued, applied


def test_native_transition_is_posted_after_close_callback_returns():
    visibility, queued, applied = controller()
    visibility.hide(save=False)
    assert applied == []
    queued.pop()()
    assert applied == [False]


def test_restore_supersedes_delayed_hide():
    entered, release = threading.Event(), threading.Event()
    def save():
        entered.set()
        release.wait(2)
    visibility, queued, applied = controller(save)
    try:
        visibility.hide()
        assert entered.wait(1)
        visibility.show()
        wait_for(lambda: len(queued) == 2)
        for callback in queued:
            callback()
        assert applied == [True]
    finally:
        release.set()


def test_close_supersedes_queued_restore():
    visibility, queued, applied = controller()
    visibility.show()
    visibility.hide(save=False)
    for callback in queued:
        callback()
    assert applied == [False]


def test_delayed_minimize_notification_cannot_hide_a_restored_window(monkeypatch):
    visibility, queued, applied = controller()
    visibility.window = SimpleNamespace(native=SimpleNamespace(IsDisposed=False, WindowState='normal'))
    monkeypatch.setitem(__import__('sys').modules, 'System.Windows.Forms',
                        SimpleNamespace(FormWindowState=SimpleNamespace(Minimized='minimized')))
    visibility.hide_if_minimized()
    queued.pop()()
    assert applied == [] and queued == []
    visibility.window.native.WindowState = 'minimized'
    visibility.hide_if_minimized()
    queued.pop()()
    queued.pop()()
    assert applied == [False]


def test_unresponsive_renderer_does_not_block_hide_or_spawn_more_snapshots():
    entered, release = threading.Event(), threading.Event()
    captures = []
    def save():
        captures.append(1)
        entered.set()
        release.wait(2)
    visibility, queued, applied = controller(save)
    try:
        visibility.hide()
        assert entered.wait(1)
        for _ in range(30):
            visibility.hide()
        wait_for(lambda: bool(queued))
        queued.pop()()
        assert applied == [False]
        for _ in range(10):
            visibility.show()
            visibility.hide()
        wait_for(lambda: len(queued) == 20)
        for callback in queued:
            callback()
        assert applied == [False, False]
        assert captures == [1]
    finally:
        release.set()


def test_quit_invalidates_pending_operations():
    visibility, queued, applied = controller()
    visibility.hide(save=False)
    visibility.stop()
    visibility.show()
    for callback in queued:
        callback()
    assert applied == []


def test_failed_native_post_allows_retry():
    queued = []
    def post(callback):
        if not queued:
            queued.append(None)
            raise RuntimeError('temporary native failure')
        queued.append(callback)
    applied = []
    visibility = DesktopVisibility(None, lambda: None, post=post, apply=applied.append)
    visibility.hide(save=False)
    visibility.hide(save=False)
    queued[-1]()
    assert applied == [False]


def test_failed_native_transition_allows_retry():
    visibility, queued, applied = controller()
    def apply(visible):
        applied.append(visible)
        if len(applied) == 1:
            raise RuntimeError('temporary native failure')
    visibility._apply = apply
    visibility.hide(save=False)
    queued.pop()()
    visibility.hide(save=False)
    queued.pop()()
    assert applied == [False, False]


def test_tray_callback_does_not_wait_for_main_ui():
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    def callback():
        entered.set()
        release.wait(2)
        finished.set()
    try:
        Tray._dispatch(callback)
        assert entered.wait(1)
        assert not finished.is_set()
    finally:
        release.set()
    assert finished.wait(1)
