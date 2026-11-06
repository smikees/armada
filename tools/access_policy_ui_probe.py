"""Hidden WebView2 access-policy check; only a synthetic, temporary realm."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run(output):
    import webview
    from armada import app, local_auth, serve, util
    from tests.golden_support import build_fixture, fixture_inputs
    result = {'ok': False, 'checks': [], 'screenshots': []}
    with tempfile.TemporaryDirectory(prefix='armada-policy-ui-', ignore_cleanup_errors=True) as folder, fixture_inputs():
        root = Path(folder)
        from armada import execution_admission
        execution_admission._directory = lambda: root / 'data' / 'execution'
        os.environ.update(HOME=str(root / 'home'), USERPROFILE=str(root / 'home'),
            ARMADA_DATA_DIR=str(root / 'data'), ARMADA_NO_MODEL_SYNC='1', ARMADA_NOTIFY_MUTE='1')
        (root / 'home').mkdir()
        realm = Path(build_fixture(root / 'realm'))
        util.write_json_atomic(realm / 'realm.json', {'name': 'Synthetic access policy',
            'read_only': ['skills/**'], 'toolkit': {'connectors': [{'id': 'synthetic', 'name': 'Synthetic brokerage',
                'tool_names': ['get_balance', 'submit_order']}]}})
        util.write_json_atomic(realm / 'agents/captain/agent.json', {'id': 'captain', 'name': 'Synthetic analyst',
            'toolkit': {'connectors': [{'id': 'synthetic'}]},
            'tool_policy': {'synthetic': {'allow': ['get_*'], 'deny': ['submit_order']}},
            'write_scope': ['Finance/data/**', 'agents/captain/**']})

        class Fixture(serve.Handler):
            capture_html = ''
            def _route_get(self):
                if self.path.split('?')[0] == '/policy-screenshot':
                    self._send(200, type(self).capture_html.encode('utf-8'))
                elif self.path.split('?')[0] in {'/api/auth-status', '/api/scheduler-status',
                    '/api/proposals-count', '/api/notifications', '/api/providers', '/api/update-status'}:
                    self._json(200, {'ok': True, 'logged_in': True})
                else:
                    super()._route_get()
        Fixture.realm = realm
        server = serve._Server(('127.0.0.1', 0), Fixture)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f'http://127.0.0.1:{server.server_port}/'
        window = webview.create_window('Synthetic policy check',
            local_auth.browser_url(url, '/agent/captain/skills'), hidden=True, width=1280, height=900)
        def js(code):
            return window.evaluate_js(code)
        def check(label, predicate):
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                try:
                    if predicate():
                        result['checks'].append(label)
                        return
                except Exception:
                    pass
                time.sleep(.1)
            raise AssertionError(label)
        def capture(theme, width):
            js(f"document.documentElement.classList.toggle('armada-dark',{str(theme == 'dark').lower()})")
            Fixture.capture_html = js("""(() => {const copy=document.documentElement.cloneNode(true);
                copy.querySelectorAll('script').forEach(s=>s.remove());
                return '<!doctype html>'+copy.outerHTML;})()""") + "<script>addEventListener('load',()=>document.querySelector('.mc-access-policy').scrollIntoView())</script>"
            image = output.with_name(f'access-policy-{theme}-{width}.png').resolve()
            chrome = Path(os.environ.get('PROGRAMFILES', 'C:/Program Files')) / 'Google/Chrome/Application/chrome.exe'
            subprocess.run([str(chrome), '--headless=new', '--disable-gpu', '--no-first-run',
                '--disable-background-networking', '--disable-component-update', '--no-proxy-server',
                '--user-data-dir=' + str(root / f'chrome-{theme}-{width}'), '--virtual-time-budget=1500',
                f'--window-size={width},1000', '--screenshot=' + str(image),
                local_auth.browser_url(url, '/policy-screenshot')], check=True, timeout=30,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
            result['screenshots'].append(str(image))
        def exercise():
            try:
                check('Policy panel loads', lambda: js("!!document.querySelector('[data-save-agent-policy]')"))
                text = js("document.querySelector('.mc-access-policy').textContent")
                assert 'Can call: get_balance' in text and 'Cannot call: submit_order' in text
                result['checks'].append('Allowed and forbidden tools shown accurately')
                js("document.querySelector('.mc-access-policy > details').open=true")
                js("document.querySelector('[data-save-agent-policy]').closest('details').open=true;document.querySelector('[data-write-scope]').value='../**';document.querySelector('[data-save-agent-policy]').click()")
                check('Invalid path shows validation error', lambda: 'relative to the realm' in js("document.querySelector('[data-policy-status]').textContent"))
                assert util.read_json_state(realm / 'agents/captain/agent.json')['write_scope'][0] == 'Finance/data/**'
                js("document.querySelector('[data-write-scope]').value='Finance/review/**';document.querySelector('[data-save-agent-policy]').click()")
                check('Owner save persists', lambda: util.read_json_state(realm / 'agents/captain/agent.json')['write_scope'] == ['Finance/review/**'])
                check('Reload displays saved scope', lambda: 'May write only: Finance/review/**' in js("document.querySelector('.mc-access-policy').textContent"))
                assert util.read_json_state(realm / 'agents/captain/agent.json')['_policy_changes'][-1]['actor'] == 'owner'
                result['checks'].append('Owner change logged')
                js("document.querySelector('.mc-access-policy > details').open=true;document.querySelector('[data-save-agent-policy]').closest('details').open=true")
                capture('light', 1280)
                capture('dark', 720)
                result['ok'] = True
            except Exception:
                result['error'] = traceback.format_exc()
            finally:
                util.write_json_atomic(output, result)
                window.destroy()
        try:
            webview.start(exercise, gui='edgechromium', **app._webview_options())
        finally:
            server.shutdown()
            server.server_close()
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    raise SystemExit(run(parser.parse_args().output))
