"""Real, hidden WebView2 regression gate; synthetic data, no providers or live realm.

Run with the staged Windows runtime. Both windows exercise the production HTTP
authentication/bootstrap, not cookies supplied by a test client.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import traceback
from unittest.mock import patch


def verify(stage: Path):
    """Mandatory installer gate using the actual branded runtime and desktop browser."""
    import ctypes as c
    from ctypes import wintypes as w
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from armada.desktop_launch import spawn
    with tempfile.TemporaryDirectory(prefix='armada-session-result-') as directory:
        output = Path(directory) / 'result.json'
        pid = spawn([stage / 'python/ARMADA.exe', Path(__file__).resolve(), '--output', output], cwd=stage)
        kernel = c.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        kernel.OpenProcess.restype = w.HANDLE
        kernel.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
        kernel.CloseHandle.argtypes = [w.HANDLE]
        kernel.TerminateProcess.argtypes = [w.HANDLE, w.UINT]
        handle = kernel.OpenProcess(0x100001, False, pid)  # synchronize + terminate this owned probe
        if not handle:
            raise c.WinError(c.get_last_error())
        try:
            if kernel.WaitForSingleObject(handle, 90000) != 0:
                kernel.TerminateProcess(handle, 1)
                raise RuntimeError('Hidden WebView2 session gate timed out')
        finally:
            kernel.CloseHandle(handle)
        if not output.exists():
            raise RuntimeError('Hidden WebView2 session gate exited without a result')
        result = json.loads(output.read_text(encoding='utf-8'))
        if not result.get('ok'):
            raise RuntimeError('Hidden WebView2 session gate failed: ' + result.get('error', 'unknown error'))
        print(f"Native WebView2: {len(result['checks'])} multi-window session checks passed", flush=True)


def run(output: Path, *, source_root: str = '', legacy: bool = False) -> int:
    if source_root:
        sys.path.insert(0, source_root)
    import webview
    from armada import app, local_auth, serve

    result = {'ok': False, 'checks': []}
    windows = []
    with tempfile.TemporaryDirectory(prefix='armada-webview-', ignore_cleanup_errors=True) as directory:
        os.environ['ARMADA_DATA_DIR'] = directory

        class Fixture(serve.Handler):
            realm = None

            def _route_get(self):
                if self.path == '/api/usage':
                    self._json(200, {'total': 123})
                elif self.path in ('/', '/alexander'):
                    self._send(200, '<!doctype html><title>Session probe</title><script>'
                               'window.received=[];window.mcAlexReceive=p=>received.push(p);'
                               '</script><p>Authenticated fixture</p>')
                else:
                    self._send(404, 'missing', 'text/plain')

        server = serve._Server(('127.0.0.1', 0), Fixture)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f'http://127.0.0.1:{server.server_port}/'
        main = webview.create_window('ARMADA session probe', local_auth.browser_url(url), hidden=True)
        windows.append(main)

        def wait_page(window, path):
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if window.events.loaded.wait(.1):
                    if window.evaluate_js('location.pathname') == path:
                        return
                time.sleep(.1)
            raise AssertionError('Authenticated window did not become ready')

        def javascript(window, script):
            done = threading.Event()
            values = []
            def receive(value):
                values.append(value)
                done.set()
            window.evaluate_js(script, callback=receive)
            if not done.wait(10):
                raise AssertionError('Browser request did not complete')
            return values[0]

        def usage(window):
            return javascript(window, "fetch('/api/usage').then(async r=>({status:r.status,data:await r.json()}))")

        def check(label, condition):
            if not condition:
                raise AssertionError(label)
            result['checks'].append(label)

        def exercise():
            try:
                wait_page(main, '/')
                check('main Usage authenticated before companion', usage(main) == {'status': 200, 'data': {'total': 123}})
                for index in range(2):
                    if legacy:
                        companion = webview.create_window('Alexander session probe', url + 'alexander', hidden=True)
                    else:
                        create = webview.create_window
                        dropped = []
                        acknowledged = []
                        def hidden(*args, **kwargs):
                            window=create(*args, **dict(kwargs, hidden=True))
                            evaluate=window.evaluate_js
                            def uncertain(script,*args,**kwargs):
                                value=evaluate(script,*args,**kwargs)
                                if '__mcAlexDeliveryIds' in script and value is True:
                                    acknowledged.append(True)
                                    if not dropped:
                                        dropped.append(True)
                                        return None  # Real JS ran; simulate loss of its native acknowledgement.
                                return value
                            window.evaluate_js=uncertain
                            return window
                        with patch.object(app, '_main_window', main), patch.object(app, '_app_url', url), \
                             patch.object(app, '_alex_window', None), patch.object(webview, 'create_window', hidden):
                            check('production companion opener succeeds', app.open_alexander({'message': 'Test payload'}))
                            companion = app._alex_window
                    windows.append(companion)
                    wait_page(companion, '/alexander')
                    statuses = {'companion': usage(companion)['status'], 'main': usage(main)['status']}
                    result['statuses'] = statuses
                    check(f'companion {index + 1} authenticated', statuses['companion'] == 200)
                    check(f'main Usage survives companion {index + 1}', statuses['main'] == 200)
                    if not legacy:
                        deadline = time.monotonic() + 10
                        while (not companion.evaluate_js('received') or len(acknowledged)<2) and time.monotonic() < deadline:
                            time.sleep(.1)
                        result['received'] = companion.evaluate_js('received')
                        check('payload arrives exactly once: '+repr(result['received']), result['received'] ==
                              [{'message': 'Test payload', 'item': None, 'page': ''}])
                        check('lost delivery acknowledgement does not duplicate a request', bool(dropped) and len(acknowledged)>=2)
                    companion.destroy()
                    windows.remove(companion)
                    check('main Usage survives companion close', usage(main)['status'] == 200)
                main.load_url(local_auth.browser_url(url, '/'))
                wait_page(main, '/')
                check('main authenticated navigation works', usage(main)['status'] == 200)
                check('token removed from browser location', main.evaluate_js('location.hash') == '')
                # A public browser request cannot acquire a session without the private credential.
                check('bootstrap still rejects missing credentials', javascript(main,
                    "fetch('/auth',{method:'POST',credentials:'omit'}).then(r=>r.status)") == 401)
                result['ok'] = True
            except Exception:
                result['error'] = traceback.format_exc()
            finally:
                output.write_text(json.dumps(result, indent=2), encoding='utf-8')
                for window in reversed(windows):
                    window.destroy()

        try:
            options = {} if legacy else app._webview_options()
            webview.start(exercise, gui='edgechromium', **options)
        finally:
            server.shutdown()
            server.server_close()
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-root', default='')
    parser.add_argument('--legacy', action='store_true', help='Reproduce the previous private-mode behavior')
    args = parser.parse_args()
    raise SystemExit(run(args.output, source_root=args.source_root, legacy=args.legacy))
