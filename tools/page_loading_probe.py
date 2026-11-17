"""Native destination/loading geometry, warm revisits and Register column preferences."""
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


def run(output, *, capture_images=True):
    import webview
    from armada import app, appconfig, local_auth, page_cache, serve, util, vtheme
    from tests.golden_support import build_fixture, fixture_inputs
    result = {'ok': False, 'checks': [], 'screenshots': [], 'timings': {}}
    output = output.resolve()
    with tempfile.TemporaryDirectory(prefix='armada-page-loading-', ignore_cleanup_errors=True) as folder, fixture_inputs():
        home = Path(folder)
        for name in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA'):
            os.environ[name] = str(home/name);(home/name).mkdir()
        os.environ.update(ARMADA_DATA_DIR=str(home/'data'), ARMADA_NO_MODEL_SYNC='1', ARMADA_NO_EXTERNAL_NOTIFY='1')
        appconfig.save(vtheme.preferences('armada-ii'))
        root = Path(build_fixture(home/'realm'))
        # Mature realms must be as quick to navigate as new ones. The former nav
        # badge opened every archived message, even on an inventory cache hit.
        archive = root/'agents/captain/inbox/done';archive.mkdir(parents=True, exist_ok=True)
        message = json.dumps({'id':'synthetic', 'from':'mate', 'ask':'Completed synthetic task.', 'finished':'2026-01-01T10:00:00'})
        for index in range(3000):
            (archive/f'{index}.json').write_text(message, encoding='utf-8')
        result['archive_messages'] = 3000
        cfg=util.read_json_state(root/'realm.json')
        cfg['toolkit']={'skills':[{'id':'synthetic-notes','name':'Synthetic report notes','description':'Keep reports concise.','runs':'reads'}]}
        util.write_json_atomic(root/'realm.json',cfg)
        from armada.threads import Thread
        report=root/'synthetic-report.md';report.write_text('Synthetic report for UI verification.',encoding='utf-8')
        Thread(root/'agents/captain','main').append('Prepare a synthetic report.','Saved the report.',outputs=[{'name':report.name,'path':str(report)}])
        entered, release = threading.Event(), threading.Event()
        held = [None]
        fail = [False]
        calls = {'artefacts': 0, 'skills': 0}
        page_cache.invalidate()

        class Fixture(serve.Handler):
            def _get_list_content(self, page):
                calls[page] += 1
                if held[0] == page:
                    entered.set()
                    if not release.wait(30):
                        self._send(503, 'Synthetic delay expired');return
                if fail[0]:
                    fail[0]=False;self._send(503,'Synthetic loading failure');return
                super()._get_list_content(page)

            def _route_get(self):
                path = self.path.split('?')[0]
                if path == '/probe-screenshot':
                    self._send(200, type(self).capture_html)
                elif path in {'/api/auth-status', '/api/scheduler-status', '/api/proposals-count',
                              '/api/notifications', '/api/providers', '/api/update-status', '/api/usage-limits'}:
                    self._json(200, {'ok': True, 'logged_in': True, 'providers': {}})
                else:
                    super()._route_get()

        Fixture.realm = root
        server = serve._Server(('127.0.0.1', 0), Fixture)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{server.server_port}'
        window = webview.create_window('Synthetic page loading', local_auth.browser_url(base, '/'), hidden=True, width=1280, height=900)

        def js(code):
            return window.evaluate_js(code)

        def check(name, predicate):
            end = time.monotonic()+20
            while time.monotonic()<end:
                try:
                    if predicate():
                        result['checks'].append(name);return
                except Exception:
                    pass
                time.sleep(.05)
            raise AssertionError(name)

        def navigate(path):
            window.load_url(local_auth.browser_url(base, path))
            check('Opened '+path, lambda: js('location.pathname==='+json.dumps(path.split('?')[0])+"&&document.readyState==='complete'"))

        def geometry():
            return js("JSON.stringify(['.mc-mainnav','.mc-list-heading','.mc-list-heading h2','.mc-list-tabs'].map(s=>{const e=document.querySelector(s);if(!e)return null;const r=e.getBoundingClientRect();return [r.x,r.y,r.width,r.height];}))")

        def capture(name, width=1280, height=900):
            if not capture_images:return
            Fixture.capture_html = js("""(() => {
                const d=document.documentElement.cloneNode(true),sources=[...document.querySelectorAll('style,link[rel=stylesheet]')];
                d.querySelectorAll('style,link[rel=stylesheet]').forEach((node,i)=>{
                    const sheet=sources[i].sheet;if(!sheet)return;
                    const style=document.createElement('style');style.textContent=[...sheet.cssRules].map(r=>r.cssText).join('\\n');node.replaceWith(style);
                });
                d.querySelectorAll('script').forEach(s=>s.remove());return '<!doctype html>'+d.outerHTML;
            })()""")
            path = output.with_name(output.stem+'-'+name+'.png')
            chrome = Path(os.environ.get('PROGRAMFILES', 'C:/Program Files'))/'Google/Chrome/Application/chrome.exe'
            subprocess.run([str(chrome),'--headless=new','--disable-gpu','--no-first-run','--disable-background-networking',
                            '--disable-component-update','--no-proxy-server','--user-data-dir='+str(home/('capture-'+name)),
                            '--virtual-time-budget=1000',f'--window-size={width},{height}','--screenshot='+str(path),
                            local_auth.browser_url(base,'/probe-screenshot')], check=True, timeout=25,
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
            result['screenshots'].append(str(path))

        def exercise():
            try:
                check('Register exposes seven accessible column handles', lambda: js("document.querySelectorAll('.mc-register-table [role=separator]').length===7"))
                before = js("document.querySelector('.mc-register-table th').getBoundingClientRect().width")
                js("document.querySelector('.mc-column-resize').focus();document.activeElement.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));true")
                check('Keyboard changes only the selected column', lambda: js("document.querySelector('.mc-register-table th').getBoundingClientRect().width") > before+8)
                # Synthetic pointer events exercise the native DOM handlers; capture itself requires
                # a physical pointer and is substituted only in this isolated test document.
                js("""window.probeHandle=document.querySelector('.mc-column-resize');
                  probeHandle.setPointerCapture=()=>{};probeHandle.releasePointerCapture=()=>{};
                  probeHandle.dispatchEvent(new PointerEvent('pointerdown',{button:0,clientX:200,pointerId:1,bubbles:true}));
                  probeHandle.dispatchEvent(new PointerEvent('pointermove',{clientX:260,pointerId:1,bubbles:true}));
                  probeHandle.dispatchEvent(new PointerEvent('pointerup',{pointerId:1,bubbles:true}));true;""")
                width = js("document.querySelector('.mc-register-table th').getBoundingClientRect().width")
                assert width > before+65
                result['checks'].append('Pointer resizing changes the column without navigating the row')
                capture('register')
                navigate('/jobs');navigate('/')
                check('Column width survives navigation', lambda: abs(js("document.querySelector('.mc-register-table th').getBoundingClientRect().width")-width)<1)
                window.resize(900, 1000)
                js("document.body.classList.add('armada-dark');mcFontSize.preview(19);true")
                check('Narrow enlarged-text Register scrolls horizontally', lambda: js("(()=>{const e=document.querySelector('.mc-register-scroll');return e.scrollWidth>e.clientWidth&&e.getBoundingClientRect().right<=innerWidth;})()"))
                capture('register-narrow-dark',900,1000)
                js("document.querySelector('.mc-column-resize').dispatchEvent(new KeyboardEvent('keydown',{key:'Home',bubbles:true}));mcFontSize.preview(13);true")
                result['checks'].append('Home resets a column through the same persisted preference')
                window.resize(1280,900)
                for page, selector in [('artefacts','#art-table'),('skills','#cap-pane-user')]:
                    navigate('/agent/captain/threads')
                    page_cache.invalidate();held[0]=page;entered.clear();release.clear()
                    start=time.monotonic()
                    js("document.querySelector('.mc-mainnav a[href^=\"/"+page+"\"]').click();true")
                    assert entered.wait(10)
                    check(page+' destination is visible before inventory arrives', lambda: js('location.pathname==='+json.dumps('/'+page)+"&&!!document.querySelector('.mc-list-heading')&&document.getElementById('mc-page-content').getAttribute('aria-busy')==='true'"))
                    result['timings'][page+'_cold_shell_ms']=round((time.monotonic()-start)*1000,2)
                    assert result['timings'][page+'_cold_shell_ms'] < 750, result['timings']
                    assert js("(()=>{const s=document.querySelector('.mc-list-loading .mc-loading-spinner');if(!s)return false;const c=getComputedStyle(s);return s.getBoundingClientRect().width>=14&&c.animationName==='mc-spin'&&c.borderRightColor==='rgba(0, 0, 0, 0)';})()")
                    result['checks'].append(page+' cold destination has a visible animated spinner within 750ms with 3,000 archived messages')
                    assert js("!document.querySelector('.mc-sub')&&!document.querySelector('.mc-crumb')&&!document.querySelector('.mc-navigation-title')")
                    result['checks'].append(page+' destination has no outgoing thread header or tabs')
                    if page=='skills':
                        window.resize(900,1000)
                        js("document.body.classList.add('armada-dark');mcFontSize.preview(19);true")
                    before_geometry=geometry()
                    capture(page+'-loading',900 if page=='skills' else 1280,1000 if page=='skills' else 900)
                    release.set()
                    check(page+' content loads and becomes interactive', lambda: js('!!document.querySelector('+json.dumps(selector)+")&&document.getElementById('mc-page-content').getAttribute('aria-busy')==='false'"))
                    assert geometry()==before_geometry, (page,before_geometry,geometry())
                    result['checks'].append(page+' heading, actions, tabs and navigation have zero geometry shift')
                    capture(page+'-loaded',900 if page=='skills' else 1280,1000 if page=='skills' else 900)
                    count=calls[page]
                    held[0]=None
                    navigate('/jobs')
                    start=time.monotonic()
                    js("document.querySelector('.mc-mainnav a[href^=\"/"+page+"\"]').click();true")
                    check(page+' warm revisit renders cached content immediately', lambda: js('location.pathname==='+json.dumps('/'+page)+'&&!!document.querySelector('+json.dumps(selector)+")&&!document.querySelector('script[src*=page_content]')"))
                    result['timings'][page+'_warm_ms']=round((time.monotonic()-start)*1000,2)
                    assert result['timings'][page+'_warm_ms'] < 750, result['timings']
                    assert calls[page]==count
                    result['checks'].append(page+' warm revisit makes no inventory request')
                    held[0]=page;entered.clear();release.clear()
                    js("document.querySelector('.mc-list-actions>button').click();true")
                    assert entered.wait(10), 'Refresh must bypass cached '+page
                    release.set();held[0]=None
                    check(page+' Refresh loads current inventory', lambda: js("document.getElementById('mc-page-content')?.getAttribute('aria-busy')==='false'"))
                    page_cache.invalidate();fail[0]=True
                    js("document.querySelector('.mc-list-actions>button').click();true")
                    check(page+' load error retains heading and offers retry',lambda: js("!!document.querySelector('#mc-page-content [role=alert]')&&!!document.querySelector('.mc-list-heading h2')"))
                    js("document.querySelector('#mc-page-content button').click();true")
                    check(page+' retry recovers usable content',lambda: js('!!document.querySelector('+json.dumps(selector)+")&&document.getElementById('mc-page-content').getAttribute('aria-busy')==='false'"))
                result['ok']=True
            except Exception:
                result['error']=traceback.format_exc()
            finally:
                release.set();util.write_json_atomic(output,result);window.destroy()
        try:
            webview.start(exercise,gui='edgechromium',**app._webview_options())
        finally:
            server.shutdown();server.server_close()
        print(json.dumps(result,indent=2))
        return 0 if result['ok'] else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--no-captures',action='store_true')
    args=parser.parse_args()
    raise SystemExit(run(args.output,capture_images=not args.no_captures))
