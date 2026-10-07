"""Regression checks for the login-script/headless-server launch collision."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from unittest.mock import Mock

import pytest

from armada import app, cli, instance, local_auth, serve, startup, util
from armada.background import process_options

ROOT = Path(__file__).resolve().parents[1]
SERVER = """
import json,sys,threading,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from armada import app,instance,serve,startup,util
root=Path(sys.argv[2])
util.data_dir=lambda:root
instance._path=lambda:root/'desktop-instance.json'
def desktop(realm,port):
    owner=instance.current()
    assert instance.owned_role()=='app'
    assert serve._launch_mode()=='app'
    with instance.claim('app',port) as primary:
        assert primary
    util.write_json_atomic(root/'opened.json',dict(owner,main_thread=threading.current_thread() is threading.main_thread()))
    sys.stdin.readline()
    return 0
app.run=desktop
with instance.claim('serve',0) as primary:
    assert primary
    sys.exit(startup.serve_with_desktop('',0))
"""


def wait_for(fn, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = fn()
        if value:
            return value
        time.sleep(.05)
    raise AssertionError("Timed out waiting for synthetic startup")


def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def test_headless_owner_opens_desktop_without_replacing_server(tmp_path, monkeypatch):
    """Real process, account lock, activation file, listener and auth; only the UI is fake."""
    monkeypatch.setattr(instance, '_path', lambda: tmp_path/'desktop-instance.json')
    monkeypatch.setattr(instance, '_focus_pid', lambda _: False)
    child = subprocess.Popen([getattr(sys, '_base_executable', sys.executable), '-c', SERVER, str(ROOT), str(tmp_path)],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, **process_options())
    try:
        before = wait_for(lambda: (d if (d := instance.current()).get('server_ready') else None))
        assert before['role'] == 'serve'
        auth = read_json(tmp_path/'local-auth'/f"{before['port']}.json")
        with instance.claim('serve', 8890) as primary:
            assert not primary
        time.sleep(.35)
        assert not (tmp_path/'opened.json').exists()
        assert instance.current() == before

        # Concurrent desktop requests must all reuse the same process.
        errors = []
        def activate():
            try:
                instance.activate(before)
            except Exception as error:
                errors.append(error)
        launches = [threading.Thread(target=activate) for _ in range(3)]
        for launch in launches: launch.start()
        for launch in launches: launch.join(timeout=15)
        assert not errors and not any(t.is_alive() for t in launches)
        opened = wait_for(lambda: read_json(tmp_path/'opened.json'))
        assert opened['pid'] == before['pid'] == child.pid
        assert opened['port'] == before['port'] and opened['nonce'] == before['nonce']
        assert opened['role'] == 'app' and opened['main_thread']
        assert read_json(tmp_path/'local-auth'/f"{before['port']}.json") == auth
        import urllib.request
        req = urllib.request.Request(f"http://127.0.0.1:{before['port']}/api/instance",
                                     headers={'Authorization': 'Bearer '+auth['token']})
        with urllib.request.urlopen(req, timeout=3) as response:
            assert json.load(response)['nonce'] == before['nonce']
    finally:
        try:
            out, err = child.communicate('\n', timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
            out, err = child.communicate(timeout=5)
            pytest.fail(f"synthetic server did not exit: {err}")
    assert child.returncode == 0, err
    assert not (tmp_path/'desktop-instance.json').exists()


def test_older_headless_owner_is_a_clear_error_not_a_success(monkeypatch):
    monkeypatch.setattr(instance, '_focus_pid', lambda _: False)
    with pytest.raises(instance.ActivationError, match=r"older background server \(PID 123\)"):
        instance.activate({'pid': 123, 'role': 'serve', 'nonce': 'old'})
    instance.activate({'pid': 123, 'role': 'serve'}, 'serve')  # headless reuse is still OK


def test_legacy_gui_can_still_be_focused(monkeypatch):
    focus = Mock(return_value=True)
    monkeypatch.setattr(instance, '_focus_pid', focus)
    instance.activate({'pid': 123, 'legacy': True})
    focus.assert_called_once_with(123)


def test_unresponsive_new_server_reports_activation_failure(monkeypatch):
    monkeypatch.setattr(instance, '_focus_pid', lambda _: False)
    with pytest.raises(instance.ActivationError, match='did not open its desktop'):
        instance.activate({'pid': 123, 'role': 'serve', 'nonce': 'stuck',
                           'activation_protocol': 1}, timeout=0)


def test_runtime_role_is_used_by_restart_after_promotion(monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['armada', 'serve'])
    with instance.claim('serve', 0):
        assert serve._launch_mode() == 'serve'
        instance.promote_to_desktop()
        assert serve._launch_mode() == 'app'


@pytest.mark.parametrize('raises', [True, False])
def test_failed_native_promotion_preserves_server_and_explains_next_launch(monkeypatch, raises):
    stop = threading.Event()
    preserved = []
    def server(realm, port):
        serve.Handler.realm = realm
        instance.server_ready()
        stop.wait(5)
    monkeypatch.setattr(serve, 'serve', server)
    monkeypatch.setattr(instance, '_focus_pid', lambda _: False)
    run = Mock(side_effect=RuntimeError('native window failed')) if raises else Mock(return_value=1)
    monkeypatch.setattr(app, 'run', run)
    report = Mock()
    monkeypatch.setattr(startup, 'report_failure', report)
    with instance.claim('serve', 8877):
        nonce = instance.current()['nonce']
        util.write_json_atomic(instance._path().with_name('desktop-activate.json'),
                               {'nonce': nonce, 'request': 'legacy-client'})  # old clients omit role
        def observe():
            try:
                owner = wait_for(lambda: (d if (d := instance.current()).get('desktop_error') else None))
                preserved.append(owner)
                with pytest.raises(instance.ActivationError, match='background server is still running'):
                    instance.activate(owner)
            finally:
                stop.set()
        observer = threading.Thread(target=observe)
        observer.start()
        assert startup.serve_with_desktop('', 8877) == 0
        observer.join(timeout=5)
        assert preserved and preserved[0]['role'] == 'serve' and preserved[0]['nonce'] == nonce
        assert not preserved[0]['desktop_ready']
    assert report.call_count == (1 if raises else 0)
    if raises:
        assert str(report.call_args.args[0]) == 'native window failed'
        assert report.call_args.kwargs == {'gui': True}


@pytest.mark.parametrize('stage', ['early', 'cli'])
def test_gui_entrypoint_reports_errors_before_or_during_cli(monkeypatch, stage):
    from armada import __main__, desktop_launch, updater
    monkeypatch.setattr(sys, 'argv', ['armada', 'app'])
    monkeypatch.setattr(updater, 'installed', lambda: False)
    fail = Mock(side_effect=OSError('access denied'))
    monkeypatch.setattr(desktop_launch, 'relaunch_if_needed', fail if stage == 'early' else lambda _: False)
    if stage == 'cli':
        monkeypatch.setattr(cli, 'main', fail)
    report = Mock()
    monkeypatch.setattr(startup, 'report_failure', report)
    assert __main__.entrypoint() == 1
    assert str(report.call_args.args[0]) == 'access denied'
    assert report.call_args.kwargs == {'gui': True}


def test_error_report_survives_log_failure_without_console(monkeypatch):
    import ctypes
    from types import SimpleNamespace
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setattr(sys, 'stderr', None)
    monkeypatch.setattr(util, 'init_logging', Mock(side_effect=PermissionError('read only')))
    box = Mock()
    monkeypatch.setattr(ctypes, 'windll', SimpleNamespace(user32=SimpleNamespace(MessageBoxW=box)), raising=False)
    startup.report_failure(OSError('port unavailable'), gui=True)
    assert box.call_count == 1
    assert 'port unavailable' in box.call_args.args[1]


def test_close_saves_state_off_the_calling_thread_before_final_close(monkeypatch):
    saved = []
    allowed = threading.Event()
    main = Mock()
    monkeypatch.setattr(app, 'save_window_state', lambda: saved.append(threading.current_thread()))
    def close(window):
        assert allowed.is_set() and saved and window is main
    monkeypatch.setattr(app, '_quit_windows', close)
    app._finish_close(main, allowed)
    assert saved[0] is not threading.current_thread()


def test_unresponsive_browser_cannot_block_full_quit(monkeypatch, caplog):
    blocked = threading.Event()
    monkeypatch.setattr(app, 'save_window_state', lambda: blocked.wait(5))
    quit_window = Mock()
    monkeypatch.setattr(app, '_quit_windows', quit_window)
    allowed = threading.Event()
    try:
        start = time.monotonic()
        app._finish_close(Mock(), allowed)
        assert time.monotonic() - start < 4
    finally:
        blocked.set()
    assert allowed.is_set() and quit_window.call_count == 1
    assert 'continuing to quit' in caplog.text


def test_headless_duplicate_cannot_erase_a_pending_desktop_request(monkeypatch):
    monkeypatch.setattr(instance, '_focus_pid', lambda _: False)
    owner = {'pid': 123, 'role': 'app', 'nonce': 'existing'}
    instance.activate(owner)
    path = instance._path().with_name('desktop-activate.json')
    before = path.read_bytes()
    instance.activate(owner, 'serve')
    assert path.read_bytes() == before
