"""Detached size preferences survive close/restart and fit smaller/DPI-scaled displays."""
import json
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from armada import app, util
from armada.monitor_recovery import fit_size
from armada.request_context import RealmContext
from golden_support import build_fixture


@pytest.mark.parametrize('size,area,expected', [
    ((700, 900), (0, 0, 1920, 1040), (700, 900)),
    ((1280, 720), (0, 0, 1280, 720), (1280, 720)),
    ((1600, 1000), (0, 0, 1280, 720), (921, 576)),
    ((2200, 800), (-1920, 40, 1920, 1040), (1536, 558)),
    ((700, 1400), (0, 0, 1280, 720), (288, 576)),
    ((800, 1000), (0, 0, 320, 240), (153, 192)),
])
def test_saved_size_fits_proportionally(size, area, expected):
    result = fit_size(size, area)
    assert result == expected
    assert result[0] <= area[2] and result[1] <= area[3]
    assert abs(result[0] - result[1] * size[0] / size[1]) < 3


def native_forms(monkeypatch, area=(0, 0, 1920, 1040)):
    forms = SimpleNamespace(
        FormWindowState=SimpleNamespace(Normal='normal'),
        Screen=SimpleNamespace(FromControl=lambda _: SimpleNamespace(
            WorkingArea=SimpleNamespace(X=area[0], Y=area[1], Width=area[2], Height=area[3]))))
    monkeypatch.setitem(sys.modules, 'System.Windows.Forms', forms)


def test_close_reopen_and_app_restart_retain_each_threads_own_size(tmp_path, monkeypatch):
    monkeypatch.setattr(util, 'data_dir', lambda: tmp_path/'account')
    native_forms(monkeypatch)
    monkeypatch.setattr(app.sys, 'platform', 'win32')
    monkeypatch.setattr(app, '_main_window', SimpleNamespace(
        native=SimpleNamespace(_scale=1), x=80, y=40, width=900, height=800))
    monkeypatch.setattr(app, '_app_url', 'http://127.0.0.1:8756/')
    monkeypatch.setattr(app, '_thread_windows', {})
    monkeypatch.setattr(app, '_quitting', False)
    monkeypatch.setattr(app.threading, 'Thread', Mock())
    monkeypatch.setattr('armada.local_auth.browser_url', lambda base, route: base.rstrip('/')+route)
    class Event:
        def __init__(self):
            self.callbacks = []

        def __iadd__(self, callback):
            self.callbacks.append(callback)
            return self

        def emit(self):
            for callback in self.callbacks:
                callback()

    created = []

    def create(*args, **kwargs):
        events = SimpleNamespace(**{name: Event() for name in ('loaded', 'resized', 'closing', 'closed')})
        window = SimpleNamespace(events=events, show=Mock(), restore=Mock(), min_size=kwargs['min_size'])
        window.native = SimpleNamespace(
            _scale=1.5, WindowState='normal',
            Bounds=SimpleNamespace(Width=kwargs['width']*1.5, Height=kwargs['height']*1.5))

        def close():
            events.closing.emit()
            window.native = None  # Size must have been captured before disposal.
            events.closed.emit()

        def resize(width, height):
            window.native.Bounds = SimpleNamespace(Width=width*1.5, Height=height*1.5)

        window.resize = resize
        window.destroy = close
        created.append((window, kwargs))
        return window

    monkeypatch.setitem(sys.modules, 'webview', SimpleNamespace(create_window=create))
    realm = build_fixture(tmp_path/'first')
    other = build_fixture(tmp_path/'second')
    key = (RealmContext.capture(realm).realm_id, 'captain', 'main')
    other_key = (RealmContext.capture(other).realm_id, 'captain', 'main')
    assert app.open_thread(realm, 'captain', 'main')
    window = created[-1][0]
    window.native.Bounds = SimpleNamespace(Width=1140, Height=960)
    window.destroy()
    assert app._thread_window_size(key) == (760, 640)
    assert util.read_json_state(tmp_path/'account/desktop-threads.json')['threads'] == []

    assert app.open_thread(other, 'captain', 'main')
    assert (created[-1][1]['width'], created[-1][1]['height']) == (520, 720)
    other_window = created[-1][0]
    other_window.native.Bounds = SimpleNamespace(Width=900, Height=1200)
    assert app.open_thread(realm, 'captain', 'main')
    assert (created[-1][1]['width'], created[-1][1]['height']) == (760, 640)

    monkeypatch.setattr(app, '_quitting', True)
    for window in list(app._thread_windows.values()):
        window.destroy()
    assert not app._thread_windows
    assert app._thread_window_size(other_key) == (600, 800)
    monkeypatch.setattr(app, '_quitting', False)
    app._restore_thread_windows()
    assert [(options['width'], options['height']) for _, options in created[-2:]] == [(600, 800), (760, 640)]


