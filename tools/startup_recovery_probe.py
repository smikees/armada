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


def open_tray_and_wait(tray, action, *, timeout=3):
    """Wait for this Open callback, even when the window was already visible."""
    delivered = threading.Event()
    failures = []
    original = tray.show

    def observed_show():
        try:
            original()
        except Exception as exc:
            failures.append(exc)
        finally:
            delivered.set()

    tray.show = observed_show
    try:
        tray._dispatcher.BeginInvoke(action(lambda: tray._icon.ContextMenuStrip.Items[0].PerformClick()))
        if not delivered.wait(timeout):
            raise AssertionError('Tray Open callback was not delivered')
        if failures:
            raise AssertionError('Tray Open callback failed') from failures[0]
    finally:
        tray.show = original


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
        for mode in ('visible', 'tray', 'busy'):
            output = Path(directory) / (mode+'.json')
            completed = subprocess.run([str(stage/'python/python.exe'), str(Path(__file__).resolve()),
                '--output', str(output), '--restart', mode, '--staged'], cwd=stage, timeout=120,
                creationflags=subprocess.CREATE_NO_WINDOW, capture_output=True, text=True)
            if not output.exists():
                raise RuntimeError('Native restart gate exited without evidence: '+completed.stderr[-2000:])
            restart = json.loads(output.read_text(encoding='utf-8'))
            if completed.returncode or not restart.get('ok'):
                raise RuntimeError('Native restart gate failed: '+restart.get('error', completed.stderr[-2000:]))
            evidence = Path(__file__).resolve().parents[1]/('build/restart-'+mode+'-staged.json')
            evidence.write_text(json.dumps(restart, indent=2), encoding='utf-8')
            print(f"Native restart ({mode}): {len(restart['checks'])} teardown checks passed", flush=True)


