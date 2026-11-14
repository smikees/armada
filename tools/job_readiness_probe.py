"""Hidden WebView2 journey for outage controls; synthetic realm and credentials only."""
import argparse
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import threading
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run(output):
    import webview
    from armada import app, local_auth, serve, util, run_policy, capabilities, connector_health
    from tests.golden_support import build_fixture, fixture_inputs
    result = {'ok': False, 'checks': []}
    with tempfile.TemporaryDirectory(prefix='armada-job-readiness-', ignore_cleanup_errors=True) as folder, fixture_inputs():
        home = Path(folder)
        os.environ.update(HOME=str(home/'home'), USERPROFILE=str(home/'home'),
            ARMADA_DATA_DIR=str(home/'data'), ARMADA_NO_MODEL_SYNC='1', ARMADA_NO_EXTERNAL_NOTIFY='1')
        (home/'home').mkdir()
        realm = Path(build_fixture(home/'realm'))
        config = util.read_json_state(realm/'realm.json')
        config.setdefault('toolkit', {})['connectors'] = [{'id':'broker','name':'Synthetic broker','mcp_url':'https://broker.example/mcp'}]
        util.write_json_atomic(realm/'realm.json', config)
        capabilities.grant(realm,'captain','broker')
        # This journey must never contact a real provider.
        connector_health.probe = lambda root, provider, ids: {cid: {'id':cid, 'name':'Synthetic broker',
            'provider':provider, 'state':'up', 'reason':'Synthetic check passed', 'links':{}} for cid in ids}
        for jid in ('read','desk'):
            job = {'id':jid,'kind':'agent','name':jid.title(),'prompt':'Never execute this fixture.',
                   'allow_tools':False,'schedule':'daily 16:00'}
            util.write_json_atomic(realm/f'agents/captain/jobs/{jid}.json',job)
            run_policy.seal_job(realm,'captain',job)

        class Fixture(serve.Handler):
            def _route_get(self):
                path = self.path.split('?')[0]
                if path == '/probe-screenshot':
                    self._send(200, type(self).capture_html)
                elif path in {'/api/auth-status','/api/scheduler-status','/api/proposals-count',
                    '/api/notifications','/api/providers','/api/update-status','/api/usage-limits'}:
                    self._json(200, {'ok':True,'logged_in':True,'providers':{}})
                elif path == '/api/capability-connections':
                    self._json(200, {'pending':False,'providers':{},'connectors':{}})
                else:
                    super()._route_get()
        Fixture.realm = realm
        server = serve._Server(('127.0.0.1',0),Fixture)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        base = f'http://127.0.0.1:{server.server_port}/'
        window = webview.create_window('Synthetic job recovery controls',
            local_auth.browser_url(base,'/job/captain/desk'),hidden=True,width=1200,height=1000)
        def js(code):
            return window.evaluate_js(code)
        def capture():
            # Frozen native DOM, rendered offline against the same fixture assets.
            Fixture.capture_html = js("(() => {const copy=document.documentElement.cloneNode(true);copy.querySelectorAll('script').forEach(s=>s.remove());copy.querySelectorAll('details').forEach(s=>s.open=true);return '<!doctype html>'+copy.outerHTML;})()")
            Fixture.capture_html += "<script>addEventListener('load',()=>document.getElementById('j-start-deadline').closest('details').scrollIntoView({block:'start'}))</script>"
            path = output.with_suffix('.png')
            chrome = Path(os.environ.get('PROGRAMFILES', 'C:/Program Files'))/'Google/Chrome/Application/chrome.exe'
            subprocess.run([str(chrome), '--headless=new', '--disable-gpu', '--no-first-run',
                '--disable-background-networking', '--disable-component-update', '--no-proxy-server',
                '--user-data-dir='+str(home/'capture-browser'), '--virtual-time-budget=1500',
                '--window-size=1200,1100', '--screenshot='+str(path),
                local_auth.browser_url(base, '/probe-screenshot')], check=True, timeout=30,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
            assert path.is_file() and path.stat().st_size > 1000
            result['screenshot'] = str(path)
        def check(label, predicate):
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                try:
                    if predicate():
                        result['checks'].append(label)
                        return
                except Exception:
                    pass
                time.sleep(.1)
            raise AssertionError(label)
        def exercise():
            try:
                check('Job start controls load',lambda:js("typeof mcJobReadiness==='function'&&typeof mcSaveJob==='function'&&document.readyState==='complete'"))
                path=realm/'agents/captain/jobs/desk.json'
                assert 'daily 16:00' in js("document.getElementById('j-next').textContent")
                js("document.getElementById('j-critical').checked=true;mcSaveJob('captain','desk');true")
                check('Critical-only edit finishes saving',lambda:'saved' in js("document.getElementById('j-savemsg').textContent"))
                assert util.read_json_state(path)['schedule']=='daily 16:00'
                assert 'cron' not in util.read_json_state(path)
                assert run_policy.verify_job(realm,'captain',util.read_json_state(path))
                result['checks'].append('Untouched legacy schedule and approval survive Critical edit')
                js("mcPreset('weekdays');mcSaveJob('captain','desk');true")
                check('Explicit schedule change is disclosed',lambda:'Schedule changed: daily 16:00' in js("document.getElementById('j-savemsg').textContent"))
                assert util.read_json_state(path)['cron']=='0 9 * * 1,2,3,4,5'
                js("document.getElementById('j-start-deadline').closest('details').open=true;document.getElementById('j-window-from').value='16:30';document.getElementById('j-window-until').value='18:30';document.querySelector('[data-required-connector]').checked=true;document.getElementById('j-dependencies').append(document.getElementById('j-dependency-template').content.cloneNode(true));document.querySelector('#j-dependencies [data-job]').value='captain/read';document.getElementById('j-coordinator-start').checked=true;mcSaveJob('captain','desk');true")
                path=realm/'agents/captain/jobs/desk.json'
                check('Owner saves window, connectors and dependency',lambda:util.read_json_state(path).get('after'))
                saved=util.read_json_state(path)
                assert saved['start_window']=={'from':'16:30','until':'18:30'}
                assert saved['requires_connectors']==['broker'] and saved['coordinator_may_start']
                assert run_policy.verify_job(realm,'captain',saved)
                result['checks'].append('Saved controls carry owner approval')
                window.load_url(local_auth.browser_url(base,'/job/captain/desk'))
                check('Saved values survive reload',lambda:js("typeof mcSaveJob==='function'&&document.readyState==='complete'&&document.getElementById('j-window-until')?.value==='18:30'&&document.querySelector('#j-dependencies [data-job]')?.value==='captain/read'"))
                js("document.getElementById('j-start-deadline').closest('details').open=true;true")
                check('Expanded controls fit their panel',lambda:js("(() => {const panel=document.getElementById('j-start-deadline').closest('details'),box=panel.getBoundingClientRect();return [...panel.querySelectorAll('input,select,button')].every(el=>{const r=el.getBoundingClientRect();return r.left>=box.left-1&&r.right<=box.right+1;});})()"))
                capture()
                js("document.getElementById('j-window-from').value='';mcSaveJob('captain','desk');true")
                check('Incomplete window keeps prior saved job',lambda:'both' in js("document.getElementById('j-savemsg').textContent"))
                assert util.read_json_state(path)['start_window']['from']=='16:30'
                window.load_url(local_auth.browser_url(base,'/skills'))
                check('Monitoring modal is available',lambda:js("typeof mcSaveWatches==='function'&&!!document.getElementById('connector-watch-dialog')"))
                js("document.getElementById('connector-watch-dialog').showModal();document.querySelector('[data-watch][value=broker]').checked=true;mcSaveWatches(document.querySelector('#connector-watch-dialog .btn-primary'));true")
                from armada import connector_health, command_secrets
                check('Watch settings save without a model call',lambda:'broker' in connector_health.settings(realm).get('watched',[]))
                js("mcCheckHealth(document.querySelector('#connector-watch-dialog [onclick=\"mcCheckHealth(this)\"]'));true")
                check('On-demand heartbeat is recorded even outside weekday watch hours',lambda:(realm/'connector-health.json').exists())
                check('On-demand check gives visible feedback',lambda:'Check requested' in js("document.querySelector('#connector-watch-dialog [data-feedback]').textContent"))
                original = util.read_json_state(realm/'agents/captain/jobs/read.json')
                util.write_json_atomic(realm/'agents/captain/jobs/_pending/read.json', {**original, 'timeout':1234, 'prompt':'Proposed replacement prompt.'})
                window.load_url(local_auth.browser_url(base,'/jobs'))
                check('Change proposal displays every changed field',lambda:js("!!document.querySelector('.mc-propdiff')&&document.querySelector('.mc-propdiff').textContent.includes('timeout')&&document.querySelector('.mc-propdiff').textContent.includes('Proposed replacement prompt.')"))
                assert util.read_json_state(realm/'agents/captain/jobs/read.json') == original
                assert run_policy.verify_job(realm,'captain',original)
                result['checks'].append('Pending change leaves the approved job intact')
                js("document.querySelector('.mc-propdiff').closest('.mc-prop').querySelector('.mc-propapprove').click();true")
                check('Reviewed change replaces and reseals the job',lambda:util.read_json_state(realm/'agents/captain/jobs/read.json').get('timeout')==1234)
                assert run_policy.verify_job(realm,'captain',util.read_json_state(realm/'agents/captain/jobs/read.json'))
                assert not (realm/'agents/captain/jobs/_pending/read.json').exists()
                window.load_url(local_auth.browser_url(base,'/settings?tab=app'))
                check('Command credentials modal is available',lambda:js("typeof mcSaveCommandSecret==='function'&&!!document.getElementById('command-secret-dialog')"))
                js("document.getElementById('command-secret-dialog').showModal();document.getElementById('command-secret-name').value='synthetic';document.getElementById('command-secret-value').value='synthetic-probe-secret';mcSaveCommandSecret(document.querySelector('#command-secret-dialog .btn-primary'),false);true")
                check('Credential save returns only its name',lambda:command_secrets.names(realm)==['synthetic'])
                assert js("document.getElementById('command-secret-value').value")==''
                assert 'synthetic-probe-secret' not in command_secrets._path().read_text()
                assert all(b'synthetic-probe-secret' not in p.read_bytes() for p in realm.rglob('*') if p.is_file())
                result['checks'].append('Credential cleared from form and absent from realm and plaintext store')
                result['ok']=True
            except Exception:
                result['error']=traceback.format_exc()
            finally:
                util.write_json_atomic(output,result)
                window.destroy()
        try:
            webview.start(exercise,gui='edgechromium',**app._webview_options())
        finally:
            server.shutdown();server.server_close()
    return 0 if result['ok'] else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    raise SystemExit(run(parser.parse_args().output.resolve()))
