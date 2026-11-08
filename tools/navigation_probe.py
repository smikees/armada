"""Synthetic native navigation feedback with a deliberately held page response."""
import argparse
import json
import os
import queue
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import traceback


def run(output, baseline=False):
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    output = output.resolve()
    with tempfile.TemporaryDirectory(prefix='armada-navigation-', ignore_cleanup_errors=True) as directory:
        home = Path(directory)
        for name in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA'):
            os.environ[name] = str(home / name)
            Path(os.environ[name]).mkdir()
        os.environ.update(ARMADA_DATA_DIR=str(home / 'account'), ARMADA_NO_MODEL_SYNC='1', ARMADA_NO_EXTERNAL_NOTIFY='1')
        import webview
        from armada import app, serve, local_auth, util
        from tests.golden_support import build_fixture
        realm = build_fixture(home / 'realm')
        entered, release = threading.Event(), threading.Event()
        observed, observations = threading.Event(), []
        result = {'ok': False, 'checks': [], 'baseline': baseline}

        class Fixture(serve.Handler):
            capture_html = ''
            def _route_get(self):
                path = self.path.split('?')[0]
                if path == '/probe-screenshot':
                    self._send(200, type(self).capture_html)
                elif path == '/probe-observation':
                    from urllib.parse import parse_qs, urlsplit
                    observations.append(json.loads(parse_qs(urlsplit(self.path).query)['data'][0]))
                    observed.set()
                    self._json(200, {'ok': True})
                elif path == '/probe-command':
                    self._json(200, bridge.next_command())
                elif baseline and path == '/static/js/navigation.js':
                    self._send(200, '// Baseline: controller disabled', 'application/javascript')
                elif path == '/artefacts' and 'probe_slow=1' in self.path:
                    entered.set()
                    if not release.wait(20):
                        self._send(503, 'Synthetic delay expired')
                        return
                    super()._route_get()
                elif path == '/api/providers':
                    self._json(200, {'providers': {p: {} for p in ('claude', 'codex', 'gemini')}, 'models': []})
                elif path.startswith('/api/') and path not in ('/api/font-size', '/api/thread-state'):
                    self._json(200, {})
                else:
                    super()._route_get()

            def _route_post(self):
                if self.path.split('?')[0] == '/api/probe-reply':
                    data = self._body()
                    bridge.reply(data['id'], data.get('value'), data.get('error'))
                    self._json(200, {'ok': True})
                else:
                    super()._route_post()

        Fixture.realm = realm
        server = serve._Server(('127.0.0.1', 0), Fixture)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{server.server_port}/'
        commands, replies, reply_lock = queue.Queue(), {}, threading.Lock()

        class Bridge:
            def next_command(self):
                try:
                    return commands.get_nowait()
                except queue.Empty:
                    return None

            def reply(self, identifier, value, error):
                with reply_lock:
                    item = replies.get(identifier)
                    if item:
                        item.update(value=value, error=error)
                        item['done'].set()

        bridge = Bridge()
        window = webview.create_window('Synthetic navigation', local_auth.browser_url(base, '/settings?tab=realm'),
                                       width=1280, height=850, hidden=True)
        bridge_script = """if(!window.probeBridge){window.probeBridge=true;let busy=false;
          setInterval(async()=>{if(busy)return;busy=true;try{const c=await (await fetch('/probe-command')).json();
            if(c){let value=null,error='';try{value=eval(c.code)??null;}catch(e){error=String(e);}
              await fetch('/api/probe-reply',{method:'POST',headers:{'Content-Type':'application/json'},
                body:JSON.stringify({id:c.id,value,error})});}}finally{busy=false;}},20);}true;"""
        window.events.loaded += lambda: app._browser_result(window, bridge_script)

        def js(code):
            # The existing page drives this test-only bridge, so commands do not
            # get queued for the destination document by ExecuteScriptAsync.
            identifier = str(time.monotonic_ns())
            item = {'done': threading.Event()}
            with reply_lock:
                replies[identifier] = item
            commands.put({'id': identifier, 'code': code})
            try:
                if not item['done'].wait(5):
                    raise TimeoutError('In-page probe command did not complete')
                if item.get('error'):
                    raise RuntimeError(item['error'])
                return item.get('value')
            finally:
                with reply_lock:
                    replies.pop(identifier, None)

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

        def navigate(path):
            window.load_url(local_auth.browser_url(base, path))
            wait(lambda: js('document.readyState==="complete"&&location.pathname==='+json.dumps(path.split('?')[0])), path)

        def delayed_click():
            entered.clear(); release.clear()
            observed.clear(); observations.clear()
            js("""window.probeStart=performance.now();window.probeFeedback=null;
                const observer=new MutationObserver(()=>{const p=document.querySelector('.mc-navigation-loading');
                  if(p&&!p.hidden){window.probeFeedback=performance.now()-window.probeStart;observer.disconnect();}});
                observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['hidden']});
                setTimeout(()=>fetch('/probe-observation?data='+encodeURIComponent(JSON.stringify({
                  visible:!!document.querySelector('.mc-navigation-loading:not([hidden])'),ms:window.probeFeedback}))),300);
                const a=document.querySelector('.mc-mainnav a[href*="/artefacts"]');
                const u=new URL(a.href);u.searchParams.set('probe_slow','1');a.href=u.href;a.click();true;""")
            assert entered.wait(5), 'Native navigation request started'

        def capture(name, width):
            chrome = Path(os.environ.get('PROGRAMFILES', 'C:/Program Files')) / 'Google/Chrome/Application/chrome.exe'
            assert chrome.is_file()
            Fixture.capture_html = js("(() => {const c=document.documentElement.cloneNode(true);c.querySelectorAll('script').forEach(s=>s.remove());return '<!doctype html>'+c.outerHTML;})()")
            path = output.with_name(name+'.png')
            subprocess.run([str(chrome), '--headless=new', '--disable-gpu', '--no-first-run', '--disable-background-networking',
                            '--disable-component-update', '--no-proxy-server', '--user-data-dir='+str(home / name),
                            '--virtual-time-budget=1000', f'--window-size={width},850', '--screenshot='+str(path),
                            local_auth.browser_url(base, '/probe-screenshot')], check=True, timeout=25,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
            result.setdefault('screenshots', []).append(str(path))

        def exercise():
            try:
                wait(lambda: js("document.readyState==='complete'&&!!document.getElementById('st-realmname')"), 'Settings ready')
                js("document.getElementById('st-realmname').value='Unsubmitted synthetic edit';document.querySelector('.mc-appscroll').scrollTop=280")
                delayed_click()
                assert observed.wait(5), 'Outgoing document observation received'
                visible = observations[-1]['visible']
                result['feedback_visible_while_response_held'] = visible
                result['feedback_dom_ms'] = observations[-1]['ms']
                if baseline:
                    assert not visible, 'Baseline unexpectedly has loading feedback'
                    release.set()
                    wait(lambda: js("location.pathname==='/artefacts'&&document.readyState==='complete'"), 'Baseline destination')
                else:
                    assert visible and result['feedback_dom_ms'] < 100, result
                    assert js("document.querySelector('.mc-mainnav a[href*=artefacts]').getAttribute('aria-current')==='page'"), 'Target tab selected'
                    assert js("document.querySelector('.mc-appscroll').inert&&getComputedStyle(document.querySelector('.mc-appscroll')).visibility==='hidden'"), 'Old content withheld'
                    result['checks'].append('Loading content and target tab appear under 100ms before the server responds')
                    capture('navigation-light', 1280)
                    js("document.body.classList.add('armada-dark')")
                    window.resize(1024, 850)
                    time.sleep(.2)
                    assert js("document.querySelector('.mc-navigation-loading').getBoundingClientRect().top>=document.querySelector('.mc-mainnav').getBoundingClientRect().bottom-1"), 'Menu remains uncovered'
                    capture('navigation-dark-1024', 1024)
                    wait(lambda: js("!document.querySelector('.mc-navigation-slow').hidden"), 'Slow-load recovery')
                    js("document.querySelector('.mc-navigation-stay').click();true")
                    assert js("document.querySelector('.mc-navigation-loading').hidden&&!document.querySelector('.mc-appscroll').inert&&document.getElementById('st-realmname').value==='Unsubmitted synthetic edit'"), 'Cancel preserves edits'
                    assert js("document.querySelector('.mc-appscroll').scrollTop>200&&document.querySelector('.mc-nav-action[href^=\"/settings\"]').getAttribute('aria-current')==='page'"), 'Cancel restores page and scroll'
                    result['checks'].append('Slow navigation can be stopped without losing fields, scroll or current tab')
                    release.set()
                    time.sleep(.3)
                    delayed_click()
                    js("document.querySelector('.mc-mainnav a[href^=\"/jobs\"]').click();true")
                    wait(lambda: js("location.pathname==='/jobs'&&document.readyState==='complete'"), 'Later menu wins')
                    release.set()
                    result['checks'].append('A second menu selection supersedes the delayed page')
                    navigate('/settings?tab=realm')
                    delayed_click(); release.set()
                    wait(lambda: js("location.pathname==='/artefacts'&&document.readyState==='complete'"), 'Artefacts completes')
                    assert js("!document.querySelector('.mc-navigation-loading:not([hidden])')"), 'Loaded page not obscured'
                    js('history.back();true')
                    wait(lambda: js("location.pathname==='/settings'&&document.readyState==='complete'&&!document.querySelector('.mc-navigation-loading:not([hidden])')"), 'Back restores page')
                    result['checks'].append('Successful navigation and browser Back leave no stale loading view')
                result['ok'] = True
            except Exception:
                result['error'] = traceback.format_exc()
            finally:
                release.set()
                util.write_json_atomic(output, result)
                window.destroy()

        webview.start(exercise, gui='edgechromium', debug=False, private_mode=False, storage_path=str(home / 'webview'))
        server.shutdown(); server.server_close()
        print(json.dumps(result, indent=2))
        return 0 if result['ok'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline', action='store_true')
    args = parser.parse_args()
    raise SystemExit(run(args.output, args.baseline))
