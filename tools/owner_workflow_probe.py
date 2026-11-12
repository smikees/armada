"""Synthetic native owner journeys: keyboard safety, policy previews and scaled layouts."""
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
    with tempfile.TemporaryDirectory(prefix='armada-owner-workflow-', ignore_cleanup_errors=True) as directory:
        home = Path(directory)
        for name in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA'):
            os.environ[name] = str(home / name)
            Path(os.environ[name]).mkdir()
        os.environ['ARMADA_DATA_DIR'] = str(home / 'account')
        os.environ['ARMADA_NO_MODEL_SYNC'] = '1'
        os.environ['ARMADA_NO_EXTERNAL_NOTIFY'] = '1'
        import webview
        from armada import app, serve, local_auth, util, jobs
        from tests.golden_support import build_fixture
        root = Path(build_fixture(home / 'realm'))
        cfg = util.read_json_state(root / 'realm.json')
        cfg.setdefault('toolkit', {})['connectors'] = [{'id': 'ibkr', 'name': 'Synthetic brokerage',
            'tool_names': ['get_balance', 'submit_order', 'create_order_instruction']}]
        cfg.update(tool_policy={'ibkr': {'deny': ['*order*']}}, read_only=['skills/**'])
        util.write_json_atomic(root / 'realm.json', cfg)
        agent_path = root / 'agents/captain/agent.json'
        agent = util.read_json_state(agent_path)
        agent.setdefault('toolkit', {})['connectors'] = [{'id': 'ibkr'}]
        agent.update(tool_policy={'ibkr': {'allow': ['get_*'], 'deny': ['submit_*']}}, write_scope=['agents/captain/**'])
        util.write_json_atomic(agent_path, agent)
        util.write_json_atomic(root / 'agents/captain/jobs' / jobs.PENDING / 'synthetic-review.json',
                               {'id': 'synthetic-review', 'name': 'Synthetic review', 'kind': 'agent',
                                'schedule': 'manual', 'prompt': 'Never execute this fixture.', 'enabled': False})
        before = agent_path.read_bytes(), (root / 'realm.json').read_bytes()
        entered, release = threading.Event(), threading.Event()
        activity_entered,activity_release=threading.Event(),threading.Event()

        class Fixture(serve.Handler):
            capture_html = ''
            delay_layout = False
            reject_layout = False
            saves = []
            activity_reads = 0
            reject_activity = False
            delay_activity = False

            def _send(self,code,body,ctype='text/html; charset=utf-8',cache='',csp=''):
                if isinstance(body,str) and '<head>' in body:
                    # Observe the real registered timer and advance it without
                    # making a native probe wait five wall-clock minutes.
                    body=body.replace('<head>',"<head><script>window.__probeIntervals=[];const nativeInterval=window.setInterval.bind(window);window.setInterval=(fn,delay,...args)=>{window.__probeIntervals.push({fn,delay});return nativeInterval(fn,delay,...args);};</script>",1)
                super()._send(code,body,ctype,cache,csp)

            def _get_activity_monitor(self):
                type(self).activity_reads+=1
                if type(self).delay_activity:
                    type(self).delay_activity=False
                    activity_entered.set()
                    if not activity_release.wait(10):
                        self._json(503,{'error':'Synthetic delay expired'})
                        return
                if type(self).reject_activity:
                    self._json(503,{'error':'Synthetic refresh refused'})
                else:
                    super()._get_activity_monitor()

            def _route_get(self):
                path = self.path.split('?')[0]
                if path == '/probe-screenshot':
                    self._send(200, type(self).capture_html)
                elif path == '/api/providers':
                    self._json(200, {'providers': {p: {} for p in ('claude', 'codex', 'gemini')}, 'models': []})
                elif path == '/api/usage-limits':
                    self._json(200,{'available':False,'connected':True,'message':'Synthetic provider has not supplied a reading.'})
                elif path.startswith('/api/') and path not in ('/api/font-size', '/api/thread-state','/api/activity-monitor','/api/agent-activity'):
                    self._json(200, {})
                else:
                    super()._route_get()

            def _save_dashboard(self, body):
                if type(self).delay_layout:
                    type(self).delay_layout = False
                    entered.set()
                    if not release.wait(10):
                        return {'ok': False, 'error': 'Synthetic delay expired'}
                if type(self).reject_layout:
                    return {'ok': False, 'error': 'Synthetic save refused'}
                type(self).saves.append(body.get('heights', {}).get('register'))
                return super()._save_dashboard(body)

        Fixture.realm = str(root)
        server = serve._Server(('127.0.0.1', 0), Fixture)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{server.server_port}/'
        window = webview.create_window('Synthetic owner workflows', local_auth.browser_url(base), width=1024, height=900, hidden=True)
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

        def capture(name, focus=None):
            chrome = Path(os.environ.get('PROGRAMFILES', 'C:/Program Files')) / 'Google/Chrome/Application/chrome.exe'
            Fixture.capture_html = js("(() => {const copy=document.documentElement.cloneNode(true);copy.querySelectorAll('script').forEach(s=>s.remove());document.querySelectorAll('textarea').forEach((el,i)=>copy.querySelectorAll('textarea')[i].textContent=el.value);return '<!doctype html>'+copy.outerHTML;})()")
            if focus:
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
            result['screenshot_renderer'] = 'Headless Chromium rendering native DOM at its logical viewport size'

        def exercise():
            try:
                wait(lambda: js("document.readyState==='complete'&&typeof mcConfirm==='function'&&!!document.getElementById('mc-grid')"), 'Overview ready')
                wait(lambda: js("document.querySelector('.mc-attention-summary').textContent.includes('job proposals')"), 'Attention links pending review')
                wait(lambda: js("!!document.querySelector('.mc-w[data-id=activity] [data-activity-monitor]')&&!document.querySelector('#mc-ovh .mc-attention-summary')"),'Activity monitor owns attention outside the header')
                wait(lambda: js("document.querySelectorAll('#mc-hdr-limits .mc-limit-unavailable').length===6&&[...document.querySelectorAll('#mc-hdr-limits .mc-limit-unavailable')].every(el=>el.textContent==='Not reported')"),'Missing subscription readings keep Not reported in every row')
                assert js("[...document.querySelectorAll('#mc-hdr-limits .mc-limit-bar')].every(el=>getComputedStyle(el).borderTopStyle==='dashed'&&parseFloat(getComputedStyle(el).borderTopWidth)>=1&&el.getBoundingClientRect().width>0)")
                result['checks'].append('Missing subscription readings retain dashed tracks in the default theme')
                from armada import thread_metadata
                # The probe stays invisible to the owner. Simulate a visible
                # document for a widget that deliberately pauses hidden polling.
                js("Object.defineProperty(document,'hidden',{configurable:true,get:()=>false});true")
                js("window.__activitySignals=0;window.addEventListener('armada:agent-activity',()=>window.__activitySignals++);true")
                thread_metadata.set_unread(root/'agents/captain','main',True)
                marker=root/'agents/captain/runs/.running/widget-probe.json'
                util.write_json_atomic(marker,{})
                Fixture.delay_activity=True
                js("document.querySelector('[data-activity-refresh]').focus();document.querySelector('[data-activity-refresh]').click();true")
                assert activity_entered.wait(5)
                assert js("document.querySelector('[data-activity-refresh]').disabled&&document.querySelector('[data-activity-monitor]').getAttribute('aria-busy')==='true'")
                activity_release.set()
                wait(lambda: js("!!document.querySelector('[data-activity-group=working] .mc-activity-avatar .mc-actdot[data-act=working]')&&!document.querySelector('[data-activity-refresh]').disabled"),'Refresh icon updates circular avatars with pulsing working dots')
                assert js("getComputedStyle(document.querySelector('[data-activity-group=working] .mc-av')).borderRadius==='50%'&&getComputedStyle(document.querySelector('[data-activity-group=working] .mc-actdot')).animationName==='mc-actwork'")
                wait(lambda: js("!!document.querySelector('[data-activity-group=unread-replies] .mc-activity-avatar[aria-label]')"),'Activity monitor refreshes unread avatars with accessible names')
                assert js("!document.querySelector('[data-activity-monitor] details')&&!document.querySelector('[data-activity-monitor] summary')")
                assert util.read_json_state(root/'agents/captain/threads/meta.json')['unread']['main']
                wait(lambda: js('window.__activitySignals>0'),'Shared status poll reports live activity')
                js("document.querySelector('[data-activity-group=working] .mc-activity-avatar').focus();true")
                marker.unlink()
                wait(lambda: js("!document.querySelector('[data-activity-group=working] li')&&!!document.querySelector('[data-activity-group=unread-replies] li')"),'Completed agent automatically moves out of Working and remains unread')
                assert js("document.activeElement.matches('[data-activity-refresh]')"),'Removed focused avatar returns focus to Refresh'
                result['checks'].append('Completion preserves keyboard focus and unread metadata')
                assert js("window.__probeIntervals.find(i=>i.fn===window.mcRefreshActivityMonitor).delay===300000")
                reads=Fixture.activity_reads
                js('window.__probeIntervals.find(i=>i.fn===window.mcRefreshActivityMonitor).fn();true')
                wait(lambda: Fixture.activity_reads>reads and js("!document.querySelector('[data-activity-refresh]').disabled"),'Five-minute timer refreshes the actual widget snapshot')
                snapshot=js("document.querySelector('[data-activity-monitor]').innerHTML")
                Fixture.reject_activity=True
                js("document.querySelector('[data-activity-refresh]').click();true")
                wait(lambda: js("document.querySelector('[data-activity-monitor]').hasAttribute('data-stale')&&!document.querySelector('[data-activity-refresh]').disabled"),'Refresh failure preserves content and reports a stale reading')
                assert js("document.querySelector('[data-activity-monitor]').innerHTML")==snapshot
                Fixture.reject_activity=False
                js("document.querySelector('[data-activity-refresh]').click();true")
                wait(lambda: js("!document.querySelector('[data-activity-monitor]').hasAttribute('data-stale')&&!document.querySelector('[data-activity-refresh]').disabled"),'Refresh icon recovers after a failed refresh')
                js("document.getElementById('mc-addwidget').focus();window.answer='pending';mcConfirm('Remove synthetic item?','Nothing real is changed.',{ok:'Remove',danger:true}).then(value=>window.answer=value);true")
                wait(lambda: js("document.activeElement.matches('[data-no]')&&!!document.querySelector('[role=dialog][aria-modal=true]')"), 'Destructive dialog starts on Cancel and is named')
                js("document.activeElement.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}))")
                assert js("window.answer==='pending'"), 'Enter on Cancel must not confirm'
                js("document.activeElement.click()")
                wait(lambda: js("window.answer===false&&document.activeElement.id==='mc-addwidget'"), 'Cancel restores opener focus')
                js("window.answer='pending';mcConfirm('Keyboard check','Synthetic dialog',{ok:'Continue'}).then(value=>window.answer=value);true")
                js("document.querySelector('[data-yes]').focus();document.activeElement.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true,cancelable:true}))")
                assert js("document.activeElement.matches('[data-no]')"), 'Tab wraps within dialog'
                js("document.activeElement.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}))")
                wait(lambda: js("window.answer===false&&!document.querySelector('.mc-confirm-ov')"), 'Escape cancels without confirming')
                wait(lambda: js("document.documentElement.scrollWidth<=innerWidth+1&&document.querySelector('.mc-nav-actions').getBoundingClientRect().right<=innerWidth+1"), '1024px navigation fits and actions remain reachable')
                js("document.documentElement.classList.remove('armada-dark');document.body.classList.remove('armada-dark')")
                for aid in ('navigator','quartermaster'):
                    util.write_json_atomic(root/f'agents/{aid}/runs/.running/widget-display.json',{})
                js('window.mcRefreshActivityMonitor();true')
                wait(lambda: js("document.querySelectorAll('[data-activity-group=working] .mc-activity-avatar').length===2"),'Working portraits share a horizontal row')
                assert js("(()=>{const a=[...document.querySelectorAll('[data-activity-group=working] .mc-activity-avatar')].map(e=>e.getBoundingClientRect());return Math.abs(a[0].top-a[1].top)<1&&a[1].left>a[0].right;})()")
                capture('m11-overview-light-1024')
                Fixture.delay_layout = True
                js("MC_DASH.heights.register=401;mcDashSave()")
                assert entered.wait(5)
                js("MC_DASH.heights.register=402;mcDashSave();MC_DASH.heights.register=403;mcDashSave()")
                release.set()
                wait(lambda: Fixture.saves == [401, 403], 'Layout writes serialize and coalesce to the last edit')
                wait(lambda: js("document.getElementById('mc-layout-status').dataset.state==='saved'"), 'Layout success is reported')
                Fixture.reject_layout = True
                js("MC_DASH.heights.register=404;mcDashSave()")
                wait(lambda: js("document.getElementById('mc-layout-status').dataset.state==='error'"), 'Failed layout save is visible')
                assert util.read_json_state(root / 'dashboard.json')['heights']['register'] == 403
                navigate('/agent/captain/skills')
                js("document.querySelector('[data-save-agent-policy]').closest('details').open=true;document.querySelector('[data-tool-connector=ibkr] [data-allow]').value='get_*\\ncreate_order_instruction\\nsubmit_order';document.querySelector('[data-preview-policy=agent]').click()")
                wait(lambda: js("document.querySelector('[data-policy-status]').dataset.state==='ready'"), 'Unsaved access preview completes')
                assert js("document.querySelector('[data-policy-preview]').textContent.includes('Newly permitted: create_order_instruction')")
                assert js("document.querySelector('[data-policy-preview]').textContent.includes('Cannot call: submit_order')")
                assert (agent_path.read_bytes(), (root / 'realm.json').read_bytes()) == before
                result['checks'].append('Preview shows draft grant and order denial without writing permissions')
                js("document.querySelector('[data-policy-preview] details').open=true;document.querySelector('[data-policy-preview]').scrollIntoView({block:'center'})")
                capture('m11-policy-light-1024', '[data-policy-preview]')
                js("document.querySelector('[data-tool-connector=ibkr] [data-allow]').dispatchEvent(new Event('input',{bubbles:true}))")
                assert js("document.querySelector('[data-policy-preview]').hidden"), 'Edits invalidate the preview'
                from System import Action
                window.native.Invoke(Action(lambda: setattr(window.native.webview, 'ZoomFactor', 1.5)))
                navigate('/')
                wait(lambda: js('innerWidth<800&&document.documentElement.scrollWidth<=innerWidth+1'), '150 percent zoom fits the logical viewport')
                js("document.documentElement.classList.add('armada-dark')")
                assert js("[...document.querySelectorAll('#mc-hdr-limits .mc-limit-bar')].every(el=>getComputedStyle(el).borderTopStyle==='dashed')")
                capture('m11-overview-dark-150pct')
                navigate('/settings?tab=realm')
                js("document.documentElement.classList.add('armada-dark');mcChangelog(true)")
                wait(lambda: js("!!document.activeElement.closest('#mc-changelog')&&document.querySelector('#mc-changelog').getAttribute('role')==='dialog'"), 'Lazy dialog owns focus at 150 percent zoom')
                capture('m11-dialog-dark-150pct')
                js("document.activeElement.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}))")
                assert js("getComputedStyle(document.getElementById('mc-changelog')).display==='none'")
                result['ok'] = True
            except Exception:
                result['error'] = traceback.format_exc()
                result['activity_state']=js("document.querySelector('[data-activity-monitor]')?.outerHTML")
                result['state'] = js("JSON.stringify({path:location.pathname,focus:document.activeElement?.outerHTML?.slice(0,300),width:innerWidth,scrollWidth:document.documentElement.scrollWidth,status:document.querySelector('[data-policy-status]')?.textContent})")
            finally:
                release.set()
                activity_release.set()
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
    raise SystemExit(run(parser.parse_args().output))