def run(output, *, tray_lifecycle=False, staged=False, restart_mode=None, presentation=None):
    if not staged:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import webview
    import webbrowser
    from armada import app, assets, desktop_navigation, instance, local_auth, schedsvc, serve, startup, util
    from armada.tray import Tray
    from armada.desktop_visibility import DesktopVisibility
    result = {'ok': False, 'checks': []}
    windows = []
    trays = []
    done = threading.Event()
    external_urls = []
    local_popups = []
    restart_completed = []
    effects = {'started': 0, 'finished': 0}
    finish_effect = threading.Event()
    draft_script = ((Path(app.__file__).parent/'webui/static/js/chat.js').read_text(encoding='utf-8')
                    .split('function mcAutosize()', 1)[0]) if presentation else ''
    handle_popup = desktop_navigation.handle_popup
    def observed_popup(backend, args, base):
        handled = handle_popup(backend, args, base)
        local_popups.append((str(args.Uri), handled))
        return handled
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
                               ('<meta name="armada-realm" content="none">' if presentation else '')+
                               '</head><body><main id="probe-home">Synthetic ARMADA home</main>'
                               '<a id="probe-nav" href="/?_realm=none">Overview</a>'+
                               ('<textarea id="mc-msg"></textarea><script>'+draft_script+'</script>' if presentation else '')+
                               '</body></html>')
                elif presentation and path == '/alexander':
                    self._get_alexander()
                elif path == '/settings':
                    raise RuntimeError('Synthetic Settings failure')
                elif path == '/expire-session':
                    self.send_response(204)
                    self.send_header('Set-Cookie', f'{self.server.auth.cookie_name}=; Max-Age=0; HttpOnly; SameSite=Strict; Path=/')
                    self.end_headers()
                elif path.startswith('/api/'):
                    self._json(200, {})
                else:
                    super()._route_get()

            def _route_post(self):
                if presentation and self.path.split('?')[0] == '/api/probe-effect':
                    self._body()
                    effects['started'] += 1
                    finish_effect.wait(40)
                    effects['finished'] += 1
                    self._json(200, {'ok': True})
                else:
                    super()._route_post()

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
            user = c.WinDLL('user32', use_last_error=True)
            user.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
            user.SendMessageTimeoutW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM,
                                               w.UINT, w.UINT, c.POINTER(c.c_size_t)]
            hwnd = native.Handle.ToInt64()
            def ping():
                value = c.c_size_t()
                assert user.SendMessageTimeoutW(hwnd, 0, 0, 0, 3, 1000, c.byref(value)), 'UI thread not responding'
            def open_tray():
                # Visible can already be true before the asynchronously dispatched
                # Open runs. A following Close must not overtake that callback.
                open_tray_and_wait(tray, Action)
            window.evaluate_js("(()=>{let e=document.getElementById('mc-msg');if(!e){e=document.createElement('textarea');e.id='mc-msg';document.body.append(e);}e.value='unsent draft';e.dispatchEvent(new Event('input'));})()")
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
                window.evaluate_js("document.getElementById('probe-nav').click();true")
                wait_for(lambda: window.evaluate_js('location.pathname+location.search') == '/?_realm=none',
                         'ordinary left-click navigation remains inside the desktop')
                assert not external_urls
                window.load_url(f"http://127.0.0.1:{before['port']}/resume")
                wait_for(lambda: window.evaluate_js('location.pathname') == '/resume', 'return to saved page')
                # Exercise the real WebView2 popup event, not a mocked click handler.
                window.evaluate_js("(()=>{const a=document.createElement('a');a.href='/?_realm=none';a.target='_blank';document.body.append(a);a.click();return true;})()")
                wait_for(lambda: window.evaluate_js('location.pathname+location.search') == '/?_realm=none',
                         'internal new-window link stays in authenticated desktop')
                assert not external_urls
                window.evaluate_js("window.open('https://example.com/armada-probe','_blank');true")
                wait_for(lambda: external_urls == ['https://example.com/armada-probe'],
                         'external links still reach the browser handler without a credential')
                window.evaluate_js("(()=>{const f=document.createElement('iframe');f.sandbox='allow-scripts allow-popups';"
                    "f.srcdoc=\"<script>window.open('"+f"http://127.0.0.1:{before['port']}/resume?blocked-probe=1"+
                    "','_blank')<\\/script>\";document.body.append(f);return true;})()")
                wait_for(lambda: any('blocked-probe=1' in url and handled for url, handled in local_popups),
                         'sandboxed frame popup is intercepted by the native policy')
                assert window.evaluate_js('location.pathname+location.search') == '/?_realm=none'
                assert external_urls == ['https://example.com/armada-probe']
                result['checks'].append('untrusted frame cannot open a privileged page or a browser tab')
                # Lose the real HttpOnly cookie after startup has finished. No
                # server restart or timer assumption is needed to reproduce it.
                assert app._browser_result(window, "fetch('/expire-session',{method:'GET'}).then(r=>r.status)") == 204
                assert app._browser_result(window, "fetch('/api/instance').then(r=>r.status)") == 401
                window.load_url(f"http://127.0.0.1:{before['port']}/resume?_realm=none")
                wait_for(lambda: (window.evaluate_js('location.pathname+location.search') == '/resume?_realm=none'
                                  and window.evaluate_js("!!document.getElementById('probe-home')")),
                         'lost desktop cookie recovers after startup and preserves destination')
                assert app._browser_result(window, "fetch('/api/instance').then(r=>r.status)") == 200
                assert window.evaluate_js('location.hash') == ''
                result['checks'].append('recovered session authenticates requests and removes bootstrap fragment')
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
                if presentation:
                    presentation(window, result, wait_for, before, effects, finish_effect)
                result['ok'] = True
            except BaseException:
                result['error'] = traceback.format_exc()
            finally:
                finish_effect.set()
                if restart_mode and result['ok']:
                    from System import Action, Func, Int32
                    from System.Diagnostics import Process
                    native = window.native
                    browser = native.browser.webview
                    browser_pid = native.Invoke(Func[Int32](lambda: int(browser.CoreWebView2.BrowserProcessId)))
                    browser_process = Process.GetProcessById(browser_pid)
                    hwnd = native.Handle.ToInt64()
                    app.save_before_close()
                    if restart_mode == 'tray':
                        native.Invoke(Action(native.Hide))
                    elif restart_mode == 'busy':
                        window.evaluate_js('setTimeout(()=>{while(true){}},50);true')
                        time.sleep(.1)
                    def after_close():
                        import ctypes
                        assert threading.current_thread() is threading.main_thread()
                        assert native.IsDisposed and browser.IsDisposed
                        assert app._main_window is None and not webview.windows
                        assert not trays[0]._thread.IsAlive
                        user = ctypes.WinDLL('user32')
                        user.IsWindow.argtypes = [ctypes.c_void_p]
                        assert not user.IsWindow(hwnd)
                        assert browser_process.WaitForExit(5000), 'WebView2 browser did not exit'
                        restart_completed.append(True)
                        result['checks'].append('restart waits for disposed form/browser, vanished HWND and stopped tray/browser process: '+restart_mode)
                    app.restart_desktop(after_close)
                elif tray_lifecycle and trays and result['ok']:
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
                (webbrowser, 'open', lambda url, *a, **k: external_urls.append(url) or True),
                (desktop_navigation, 'handle_popup', observed_popup),
            ]:
                stack.enter_context(patch.object(obj, name, value))
            if not tray_lifecycle:
                stack.enter_context(patch.object(Tray, 'stop', lambda _: None))
            else:
                stack.enter_context(patch.object(DesktopVisibility, '_native_apply', invisible_apply))
            def watchdog():
                if not done.wait(180 if presentation else 80):
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
                    if restart_mode:
                        assert restart_completed == [True]
                    state = json.loads((root/'data'/'desktop-state.json').read_text(encoding='utf-8'))
                    assert state['route'] == ('/?_realm=none' if presentation else '/')
                    if tray_lifecycle:
                        assert state['draft'] == 'unsent draft'
                        assert not trays[0]._thread.IsAlive
                        result['checks'].append(('restart' if restart_mode else 'tray Quit')+' saves draft and shuts down both native UI loops')
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
    parser.add_argument('--restart', choices=['visible', 'tray', 'busy'], help='Verify native teardown before restart handover')
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    raise SystemExit(run(args.output, tray_lifecycle=args.tray or bool(args.restart), staged=args.staged, restart_mode=args.restart))
