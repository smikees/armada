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


def run(output):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import webview
    from armada import app, assets, icons, instance, local_auth, schedsvc, serve, startup, util
    from armada.tray import Tray
    result = {'ok': False, 'checks': []}
    windows = []
    done = threading.Event()
    with tempfile.TemporaryDirectory(prefix='armada-startup-probe-', ignore_cleanup_errors=True) as directory:
        root = Path(directory)
        (root/'home').mkdir()
        class Fixture(serve.Handler):
            def _route_get(self):
                path = self.path.split('?')[0]
                if path == '/':
                    self._send(200, '<!doctype html><html><head>'+assets.CSS_LINKS+icons._ICONS_JS+
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
                result['ok'] = True
            except BaseException:
                result['error'] = traceback.format_exc()
            finally:
                for window in windows:
                    try: app._quit_windows(window)
                    except Exception: pass
                done.set()

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
                (Tray, 'start', lambda _: False), (Tray, 'stop', lambda _: None),
            ]:
                stack.enter_context(patch.object(obj, name, value))
            def watchdog():
                if not done.wait(80):
                    output.write_text(json.dumps(dict(result, ok=False, error='native probe timed out; '+result.get('error', 'unfinished teardown')), indent=2), encoding='utf-8')
                    os._exit(2)
            threading.Thread(target=watchdog, daemon=True).start()
            with instance.claim('serve', 0) as primary:
                assert primary
                threading.Thread(target=controller, daemon=True).start()
                code = startup.serve_with_desktop('', 0)
                if result['ok']:
                    assert app._main_window is None and not webview.windows
                    state = json.loads((root/'data'/'desktop-state.json').read_text(encoding='utf-8'))
                    assert state['route'] == '/'
                    result['checks'].append('native close completes and saves window state')
                if code:
                    result['ok'] = False
                    result.setdefault('error', f'desktop returned {code}')
        output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    raise SystemExit(run(args.output))
