"""Hidden native WebView2 check of headless promotion and recovery navigation.

Uses the production server, owner lock, desktop and authentication bootstrap with a
synthetic home page. No real realms, providers, startup registry or schedulers are used.
Run: python tools/startup_recovery_probe.py --output <result.json>
"""
from __future__ import annotations
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import traceback
from unittest.mock import patch


def verify_tray(stage):
    """Installer gate: exercise the staged package with real tray/WinForms loops."""
    import subprocess
    with tempfile.TemporaryDirectory(prefix='armada-tray-result-') as directory:
        output = Path(directory) / 'result.json'
        completed = subprocess.run([str(stage/'python/python.exe'), str(Path(__file__).resolve()),
            '--output', str(output), '--tray', '--staged'], cwd=stage, timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW, capture_output=True, text=True)
        if not output.exists():
            raise RuntimeError('Native tray gate exited without evidence: ' + completed.stderr[-2000:])
        result = json.loads(output.read_text(encoding='utf-8'))
        if completed.returncode or not result.get('ok'):
            raise RuntimeError('Native tray gate failed: ' + result.get('error', completed.stderr[-2000:]))
        evidence = Path(__file__).resolve().parents[1]/'build/tray-lifecycle-staged.json'
        evidence.write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(f"Native tray: {len(result['checks'])} lifecycle/recovery checks passed", flush=True)


