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


def run(output, *, system_jobs_only=False):
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
        cfg.update(tool_policy={'ibkr': {'deny': ['*order*']}}, read_only=['skills/**'], providers=['claude', 'codex', 'gemini'])
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
            mixed_limits = False
            reject_fallback = False
            system_runs = []

            def _system_job_run(self, body):
                type(self).system_runs.append(body.get('id'))
                return {'ok': True, 'detail': 'Synthetic layout check; no system job was executed.'}

            def _api_fallback_action(self, body):
                if body.get('action') == 'test':
                    return {'ok': True, 'message': 'Key accepted by the synthetic free-check fixture.'}
                if body.get('action') == 'save' and type(self).reject_fallback:
                    return {'ok': False, 'error': 'Synthetic save refused. Try again.'}
                return super()._api_fallback_action(body)

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
                    if type(self).mixed_limits:
                        from urllib.parse import parse_qs, urlsplit
                        provider = parse_qs(urlsplit(self.path).query).get('provider', ['claude'])[0]
                        payload = {'claude': {'weekly': {'pct': 40}, 'session': {'pct': 93},
                                              'api_credit': {'spent_usd': 0, 'cap_usd': 100, 'reason': 'No API key configured.'}},
                                   'codex': {'groups': [{'id': name, 'name': name, 'windows': [{'window_minutes': 10080, 'pct': 12}]} for name in ('codex', 'other')]},
                                   'gemini': {'weekly': {'pct': 0}}}[provider]
                        self._json(200, {'available': True, 'connected': True, **payload})
                    else:
                        self._json(200,{'available':False,'connected':True,'message':'Synthetic provider has not supplied a reading.'})
                elif path.startswith('/api/') and path not in ('/api/font-size', '/api/thread-state','/api/activity-monitor','/api/agent-activity','/api/system-jobs','/api/job-calendar'):
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
            Fixture.capture_html = js("(() => {const copy=document.documentElement.cloneNode(true);copy.querySelectorAll('script').forEach(s=>s.remove());document.querySelectorAll('textarea').forEach((el,i)=>copy.querySelectorAll('textarea')[i].textContent=el.value);document.querySelectorAll('select').forEach((el,i)=>[...copy.querySelectorAll('select')[i].options].forEach((opt,j)=>opt.toggleAttribute('selected',j===el.selectedIndex)));document.querySelectorAll('input[type=checkbox],input[type=radio]').forEach((el,i)=>copy.querySelectorAll('input[type=checkbox],input[type=radio]')[i].toggleAttribute('checked',el.checked));return '<!doctype html>'+copy.outerHTML;})()")
            scrolls = js("[...document.querySelectorAll('[id]')].filter(e=>e.scrollLeft||e.scrollTop).map(e=>({id:e.id,x:e.scrollLeft,y:e.scrollTop}))")
            Fixture.capture_html += "<script>addEventListener('load',()=>{"+json.dumps(scrolls)+".forEach(s=>document.getElementById(s.id)?.scrollTo(s.x,s.y));})</script>"
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

        def system_jobs_layout():
            nonlocal window
            from System import Action
            from armada import appconfig
            main_window, views = window, []
            def aligned(label):
                geometry = js('checkSystemJobColumns()')
                result.setdefault('system_jobs_geometry', []).append({'phase': label, **geometry})
                assert geometry['ok'], label+': '+json.dumps(geometry)
                result['checks'].append(label)
            try:
                for width, dark, zoom, theme in ((1660,False,1,'armada-ii'), (1024,False,1,'armada'), (720,True,1.5,'armada-ii')):
                    appconfig.save({'theme': theme})
                    # Hidden WebView2 controls can defer shrink notifications.
                    # Fresh native views give each viewport its real initial bounds.
                    window = webview.create_window('Synthetic System jobs layout', local_auth.browser_url(base, '/jobs'),
                                                   width=width, height=900, hidden=True)
                    views.append(window)
                    wait(lambda: window.native is not None and js("document.readyState==='complete'&&typeof mcJobsFilter==='function'"),
                         'System jobs view '+str(width)+' loaded')
                    js("window.__calendarResponses=[];const originalFetch=window.fetch;window.fetch=async(...args)=>{const response=await originalFetch(...args);if(String(args[0]).includes('/api/job-calendar'))window.__calendarResponses.push({status:response.status,body:await response.clone().text()});return response;};true")
                    window.native.Invoke(Action(lambda: setattr(window.native.webview, 'ZoomFactor', zoom)))
                    wait(lambda: abs(js('innerWidth')-(width-16)/zoom)<2,
                         'System jobs viewport '+str(width)+' at '+str(zoom))
                    js("mcJobsTab('system');mcJobsView('list',null,true);true")
                    js((Path(__file__).resolve().parents[1]/'tests/system_jobs_layout_harness.js').read_text(encoding='utf-8'))
                    js('document.documentElement.classList.toggle("armada-dark",'+str(dark).lower()+');mcJobsFilter();true')
                    aligned('System job columns align at '+str(width)+' and '+str(zoom))
                    js("document.getElementById('sf-search').value='no-such-synthetic-job';mcJobsFilter();true")
                    assert js("[...document.querySelectorAll('.mc-sysjob')].every(e=>!e.getClientRects().length)")
                    js("mcJobsFilterClear(document.querySelector('.mc-jobsbar[data-pfx=sf]'));true")
                    aligned('Clearing search restores system columns at '+str(width))
                    for control, attribute in (('f1','cost'), ('status','jstatus'), ('cad','jcad')):
                        js("document.getElementById('sf-"+control+"').dataset.val=document.querySelector('.mc-sysjob').dataset."+attribute+";mcJobsFilter();true")
                        aligned('System '+control+' filter preserves columns at '+str(width))
                        js("mcJobsFilterClear(document.querySelector('.mc-jobsbar[data-pfx=sf]'));true")
                    js("[...document.querySelectorAll('#mc-sysjobstable>div:first-child [onclick]')].forEach(e=>{e.click();e.click();});mcJobsTab('user');mcJobsTab('system');true")
                    aligned('Sorting and reopening System preserve columns at '+str(width))
                    if width<900:
                        assert js("(()=>{const t=document.getElementById('mc-sysjobstable');t.scrollLeft=t.scrollWidth;return t.scrollLeft>0;})()")
                        aligned('Narrow System list scrolls to reachable actions')
                        capture('system-jobs-dark-scaled')
                        js("document.getElementById('mc-sysjobstable').scrollLeft=0;true")
                    elif width==1660:
                        capture('system-jobs-light-wide')
                    for pane in ('user','system'):
                        js("mcJobsTab('"+pane+"');mcJobsView('cal',null,true);true")
                        for mode in ('month','week','day'):
                            selector='#jobs-pane-'+pane+' .mc-jobcal'
                            js("document.querySelector('"+selector+" .mc-jc-view[data-jc="+mode+"]').click();true")
                            wait(lambda: js("!!document.querySelector('"+selector+" .mc-jc-systems [data-system-job=inbox-dispatch] svg')&&!!document.querySelector('"+selector+" .mc-jc-systems [data-system-job=telegram-inbox] svg')"),
                                 'Inbox and Telegram system jobs at top of '+pane+' '+mode+' '+str(width))
                            assert js("(()=>{const section=document.querySelector('"+selector+" .mc-jc-systems');return section===section.parentElement.firstElementChild&&[...section.querySelectorAll('.mc-jc-system')].every(e=>e.getBoundingClientRect().right<=section.getBoundingClientRect().right+1);})()")
                        if pane=='user':
                            capture('system-calendar-'+str(width),'#jobs-pane-user .mc-jc-systems')
                    js("mcJobsTab('system');mcJobsView('list',null,true);true")
                js("const row=document.querySelector('.mc-sysjob');const text=row.querySelector('.mc-sysjob-msg');text.textContent='A long status '+('synthetic-path-without-breaks'.repeat(15));text.style.display='block';true")
                aligned('Long system-job status stays inside its column')
                target = js("document.querySelector('.mc-sysjob').dataset.sysjob")
                js("const row=document.querySelector('.mc-sysjob'),toggle=row.querySelector('input[type=checkbox]');toggle.checked=false;mcSysJobToggle(toggle,row.dataset.sysjob);true")
                wait(lambda: js("document.querySelector('.mc-sysjob .btn-primary').disabled&&document.querySelector('.mc-sysjob [data-next-cell]').textContent==='off'"), 'System off refresh completes')
                aligned('Switching a system job off preserves columns')
                js("const row=document.querySelector('.mc-sysjob'),toggle=row.querySelector('input[type=checkbox]');toggle.checked=true;mcSysJobToggle(toggle,row.dataset.sysjob);true")
                wait(lambda: js("!document.querySelector('.mc-sysjob .btn-primary').disabled"), 'System on refresh completes')
                js("document.querySelector('.mc-sysjob .btn-primary').click();true")
                wait(lambda: Fixture.system_runs == [target] and js("document.querySelector('.mc-sysjob-msg').textContent.includes('done')&&!document.querySelector('.mc-sysjob .btn-primary').disabled"), 'Synthetic Run now refresh completes')
                aligned('Run-now feedback preserves system columns')
                system_state=util.read_json_state(root/'system_jobs.json',default=dict)
                # Native fixtures stay hidden. Simulate a visible page for the
                # production poller, which intentionally pauses when hidden.
                js("Object.defineProperty(document,'hidden',{configurable:true,get:()=>false});true")
                try:
                    util.write_json_atomic(root/'system_jobs.json',{'inbox-dispatch':{'attempt':{'state':'claimed','attempt_id':'native','owner_pid':os.getpid(),'started':'2026-11-13T16:00:00+01:00'}}})
                    with util.file_lock(root/'.scheduler/system/inbox-dispatch.json',validate_state=False):
                        js("document.dispatchEvent(new Event('visibilitychange'));true")
                        try:
                            wait(lambda: js("document.querySelector('[data-sysjob=inbox-dispatch]').dataset.jstatus==='running'&&document.querySelector('[data-sysjob=inbox-dispatch] .btn-primary').disabled"),'Live system execution updates Running without reloading')
                        finally:
                            result['live_system_diagnostic']=js("JSON.stringify({hidden:document.hidden,helper:typeof mcSetRunBtn,row:document.querySelector('[data-sysjob=inbox-dispatch]').outerHTML})")
                        js("document.getElementById('sf-status').dataset.val='running';mcJobsFilter();true")
                        assert js("document.querySelector('[data-sysjob=inbox-dispatch]').getClientRects().length>0")
                    wait(lambda: js("document.querySelector('[data-sysjob=inbox-dispatch] [data-system-detail]').textContent.includes('interrupted')"),'Released system ownership shows Interrupted without a false running state')
                finally:
                    util.write_json_atomic(root/'system_jobs.json',system_state)
            except Exception:
                result['calendar_diagnostic']=js("JSON.stringify({path:location.pathname,responses:window.__calendarResponses,calendars:[...document.querySelectorAll('.mc-jobcal')].map(w=>({scope:w.dataset.scope,view:w._view,html:w.querySelector('.mc-jc-body').innerHTML}))})")
                raise
            finally:
                window = main_window
                for view in views:
                    view.destroy()

        def exercise():
            try:
                wait(lambda: js("document.readyState==='complete'&&typeof mcConfirm==='function'&&!!document.getElementById('mc-grid')"), 'Overview ready')
                if system_jobs_only:
                    system_jobs_layout()
                    result['ok'] = True
                    return
                wait(lambda: js("document.querySelector('.mc-attention-summary').textContent.includes('job proposals')"), 'Attention links pending review')
                wait(lambda: js("!!document.querySelector('.mc-w[data-id=activity] [data-activity-monitor]')&&!document.querySelector('#mc-ovh .mc-attention-summary')"),'Activity monitor owns attention outside the header')
                wait(lambda: js("document.querySelectorAll('#mc-hdr-limits .mc-limit-unavailable').length===6&&[...document.querySelectorAll('#mc-hdr-limits .mc-limit-unavailable')].every(el=>el.textContent==='Not reported')"),'Missing subscription readings keep Not reported in every row')
                assert js("[...document.querySelectorAll('#mc-hdr-limits .mc-limit-bar')].every(el=>getComputedStyle(el).borderTopStyle==='dashed'&&parseFloat(getComputedStyle(el).borderTopWidth)>=1&&el.getBoundingClientRect().width>0)")
                result['checks'].append('Missing subscription readings retain dashed tracks in the default theme')
                from armada import appconfig
                Fixture.mixed_limits = True
                appconfig.save({'theme': 'armada-ii'})
                js('sessionStorage.clear();true')
                navigate('/')
                wait(lambda: js("document.querySelectorAll('#mc-hdr-limits .mc-limit-row[title*=\"93%\"]').length===1"), 'Mixed live subscription readings render')
                result['limits_dom'] = js("document.getElementById('mc-hdr-limits').outerHTML")
                result['limits_geometry'] = js("JSON.stringify([...document.querySelectorAll('#mc-hdr-limits .mc-limit-row')].map(e=>({text:e.textContent,rect:e.getBoundingClientRect().toJSON(),display:getComputedStyle(e).display,visibility:getComputedStyle(e).visibility})))")
                capture('m11-mixed-limits-armada-ii')
                assert js("[...document.querySelectorAll('#mc-hdr-limits .mc-limit-row.is-unavailable')].length===2&&[...document.querySelectorAll('#mc-hdr-limits .mc-limit-row.is-unavailable')].every(e=>e.textContent==='Not reported'&&e.getBoundingClientRect().height>0&&getComputedStyle(e.querySelector('.mc-limit-bar')).borderTopStyle==='dashed')")
                assert js("(()=>{const h=document.getElementById('mc-hdr-limits').getBoundingClientRect();return [...document.querySelectorAll('#mc-hdr-limits .mc-limit-row,#mc-hdr-limits .mc-limit-credit')].every(e=>{const r=e.getBoundingClientRect();return r.top>=h.top&&r.bottom<=h.bottom&&r.left>=h.left&&r.right<=h.right;});})()")
                result['checks'].append('Weekly-only connected providers keep visible dashed session rows in Armada II')
                js("document.documentElement.classList.add('armada-dark')")
                capture('m11-mixed-limits-armada-ii-dark')
                assert js("(()=>{const h=document.getElementById('mc-hdr-limits').getBoundingClientRect();return [...document.querySelectorAll('#mc-hdr-limits .mc-limit-row')].every(e=>e.getBoundingClientRect().bottom<=h.bottom);})()")
                result['checks'].append('API credit and bucket selector leave all six rows visible in dark mode')
                Fixture.mixed_limits = False
                appconfig.save({'theme': 'default'})
                js('sessionStorage.clear();true')
                navigate('/')
                from armada import thread_metadata
                # The probe stays invisible to the owner. Simulate a visible
                # document for a widget that deliberately pauses hidden polling.
                js("Object.defineProperty(document,'hidden',{configurable:true,get:()=>false});true")
                js("window.__activitySignals=0;window.addEventListener('armada:agent-activity',()=>window.__activitySignals++);true")
                thread_metadata.set_unread(root/'agents/captain','main',True)
                marker=root/'agents/captain/runs/.running/widget-probe.json'
                util.write_json_atomic(marker,{'owner_pid':os.getpid()})
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
                    util.write_json_atomic(root/f'agents/{aid}/runs/.running/widget-display.json',{'owner_pid':os.getpid()})
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
                window.native.Invoke(Action(lambda: setattr(window.native.webview, 'ZoomFactor', 1.0)))
                from armada import appconfig, provider_keys, api_fallback, worker
                appconfig.save({'theme': 'armada-ii'})
                navigate('/settings?tab=app')
                js("document.querySelector('[data-fallback-open=mc-api-fallback-claude]').focus();document.querySelector('[data-fallback-open=mc-api-fallback-claude]').click();true")
                wait(lambda: js("!document.getElementById('mc-api-fallback-claude').hidden&&!document.querySelector('#mc-api-fallback-claude [data-fallback-save]').disabled"), 'Claude setup opens as a loaded modal')
                assert js("document.activeElement.closest('#mc-api-fallback-claude')!==null&&document.querySelector('#mc-api-fallback-claude [data-fallback-key]').type==='password'")
                assert not worker.enabled() and not provider_keys.configured('claude')
                js("document.querySelector('#mc-api-fallback-claude [data-fallback-key]').value='sk-ant-synthetic-native-api-key';document.activeElement.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}));true")
                assert js("document.getElementById('mc-api-fallback-claude').hidden&&document.querySelector('#mc-api-fallback-claude [data-fallback-key]').value===''&&document.activeElement.matches('[data-fallback-open=mc-api-fallback-claude]')")
                assert not provider_keys.configured('claude')
                result['checks'].append('Escape clears an unsaved key, restores focus and does not enable fallback')
                js("mcOpenApiFallback('mc-api-fallback-claude');true")
                wait(lambda: js("!document.querySelector('#mc-api-fallback-claude [data-fallback-save]').disabled"), 'Fallback metadata reloads before save')
                capture('api-fallback-light')
                js("document.querySelector('#mc-api-fallback-claude [data-fallback-key]').value='sk-ant-synthetic-native-api-key';document.querySelector('#mc-api-fallback-claude [data-fallback-test]').click();true")
                wait(lambda: js("document.querySelector('#mc-api-fallback-claude [data-fallback-feedback]').textContent.includes('synthetic free-check')"), 'Free key check is separate from saving and model execution')
                assert not provider_keys.configured('claude')
                Fixture.reject_fallback = True
                js("document.querySelector('#mc-api-fallback-claude [data-fallback-save]').click();true")
                wait(lambda: js("document.querySelector('#mc-api-fallback-claude [data-fallback-feedback]').textContent.includes('Synthetic save refused')"), 'Failed save keeps the modal open and offers retry')
                assert not provider_keys.configured('claude')
                Fixture.reject_fallback = False
                js("document.querySelector('#mc-api-fallback-claude [data-fallback-save]').click();true")
                wait(lambda: js("document.getElementById('mc-api-fallback-claude').hidden&&document.querySelector('[data-fallback-entry=claude] [data-fallback-summary]').textContent==='Critical jobs only'"), 'Save enables critical-job fallback and closes the modal')
                assert provider_keys.key('claude') == 'sk-ant-synthetic-native-api-key' and not worker.enabled()
                assert js("document.querySelector('#mc-api-fallback-claude [data-fallback-key]').value===''")
                navigate('/agent/captain/configure')
                js("document.querySelector('[data-fallback-open=mc-api-fallback-claude-captain]').closest('details').open=true;mcOpenApiFallback('mc-api-fallback-claude-captain');true")
                wait(lambda: js("!document.querySelector('#mc-api-fallback-claude-captain [data-fallback-save]').disabled"), 'Agent key setup uses the same modal')
                js("const select=document.querySelector('#mc-api-fallback-claude-captain [data-fallback-source]');select.value='agent';mcFallbackSource(select);document.querySelector('#mc-api-fallback-claude-captain [data-fallback-key]').value='sk-ant-synthetic-agent-native-key';document.querySelector('#mc-api-fallback-claude-captain [data-fallback-save]').click();true")
                wait(lambda: js("document.getElementById('mc-api-fallback-claude-captain').hidden"), 'Agent workspace key saves without changing the engine key')
                assert api_fallback.credential('claude', root, 'captain') == 'sk-ant-synthetic-agent-native-key'
                assert provider_keys.key('claude') == 'sk-ant-synthetic-native-api-key'
                window.native.Invoke(Action(lambda: setattr(window.native.webview, 'ZoomFactor', 1.5)))
                js("document.documentElement.classList.add('armada-dark');mcOpenApiFallback('mc-api-fallback-claude-captain');true")
                wait(lambda: js("!document.querySelector('#mc-api-fallback-claude-captain [data-fallback-save]').disabled"), 'Agent modal reopens at 150 percent zoom')
                assert js("document.querySelector('#mc-api-fallback-claude-captain [data-fallback-source]').value==='agent'")
                assert js("(()=>{const r=document.querySelector('#mc-api-fallback-claude-captain .mc-modal-box').getBoundingClientRect();return r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight;})()")
                js("document.querySelector('#mc-api-fallback-claude-captain [data-fallback-save]').focus();document.activeElement.dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true,cancelable:true}));true")
                assert js("document.activeElement.matches('#mc-api-fallback-claude-captain [data-fallback-dismiss]')")
                capture('api-fallback-agent-dark-150pct')
                js("document.activeElement.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}));true")
                result['checks'].append('API setup fits a scaled dark viewport and traps keyboard focus')
                js("mcOpenApiFallback('mc-api-fallback-claude-captain');true")
                wait(lambda: js("!document.querySelector('#mc-api-fallback-claude-captain [data-fallback-save]').disabled"), 'Agent API removal opens')
                js("document.querySelector('#mc-api-fallback-claude-captain [data-fallback-remove]').checked=true;document.querySelector('#mc-api-fallback-claude-captain [data-fallback-save]').click();true")
                wait(lambda: js("document.getElementById('mc-api-fallback-claude-captain').hidden"), 'Removing an agent key turns its fallback off')
                assert not provider_keys.configured('claude', root, 'captain')
                assert api_fallback.settings('claude', root, 'captain')['key_source'] == 'off'
                assert provider_keys.key('claude') == 'sk-ant-synthetic-native-api-key'
                system_jobs_layout()
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
    parser.add_argument('--system-jobs-only', action='store_true')
    args = parser.parse_args()
    raise SystemExit(run(args.output, system_jobs_only=args.system_jobs_only))
