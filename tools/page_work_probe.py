"""Hidden WebView2 resource/state probe using synthetic pages, no providers or live realm."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import traceback


def run(output, measure_only=False, captures=False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    with tempfile.TemporaryDirectory(prefix='armada-page-work-', ignore_cleanup_errors=True) as folder:
        home = Path(folder)
        for name in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA'):
            os.environ[name] = str(home / name)
            Path(os.environ[name]).mkdir()
        os.environ['ARMADA_DATA_DIR'] = str(home / 'account')
        os.environ['ARMADA_NO_MODEL_SYNC'] = '1'
        os.environ['ARMADA_NO_EXTERNAL_NOTIFY'] = '1'
        import webview
        from armada import app, serve, local_auth, util, execution_admission
        from tests.golden_support import build_fixture
        execution_admission._directory = lambda: home / 'account/execution'
        realm = build_fixture(home / 'realm')
        util.write_json_atomic(Path(realm) / 'agents/captain/jobs/synthetic-daily.json',
                               {'id': 'synthetic-daily', 'name': 'Synthetic daily review',
                                'schedule': 'manual', 'kind': 'agent', 'enabled': False,
                                'prompt': 'Synthetic fixture. Never execute.'})
        requests = []

        class Fixture(serve.Handler):
            capture_html = ''
            def _route_get(self):
                path = self.path.split('?')[0]
                requests.append(path)
                if path == '/probe-screenshot':
                    self._send(200, type(self).capture_html)
                elif path == '/api/providers':
                    self._json(200, {'providers': {p: {} for p in ('claude','codex','gemini')}, 'models': []})
                elif path.startswith('/api/') and path not in ('/api/font-size', '/api/thread-state'):
                    self._json(200, {})
                else:
                    super()._route_get()

        Fixture.realm = realm
        server = serve._Server(('127.0.0.1', 0), Fixture)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{server.server_port}/'
        window = webview.create_window('Synthetic page work', local_auth.browser_url(base, '/settings?tab=realm'),
                                       width=1280, height=850, hidden=True)
        loaded = threading.Event()
        window.events.loaded += lambda: loaded.set()
        result = {'ok': False, 'checks': [], 'measurements': {}}

        def js(script):
            return app._browser_result(window, script, timeout=5)

        def wait(predicate, label):
            end = time.monotonic() + 15
            while time.monotonic() < end:
                try:
                    if predicate():
                        return
                except Exception:
                    pass
                time.sleep(.05)
            raise AssertionError(label)

        def measure(name):
            data = js("JSON.stringify({resources:performance.getEntriesByType('resource').map(r=>({path:new URL(r.name).pathname,bytes:r.transferSize,duration:r.duration})),dom:document.querySelectorAll('*').length,ready:performance.getEntriesByType('navigation')[0]?.domContentLoadedEventEnd})")
            result['measurements'][name] = json.loads(data) if isinstance(data, str) else data

        def navigate(path):
            loaded.clear()
            window.load_url(local_auth.browser_url(base, path))
            assert loaded.wait(15), path
            wait(lambda: js("document.readyState==='complete'&&location.pathname==="+json.dumps(path.split('?')[0])), path)

        def capture(name):
            import subprocess
            chrome = Path(os.environ.get('PROGRAMFILES', 'C:/Program Files')) / 'Google/Chrome/Application/chrome.exe'
            assert chrome.is_file(), 'Chrome required for requested visual captures'
            Fixture.capture_html = js("(() => {const copy=document.documentElement.cloneNode(true);copy.querySelectorAll('script').forEach(s=>s.remove());return '<!doctype html>'+copy.outerHTML;})()")
            path = output.with_name(name+'.png').resolve()
            subprocess.run([str(chrome), '--headless=new', '--disable-gpu', '--no-first-run',
                            '--disable-background-networking', '--disable-component-update', '--no-proxy-server',
                            '--user-data-dir='+str(home / ('chrome-'+name)), '--virtual-time-budget=1500',
                            '--window-size=1280,850', '--screenshot='+str(path),
                            local_auth.browser_url(base, '/probe-screenshot')], check=True, timeout=30,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
            assert path.is_file() and path.stat().st_size > 1000
            result.setdefault('screenshots', []).append(str(path))
            result['screenshot_renderer'] = 'Headless Chromium rendering native WebView2 DOM'

        def exercise():
            try:
                wait(lambda: js("document.readyState==='complete'&&!!document.getElementById('st-realm-pane')"), 'Settings ready')
                time.sleep(.6)
                measure('settings_realm')
                if not measure_only:
                    assert js("document.getElementById('mc-changelog').querySelectorAll('li').length===0"), 'Closed changelog is inert'
                    js("mcChangelog(true)")
                    assert js("document.getElementById('mc-changelog').querySelectorAll('li').length>100"), 'Changelog available on demand'
                    js("mcChangelog(false);mcSetTab('user');mcUserAvatarModal(true)")
                    assert js("document.querySelectorAll('#us-avatar-modal img').length>0"), 'Avatar choices hydrate'
                    js("mcUserAvatarModal(false);mcSetTab('realm');document.getElementById('st-realmname').focus();document.querySelector('.mc-appscroll').scrollTop=300")
                    result['checks'].append('Closed dialogs defer content and hydrate on demand')
                navigate('/')
                time.sleep(.6)
                measure('overview')
                js("const n=document.createElement('span');n.className='mc-math';n.dataset.tex='x^2';n.textContent='x^2';document.body.append(n)")
                wait(lambda: js("!!document.querySelector('.mc-math .katex')"), 'Dynamic formula renders')
                measure('formula')
                result['checks'].append('Dynamically inserted formula renders with local assets')
                if not measure_only:
                    for name in ('settings_realm', 'overview'):
                        assert not any('/vendor/katex/' in r['path'] for r in result['measurements'][name]['resources']), name
                    result['checks'].append('Pages without formulas load no KaTeX assets')
                    navigate('/settings?tab=realm')
                    wait(lambda: js("document.getElementById('st-tab-realm').getAttribute('aria-selected')==='true'&&document.activeElement.id==='st-realmname'&&document.querySelector('.mc-appscroll').scrollTop>200"), 'Settings tab, focus and scroll restore')
                    result['checks'].append('Settings tab, focus and scroll survive navigation')
                    navigate('/jobs')
                    js("const input=document.getElementById('jf-search');input.value='daily';input.focus();mcJobsFilter();const row=document.querySelector('#jf-status [data-val]:not([data-val=\"\"])');if(row)row.click();window.probeFilter=document.getElementById('jf-status').dataset.val")
                    choice = js('window.probeFilter')
                    navigate('/')
                    navigate('/jobs')
                    wait(lambda: js("document.getElementById('jf-search').value==='daily'&&document.getElementById('jf-status').dataset.val==="+json.dumps(choice)), 'Job filters restored')
                    result['checks'].append('Job search and status filter survive navigation')
                    navigate('/agent/captain/threads')
                    wait(lambda: js("!!document.getElementById('mc-msg')"), 'Conversation loaded')
                    js("const input=document.getElementById('mc-msg');input.value='Synthetic unsent draft';input.dispatchEvent(new Event('input',{bubbles:true}));input.focus()")
                    navigate('/')
                    navigate('/agent/captain/threads')
                    wait(lambda: js("document.getElementById('mc-msg').value==='Synthetic unsent draft'"), 'Draft preserved')
                    result['checks'].append('Unsent conversation draft survives navigation without submission')
                    if captures:
                        navigate('/settings?tab=realm')
                        js("document.documentElement.classList.remove('armada-dark')")
                        capture('m10-settings-light')
                        js("document.documentElement.classList.add('armada-dark');mcChangelog(true)")
                        capture('m10-changelog-dark')
                result['requests'] = requests[:]
                result['ok'] = True
            except Exception:
                result['error'] = traceback.format_exc()
                result['view_state'] = js("JSON.stringify({path:location.pathname,query:location.search,focus:document.activeElement?.id,tab:document.querySelector('[role=tab][aria-selected=true]')?.id,scroll:document.querySelector('.mc-appscroll')?.scrollTop,stored:sessionStorage.getItem('armada-view-state')})")
            finally:
                util.write_text_atomic(output, json.dumps(result, indent=2))
                window.destroy()

        try:
            webview.start(exercise, gui='edgechromium', **app._webview_options())
        finally:
            server.shutdown()
            server.server_close()
        return 0 if result['ok'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--measure-only', action='store_true')
    parser.add_argument('--captures', action='store_true')
    args = parser.parse_args()
    raise SystemExit(run(args.output, args.measure_only, args.captures))