def run(output, *, tray_lifecycle=False, staged=False):
    if not staged:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import webview
    from armada import app, assets, instance, local_auth, schedsvc, serve, startup, util
    from armada.tray import Tray
    from armada.desktop_visibility import DesktopVisibility
    result = {'ok': False, 'checks': []}
    windows = []
    trays = []
    done = threading.Event()
    with tempfile.TemporaryDirectory(prefix='armada-startup-probe-', ignore_cleanup_errors=True) as directory:
        root = Path(directory)
        (root/'home').mkdir()
        (root/'data').mkdir()
        (root/'data'/'desktop-state.json').write_text(
            json.dumps({'route':'/resume', 'realm':'none'}), encoding='utf-8')
        class Fixture(serve.Handler):
            def _route_get(self):
                path = self.path.split('?')[0]
                if path in ('/', '/resume'):
                    self._send(200, '<!doctype html><html><head>'+assets.CSS_LINKS+
                               '</head><body><main id="probe-home">Synthetic ARMADA home</main></body></html>')
                elif path == '/settings':
                    raise RuntimeError('Synthetic Settings failure')
                elif path.startswith('/api/'):
                    self._json(200, {})
                else:
                    super()._route_get()

        def wait_for(fn, label, timeout=30):
            deadline = time.monotonic()+timeout
            while time.monotonic() < deadline:
                try:
                    if fn():
                        result['checks'].append(label)
                        return
                except Exception:
                    pass  # Navigation can briefly replace the JavaScript execution context.
                time.sleep(.1)
            raise AssertionError(label)

        create = webview.create_window
        def hidden_create(*args, **kwargs):
            window = create(*args, **dict(kwargs, hidden=True))
            window.show = lambda: None
            window.restore = lambda: None
            windows.append(window)
            return window

        start_tray = Tray.start
        def tracked_tray(tray):
            trays.append(tray)
            return start_tray(tray)

        native_apply = DesktopVisibility._native_apply
        def invisible_apply(visibility, visible):
            visibility.window.native.Opacity = 0
            native_apply(visibility, visible)

        def exercise_tray(window):
            import ctypes as c
            from ctypes import wintypes as w
            from System import Action
            from System.Windows.Forms import FormWindowState
            native = window.native
            def prepare():
                native.Opacity = 0
                native.ShowInTaskbar = False
            native.Invoke(Action(prepare))
            tray = trays[0]
            assert tray._context is not None and tray._icon is not None
            menu = tray._icon.ContextMenuStrip
            user = c.WinDLL('user32', use_last_error=True)
            user.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
            user.SendMessageTimeoutW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM,
                                               w.UINT, w.UINT, c.POINTER(c.c_size_t)]
            hwnd = native.Handle.ToInt64()
            def ping():
                value = c.c_size_t()
                assert user.SendMessageTimeoutW(hwnd, 0, 0, 0, 3, 1000, c.byref(value)), 'UI thread not responding'
            def open_tray():
                tray._dispatcher.BeginInvoke(Action(lambda: menu.Items[0].PerformClick()))
            window.evaluate_js("document.body.insertAdjacentHTML('beforeend','<textarea id=mc-msg>unsent draft</textarea>')")
            for index in range(20):
                open_tray()
                wait_for(lambda: native.Visible, f'tray restores main {index + 1}', timeout=3)
                ping()
                assert user.PostMessageW(hwnd, 0x10, 0, 0)
                wait_for(lambda: not native.Visible, f'close hides main {index + 1}', timeout=3)
                ping()
            open_tray()
            wait_for(lambda: native.Visible, 'restore after repeated closes', timeout=3)
            native.BeginInvoke(Action(lambda: setattr(native, 'WindowState', FormWindowState.Minimized)))
            wait_for(lambda: not native.Visible, 'minimize moves main to tray', timeout=3)
            open_tray()
            wait_for(lambda: native.Visible and native.WindowState == FormWindowState.Normal,
                     'tray restores minimized main', timeout=3)
            # A blocked snapshot models a renderer that never completes JS. It must
            # not stall either UI loop, and an intervening restore must win.
            visibility = app._desktop_visibility
            save = visibility.save_state
            entered, release = threading.Event(), threading.Event()
            def blocked_save():
                entered.set()
                release.wait(10)
            try:
                visibility.save_state = blocked_save
                user.PostMessageW(hwnd, 0x10, 0, 0)
                assert entered.wait(2)
                open_tray()
                time.sleep(.7)
                ping()
                assert native.Visible, 'late hide overrode tray restore'
                result['checks'].append('restore wins over delayed close snapshot')
                user.PostMessageW(hwnd, 0x10, 0, 0)
                wait_for(lambda: not native.Visible, 'blocked renderer cannot prevent close-to-tray', timeout=2)
                ping()
            finally:
                release.set()
                visibility.save_state = save
            open_tray()
            wait_for(lambda: native.Visible, 'restore after renderer timeout', timeout=3)
            assert window.evaluate_js("document.getElementById('mc-msg').value") == 'unsent draft'
            result['checks'].append('draft and authenticated page survive tray transitions')
            # Actual renderer work must not block the native hide/restore loop.
            window.evaluate_js("setTimeout(()=>{const end=Date.now()+1500;while(Date.now()<end){}},20)")
            time.sleep(.1)
            user.PostMessageW(hwnd, 0x10, 0, 0)
            wait_for(lambda: not native.Visible, 'close while WebView2 is busy', timeout=2)
            ping()
            open_tray()
            wait_for(lambda: native.Visible, 'restore while WebView2 is busy', timeout=2)
            assert window.evaluate_js('1+1') == 2
            result['checks'].append('renderer resumes after busy close/restore')

        def controller():
            try:
                wait_for(lambda: instance.current().get('server_ready'), 'headless server ready')
                before = instance.current()
                token = local_auth.headers(before['port'])
                assert before['role'] == 'serve' and not windows
                instance.activate(before)
                wait_for(lambda: instance.current().get('desktop_ready'), 'real desktop bootstrap ready')
                after = instance.current()
                assert after['role'] == 'app'
                assert (after['pid'], after['port'], after['nonce']) == (before['pid'], before['port'], before['nonce'])
                assert local_auth.headers(before['port']) == token
                assert serve._launch_mode() == 'app'
                result['checks'].append('owner, listener and authentication preserved; restart uses app')
                window = windows[0]
                assert window.evaluate_js('location.pathname') == '/resume'
                assert window.evaluate_js('typeof window.mcIcon') == 'undefined'
                result['checks'].append('saved page without optional icon helper starts and retains its route')
                window.load_url(f"http://127.0.0.1:{before['port']}/settings")
                wait_for(lambda: window.evaluate_js("!!document.querySelector('[data-armada-recovery=\"500\"]')"),
                         'Settings failure shows recovery page')
                window.evaluate_js("document.querySelector('a[href=\"/\"]').click()")
                wait_for(lambda: window.evaluate_js("!!document.getElementById('probe-home')"),
                         'Return to ARMADA opens authenticated home')
                window.load_url(f"http://127.0.0.1:{before['port']}/settings?_realm=stale")
                wait_for(lambda: window.evaluate_js("!!document.querySelector('[data-armada-recovery=\"409\"]')"),
                         'stale realm shows recovery page')
                window.evaluate_js("document.querySelector('a[href=\"/\"]').click()")
                wait_for(lambda: window.evaluate_js("!!document.getElementById('probe-home')"),
                         'recovery navigation drops stale realm')
                if tray_lifecycle:
                    exercise_tray(window)
                result['ok'] = True
            except BaseException:
                result['error'] = traceback.format_exc()
            finally:
                if tray_lifecycle and trays and result['ok']:
                    from System import Action
                    tray = trays[0]
                    tray._dispatcher.BeginInvoke(Action(lambda: tray._icon.ContextMenuStrip.Items[1].PerformClick()))
                else:
                    for window in windows:
                        try: app._quit_windows(window)
                        except Exception: pass

        def fatal(message):
            raise RuntimeError(message)

        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ, {'ARMADA_DATA_DIR': str(root/'data'),
                'ARMADA_NO_MODEL_SYNC': '1', 'ARMADA_NO_EXTERNAL_NOTIFY': '1',
                'HOME': str(root/'home'), 'USERPROFILE': str(root/'home')}))
            for obj, name, value in [
                (instance, '_account_directory', lambda: root/'data'), (instance, '_focus_pid', lambda _: False),
                (serve, 'Handler', Fixture), (webview, 'create_window', hidden_create),
                (app, '_retire_scheduler_run_key', lambda: None), (app, '_fatal', fatal),
                (app, '_confirm_startup_health', lambda: None),
                (schedsvc, 'watch', lambda *_: None), (schedsvc, 'stop_for_app_exit', lambda: None),
                (Tray, 'start', tracked_tray if tray_lifecycle else lambda _: False),
            ]:
                stack.enter_context(patch.object(obj, name, value))
            if not tray_lifecycle:
                stack.enter_context(patch.object(Tray, 'stop', lambda _: None))
            else:
                stack.enter_context(patch.object(DesktopVisibility, '_native_apply', invisible_apply))
            def watchdog():
                if not done.wait(80):
                    output.write_text(json.dumps(dict(result, ok=False, error='native probe timed out; '+result.get('error', 'unfinished teardown')), indent=2), encoding='utf-8')
                    os._exit(2)
            threading.Thread(target=watchdog, daemon=True).start()
            with instance.claim('serve', 0) as primary:
                assert primary
                threading.Thread(target=controller, daemon=True).start()
                code = startup.serve_with_desktop('', 0)
                done.set()
                if result['ok']:
                    assert app._main_window is None and not webview.windows
                    state = json.loads((root/'data'/'desktop-state.json').read_text(encoding='utf-8'))
                    assert state['route'] == '/'
                    if tray_lifecycle:
                        assert state['draft'] == 'unsent draft'
                        assert not trays[0]._thread.IsAlive
                        result['checks'].append('tray Quit saves draft and shuts down both native UI loops')
                    result['checks'].append('native close completes and saves window state')
                if code:
                    result['ok'] = False
                    result.setdefault('error', f'desktop returned {code}')
        output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tray', action='store_true', help='Exercise real tray callbacks and visibility races')
    parser.add_argument('--staged', action='store_true', help='Use installed package instead of source checkout')
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    raise SystemExit(run(args.output, tray_lifecycle=args.tray, staged=args.staged))
