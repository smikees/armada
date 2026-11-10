"""Synthetic WebView2 journeys for app system memory and owner timing overrides."""
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


def run(output):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    output = output.resolve()
    with tempfile.TemporaryDirectory(prefix='armada-timed-inbox-', ignore_cleanup_errors=True) as directory:
        home = Path(directory)
        for name in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA'):
            os.environ[name] = str(home / name)
            Path(os.environ[name]).mkdir()
        os.environ.update(ARMADA_DATA_DIR=str(home / 'account'), ARMADA_NO_MODEL_SYNC='1', ARMADA_NO_EXTERNAL_NOTIFY='1')
        import webview
        from armada import app, serve, local_auth, util, inbox, runner, system_memory
        from tests.golden_support import build_fixture
        root = Path(build_fixture(home / 'realm'))
        agents = sorted(p.name for p in (root / 'agents').iterdir() if p.is_dir())
        sender, recipient = agents[:2]
        item = inbox.send(root, sender, recipient, 'Synthetic future task',
                          process_after='2099-11-09T09:00:00+01:00', process_before='2099-11-10T09:00:00+01:00')
        assert item['ok'], item
        calls, revealed = [], []
        runner.recipient_access = lambda *a: {'ok': True, 'provider': 'mock'}
        def fake_turn(*args, **kw):
            calls.append(kw)
            return {'status': 'ok', 'summary': 'Synthetic task completed'}
        runner.run_job_prompt = fake_turn

        class Fixture(serve.Handler):
            capture_html = ''

            def _reveal(self, body):
                revealed.append(Path(body['path']))
                return {'ok': True}

            def _route_get(self):
                path = self.path.split('?')[0]
                if path == '/probe-screenshot':
                    self._send(200, type(self).capture_html)
                elif path == '/api/providers':
                    self._json(200, {'providers': {p: {} for p in ('claude', 'codex', 'gemini')}, 'models': []})
                elif path.startswith('/api/') and path not in ('/api/font-size', '/api/thread-state'):
                    self._json(200, {})
                else:
                    super()._route_get()

        Fixture.realm = str(root)
        server = serve._Server(('127.0.0.1', 0), Fixture)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{server.server_port}/'
        window = webview.create_window('Synthetic inbox timing', local_auth.browser_url(base, '/settings?tab=app'),
                                       width=1100, height=900, hidden=True)
        loaded = threading.Event()
        window.events.loaded += lambda: loaded.set()
        result = {'ok': False, 'checks': [], 'screenshots': []}

        def js(code):
            return app._browser_result(window, code, timeout=5)

        def wait(predicate, label):
            end = time.monotonic() + 15
            while time.monotonic() < end:
                try:
                    if predicate():
                        result['checks'].append(label)
                        return
                except Exception:
                    pass
                time.sleep(.05)
            raise AssertionError(label)

        def navigate(path):
            loaded.clear()
            window.load_url(local_auth.browser_url(base, path))
            assert loaded.wait(15), path
            wait(lambda: js('document.readyState==="complete"&&location.pathname==='+json.dumps(path.split('?')[0])), 'Loaded '+path)

        def capture(name, focus):
            chrome = Path(os.environ.get('PROGRAMFILES', 'C:/Program Files')) / 'Google/Chrome/Application/chrome.exe'
            Fixture.capture_html = js("(() => {const copy=document.documentElement.cloneNode(true);copy.querySelectorAll('script').forEach(s=>s.remove());document.querySelectorAll('textarea').forEach((el,i)=>copy.querySelectorAll('textarea')[i].textContent=el.value);return '<!doctype html>'+copy.outerHTML;})()")
            Fixture.capture_html += "<script>addEventListener('load',()=>document.querySelector("+json.dumps(focus)+").scrollIntoView({block:'center'}))</script>"
            width, height = json.loads(js('JSON.stringify([innerWidth,innerHeight])'))
            path = output.with_name(name+'.png')
            subprocess.run([str(chrome), '--headless=new', '--disable-gpu', '--no-first-run',
                '--disable-background-networking', '--disable-component-update', '--no-proxy-server',
                '--user-data-dir='+str(home / ('chrome-'+name)), '--virtual-time-budget=1500',
                f'--window-size={width},{height}', '--screenshot='+str(path),
                local_auth.browser_url(base, '/probe-screenshot')], check=True, timeout=30,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
            assert path.is_file() and path.stat().st_size > 1000
            result['screenshots'].append(str(path))

        def exercise():
            try:
                wait(lambda: js("document.readyState==='complete'&&!!document.getElementById('mc-system-memory-open')"), 'System memories available in App settings')
                js("document.documentElement.classList.remove('armada-dark');document.body.classList.remove('armada-dark')")
                capture('timed-inbox-settings-light', '.mc-system-memory-row')
                js("document.getElementById('mc-system-memory-open').click();true")
                assert js("!!document.querySelector('#mc-system-memory-dialog:modal')")
                settings_text = js("document.querySelector('.mc-system-memory-text').textContent")
                assert 'process_after' in settings_text
                assert not js("!!document.querySelector('#mc-system-memory-dialog textarea, #mc-system-memory-dialog [contenteditable]')")
                js("document.querySelector('#mc-system-memory-dialog button').click();true")
                assert not js("document.getElementById('mc-system-memory-dialog').open")
                js("document.getElementById('mc-system-memory-file').click();true")
                wait(lambda: revealed == [system_memory.load().path], 'File action reveals the source of the displayed guidance')
                navigate('/memory')
                assert js("document.querySelector('.mc-memory-tabs [aria-current]').textContent==='Realm'")
                js("document.querySelector('.mc-memory-tabs a[href*=\"tab=app\"]').click();true")
                wait(lambda: js("document.querySelector('.mc-memory-tabs [aria-current]')?.textContent==='App'"), 'Memory defaults to Realm and opens App from its submenu')
                js("document.getElementById('mc-system-memory-open').click();true")
                assert js("!!document.querySelector('#mc-system-memory-dialog:modal')")
                assert js("document.querySelector('.mc-system-memory-text').textContent") == settings_text
                assert not js("!!document.querySelector('#mc-system-memory-dialog textarea, #mc-system-memory-dialog [contenteditable]')")
                result['checks'].append('Settings and Memory show the same read-only instructions')
                navigate('/inbox')
                selector = '[data-id='+json.dumps(item['id'])+'] [data-act=process]'
                click = 'document.querySelector('+json.dumps(selector)+').click();true'
                assert runner.run_inbox(root, recipient)['handled'] == 0 and not calls
                js(click)
                wait(lambda: js("!!document.querySelector('.mc-confirm-ov')&&document.querySelector('.mc-confirm-ov').textContent.includes('2099-11-09')&&document.querySelector('.mc-confirm-ov').textContent.includes('2099-11-10')"), 'Warning shows both original bounds')
                js("document.querySelector('[data-no]').click();true")
                assert inbox.has_mail(root, recipient) and not calls
                result['checks'].append('Cancel leaves future task pending without engine work')
                window.resize(1024, 900)
                js("document.documentElement.classList.add('armada-dark');document.body.classList.add('armada-dark')")
                js(click)
                wait(lambda: js("!!document.querySelector('.mc-confirm-ov')"), 'Warning can be reopened')
                capture('timed-inbox-warning-dark-1024', '.mc-confirm-ov')
                js("document.querySelector('[data-yes]').click();true")
                wait(lambda: bool(inbox._list(root, recipient, inbox.DONE)), 'Acknowledged timing override executes')
                assert len(calls) == 1 and calls[0]['inbox_timing_override']
                assert inbox._list(root, recipient, inbox.DONE)[0]['timing_override']['by'] == 'owner'
                result['checks'].append('One-time owner override is recorded with the result')
                result['ok'] = True
            except Exception:
                result['error'] = traceback.format_exc()
            finally:
                util.write_json_atomic(output, result)
                window.destroy()

        try:
            webview.start(exercise, gui='edgechromium', **app._webview_options())
        finally:
            server.shutdown(); server.server_close()
        return 0 if result['ok'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    raise SystemExit(run(parser.parse_args().output))