@pytest.mark.parametrize('state', ['normal', 'minimized', 'maximized'])
def test_normal_size_saved_in_logical_pixels_without_registry_lock(tmp_path, monkeypatch, state):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    monkeypatch.setattr(util, 'data_dir', lambda: tmp_path)
    native_forms(monkeypatch)
    monkeypatch.setattr(app.sys, 'platform', 'win32')
    key = ('realm', 'agent', 'thread')
    normal = SimpleNamespace(Width=1200, Height=1500)
    window = SimpleNamespace(native=SimpleNamespace(
        _scale=1.5, WindowState=state, RestoreBounds=normal,
        Bounds=normal if state == 'normal' else SimpleNamespace(Width=160, Height=30)))
    monkeypatch.setattr(app, '_thread_windows', {key: window})
    monkeypatch.setattr(app, '_window_lock', threading.RLock())
    with app._window_lock, ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(app._remember_thread_size, key, window).result(timeout=2)
    assert app._thread_window_size(key) == (800, 1000)


def test_scaled_secondary_display_and_cascade_are_clamped(tmp_path, monkeypatch):
    native_forms(monkeypatch, (-1920, 60, 1920, 1020))
    monkeypatch.setattr(app, '_main_window', SimpleNamespace(
        native=SimpleNamespace(_scale=1.5), x=-1200, y=100, width=1000, height=600))
    position = app._alexander_position(thread_size=(1600, 1000), offset=2000)
    assert (position['width'], position['height']) == (870, 544)
    assert -1280 <= position['x'] and position['x']+position['width'] <= 0
    assert 40 <= position['y'] and position['y']+position['height'] <= 720


@pytest.mark.parametrize('value', ['{broken', '[]', '{"invalid": true}'])
def test_unreadable_or_missing_preference_uses_default(tmp_path, monkeypatch, value):
    monkeypatch.setattr(util, 'data_dir', lambda: tmp_path)
    (tmp_path/'desktop-thread-sizes.json').write_text(value)
    assert app._thread_window_size(('realm', 'agent', 'thread')) == (520, 720)


@pytest.mark.parametrize('size', [[0, 500], [-1, 500], [True, 500], [600, '700'], [600], [10**20, 700]])
def test_invalid_saved_dimensions_use_default(tmp_path, monkeypatch, size):
    monkeypatch.setattr(util, 'data_dir', lambda: tmp_path)
    key = ('realm', 'agent', 'thread')
    util.write_json_atomic(tmp_path/'desktop-thread-sizes.json', {json.dumps(key): size})
    assert app._thread_window_size(key) == (520, 720)


def test_preferences_keep_subthreads_separate_and_write_failure_does_not_block_close(tmp_path, monkeypatch):
    monkeypatch.setattr(util, 'data_dir', lambda: tmp_path)
    native_forms(monkeypatch)
    monkeypatch.setattr(app.sys, 'platform', 'win32')
    main, other = ('realm', 'agent', 'main'), ('realm', 'agent', 'other')
    path = tmp_path/'desktop-thread-sizes.json'
    util.write_json_atomic(path, {json.dumps(main): [600, 800]})
    window = SimpleNamespace(native=SimpleNamespace(
        _scale=1, WindowState='normal', Bounds=SimpleNamespace(Width=700, Height=900)))
    monkeypatch.setattr(app, '_thread_windows', {other: window})
    app._remember_thread_size(other, window)
    assert app._thread_window_size(main) == (600, 800)
    assert app._thread_window_size(other) == (700, 900)
    monkeypatch.setattr(util, 'write_json_atomic', Mock(side_effect=OSError('read-only')))
    assert app._remember_thread_size(other, window) is None
