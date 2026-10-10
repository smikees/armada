"""Packaged previous-release -> candidate upgrade, with real hidden Windows UI.

Uses a current staged runtime/bootstrap and the verified last published app payload.
The bootstrap/runtime installer boundary is checked separately: this gate exercises
the compatible package update path once that runtime is installed. No user registry,
provider account or live realm is used. Results are tied to both signed packages.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import zipfile
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def probe_process(argv, cwd, env):
    """Own every test descendant even when a restart detaches from its first parent."""
    sys.path.insert(0, str(ROOT))
    from armada.background import process_options
    from armada.engine.windows_job import WindowsJob
    tree = WindowsJob()
    process = None
    try:
        process = subprocess.Popen(argv, cwd=cwd, env=env, **process_options(suspended=True))
        tree.attach_and_resume(process)
        yield process
    finally:
        try:
            tree.close()  # Also closes restart monitors, successors and WebView descendants.
        finally:
            if process is not None:
                if process.poll() is None: process.kill()  # Includes failed job assignment.
                process.wait(timeout=10)


def validate_assets(folder):
    sys.path.insert(0, str(ROOT))
    from armada import updater
    manifest = updater.verified_manifest((folder/updater.MANIFEST).read_bytes(),
                                        (folder/updater.SIGNATURE).read_bytes())
    package = folder/manifest['zip']
    if (package.stat().st_size != manifest['size'] or
            hashlib.sha256(package.read_bytes()).hexdigest() != manifest['sha256']):
        raise RuntimeError('Upgrade probe package does not match its signed manifest')
    return manifest, package


def font_checks(window, js, check):
    """Exercise production typography and saved shortcuts in the actual desktop browser."""
    check('reference font controller loaded',window.evaluate_js('typeof mcFontSize === "object"'))
    js(window,"""Promise.resolve().then(()=>{
      const probe=document.createElement('div');probe.id='font-probe';
      probe.innerHTML='<p class="mc-md" id="font-body">Reference text</p>'+
        '<span id="font-inline" style="font-size:10px">Small label</span>'+
        '<textarea id="font-draft" style="font-size:13px;width:180px;height:60px">Unsaved draft</textarea>'+
        '<svg id="font-icon" width="24" height="24"><text id="font-chart" font-size="9.5">1</text>'+
        '<text id="font-chart-css" class="mc-md" font-size="9.5">2</text></svg>';
      document.body.appendChild(probe);return true;
    })""")
    check('default size saves through production API',js(window,'mcFontSize.saveDefault(18)')==18)
    measured = window.evaluate_js("""({body:parseFloat(getComputedStyle(document.getElementById('font-body')).fontSize),
      inline:parseFloat(getComputedStyle(document.getElementById('font-inline')).fontSize),
      chart:parseFloat(getComputedStyle(document.getElementById('font-chart')).fontSize),
      chartCSS:parseFloat(getComputedStyle(document.getElementById('font-chart-css')).fontSize),
      icon:document.getElementById('font-icon').getBoundingClientRect().width,
      draft:document.getElementById('font-draft').value})""")
    check('stylesheet typography scales proportionally',abs(measured['body']-18)<.01)
    check('inline typography scales proportionally',abs(measured['inline']-10*18/13)<.01)
    check('SVG chart typography follows reference size',abs(measured['chart']-9.5*18/13)<.01)
    check('SVG presentation attributes preserve stylesheet precedence',abs(measured['chartCSS']-18)<.01)
    window.evaluate_js('document.getElementById("font-chart").setAttribute("font-size","11")')
    check('dynamic SVG labels follow reference size',abs(window.evaluate_js(
        'parseFloat(getComputedStyle(document.getElementById("font-chart")).fontSize)')-11*18/13)<.01)
    check('icons retain original dimensions',measured['icon']==24)
    check('font changes preserve an unsaved draft',measured['draft']=='Unsaved draft')
    for key, code, expected in [('+','Equal',19),('-','Minus',18),('0','Digit0',18),('=','Equal',19)]:
        event = json.dumps({'key':key,'code':code,'ctrlKey':True,'bubbles':True,'cancelable':True})
        check('shortcut prevents native zoom '+key,window.evaluate_js(
            '!document.dispatchEvent(new KeyboardEvent("keydown",'+event+'))'))
        check('shortcut updates and persists reference '+key,
              js(window,'mcFontSize.save(mcFontSize.get())')==expected)
    from System import Func, Boolean
    zoom_enabled = window.native.Invoke(Func[Boolean](lambda:
        window.native.browser.webview.CoreWebView2.Settings.IsZoomControlEnabled))
    check('WebView native zoom does not compete with text shortcuts',not zoom_enabled)
    check('fresh streamed text receives current size',js(window,"""new Promise(resolve=>{
      const text=document.createElement('p');text.style.fontSize='13px';
      document.getElementById('font-probe').appendChild(text);
      setTimeout(()=>resolve(Math.abs(parseFloat(getComputedStyle(text).fontSize)-19)<.01),0);
    })"""))
    js(window,'mcFontSize.save(18)')
    window.evaluate_js('document.getElementById("font-probe").remove()')


def verify(stage, previous, candidate, output):
    old, archive = validate_assets(previous)
    new, _ = validate_assets(candidate)
    if old['version'] == new['version']: raise RuntimeError('An upgrade must cross versions')
    output.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix='armada-upgrade-', ignore_cleanup_errors=True) as scratch:
        root = Path(scratch)/'install'
        shutil.copytree(stage, root)
        shutil.rmtree(root/'armada')
        with zipfile.ZipFile(archive) as package: package.extractall(root)
        config = Path(scratch)/'probe.json'
        config.write_text(json.dumps({'root':str(root), 'home':str(Path(scratch)/'home'),
            'candidate':str(candidate.resolve()), 'output':str(output.resolve()),
            'before':old['version'], 'after':new['version']}), encoding='utf-8')
        env = {k:v for k,v in os.environ.items() if not k.startswith(('ARMADA_','PYTHON','VIRTUAL_ENV'))}
        env['ARMADA_UPGRADE_PROBE'] = str(config)
        env['ARMADA_NO_EXTERNAL_NOTIFY'] = '1'
        with probe_process([str(root/'python/ARMADA.exe'),str(Path(__file__).resolve()),'--child'], root, env):
            deadline = time.monotonic()+180
            while time.monotonic() < deadline:
                if output.exists():
                    result = json.loads(output.read_text(encoding='utf-8'))
                    if not result.get('ok'): raise RuntimeError(result.get('error','Upgrade probe failed'))
                    result['previous_sha256'] = old['sha256']
                    result['candidate_sha256'] = new['sha256']
                    result['commit'] = new['commit']
                    break
                time.sleep(.5)
            else:
                raise RuntimeError('Packaged upgrade gate timed out')
        result['checks'].append('isolated probe process tree fully stopped')
        output.write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(f"Native upgrade: {len(result['checks'])} real-page/restart/cleanup checks passed",flush=True)
        return result


def child(successor=None):
    config = json.loads(Path(os.environ['ARMADA_UPGRADE_PROBE']).read_text())
    home, root = Path(config['home']), Path(config['root'])
    home.mkdir(parents=True,exist_ok=True)
    for key, value in {'HOME':home,'USERPROFILE':home,'APPDATA':home/'roaming','LOCALAPPDATA':home/'local'}.items():
        Path(value).mkdir(parents=True,exist_ok=True)
        os.environ[key] = str(value)
    os.environ['ARMADA_NO_EXTERNAL_NOTIFY'] = '1'
    os.environ['ARMADA_DATA_DIR'] = str(home/'.armada')
    sys.path.insert(0, str(root))
    if successor:
        # Normal bootstrap replacement must happen before injecting test adapters;
        # importing the old package first would keep it cached after the file swap.
        import runpy
        api = runpy.run_path(str(root/'armada_bootstrap.py'))
        api['apply'](root)
    import webview
    from armada import app, appconfig, desktop_launch, providers, auth, updater, tray
    from armada import instance
    instance._account_directory = lambda:home/'.armada'
    from unittest.mock import Mock
    # Prevent provider probes, quotas, notifications and machine registry writes.
    auth.status = lambda **kw:{'ok':True,'logged_in':False,'detail':'Isolated upgrade probe'}
    providers.status = lambda *a,**kw:{'installed':False,'logged_in':False,'detail':'Isolated upgrade probe'}
    from armada.engine import get_engine
    for provider in ('claude','codex','gemini'):
        get_engine(provider).__class__._launcher = lambda self:None
    tray.Tray = lambda *a,**kw:Mock(start=Mock(return_value=False))
    app._retire_scheduler_run_key = lambda:None
    create = webview.create_window
    webview.create_window = lambda *a,**kw:create(*a,**dict(kw,hidden=True))
    app._fatal = lambda message:(_ for _ in ()).throw(RuntimeError(message))
    assets = Path(config['candidate'])
    updater._fetch = lambda url,limit:(assets/url.rsplit('/',1)[-1]).read_bytes()
    launch_arguments = updater.launch_arguments
    # The Windows account guard intentionally ignores HOME overrides. The real test
    # daemon needs the same isolated account boundary as its GUI, so it can contact
    # that GUI for update shutdown rather than looking up the user's live instance.
    updater.launch_arguments = lambda *args: (
        [str(Path(__file__).resolve()), '--scheduler', *args[1:]]
        if args and args[0] == 'schedule' else launch_arguments(*args))
    appconfig.save({'auto_update':False,'scheduler_autostart':True,'keep_in_tray':False})
    realm = home/'Test realm'
    (realm/'agents/captain').mkdir(parents=True,exist_ok=True)
    if not (realm/'realm.json').exists():
        (realm/'realm.json').write_text(json.dumps({'name':'Upgrade test','default_engine':'codex','members':['captain']}))
        (realm/'agents/captain/agent.json').write_text(json.dumps({'id':'captain','display':'Captain','coordinator':True}))
    from armada import realm_registry, sysjobs
    other = home/'Other ready realm'
    other.mkdir(exist_ok=True)
    (other/'realm.json').write_text('{"name":"Other ready realm","members":[]}')
    for folder in (realm, other):
        realm_registry.ensure(str(folder), folder.name)
        # Real daemon/leases, but no provider, upkeep or external-delivery work.
        for job in sysjobs.JOBS:
            sysjobs.set_enabled(folder, job['id'], False)
    jobs = realm/'agents/captain/jobs'
    jobs.mkdir(exist_ok=True)
    (jobs/'future.json').write_text(json.dumps({'id':'future','cron':'0 0 29 2 *','enabled':True}))
    # This shim is copied with the normal supervisor. It propagates only this
    # isolated probe environment and wraps its successor to reinject fake providers.
    shim = home/'desktop_launch.py'
    shim.write_text('import os,subprocess\n'
        'def spawn(argv,cwd=None):\n'
        f' if "--launch" in list(map(str,argv)): argv=[str(argv[0]),{str(Path(__file__).resolve())!r},"--successor",str(argv[-1])]\n'
        ' return subprocess.Popen(list(map(str,argv)),cwd=cwd,env=dict(os.environ),creationflags=0x08000000).pid\n')
    desktop_launch.__file__ = str(shim)
    desktop_launch.desktop_parent = lambda:True
    namespace = {}
    exec(shim.read_text(),namespace)
    desktop_launch.spawn = namespace['spawn']
    checks = []
    def check(label, condition):
        if not condition: raise AssertionError(label)
        checks.append(label)
    def js(window, script):
        done = threading.Event()
        values = []
        window.evaluate_js(script,callback=lambda value:(values.append(value),done.set()))
        if not done.wait(15): raise AssertionError('Browser request timed out')
        return values[0]
    def exercise():
        try:
            deadline = time.monotonic()+35
            while time.monotonic()<deadline:
                window = app._main_window
                if window and window.evaluate_js("!!document.querySelector('link[href*=\"/static/brand.css\"]')"): break
                time.sleep(.2)
            else: raise AssertionError('Actual app page did not load')
            expected = config['after'] if successor else config['before']
            info = js(window,"fetch('/api/instance').then(r=>r.json())")
            deadline = time.monotonic()+15
            while not info.get('desktop_ready') and time.monotonic()<deadline:
                time.sleep(.2)
                info = js(window,"fetch('/api/instance').then(r=>r.json())")
            check('initial browser startup acknowledged',info.get('desktop_ready'))
            check(f"correct installed version: {info.get('version')} (expected {expected})",info['version']==expected)
            deadline = time.monotonic()+45
            while time.monotonic()<deadline:
                scheduler_status=js(window,"fetch('/api/scheduler-status').then(r=>r.json())")
                if scheduler_status.get('running'):break
                time.sleep(.2)
            check('real scheduler automatically acquired the active realm',scheduler_status.get('running'))
            from armada import scheduler, schedsvc
            check('real scheduler acquired another registered realm',bool(scheduler.lock_holder(other)))
            if successor or config.get('scheduler_recovery'):
                check('normal startup has no scheduler warning',not window.evaluate_js(
                    'document.getElementById("mc-schedbar").innerText').strip())
                original_pid=scheduler_status['pid']
                child_process=schedsvc._child
                check('recovery test owns the actual scheduler child',child_process and child_process.pid==original_pid)
                child_process.terminate()
                child_process.wait(timeout=10)
                scheduler_status=js(window,"fetch('/api/scheduler-status').then(r=>r.json())")
                check('scheduler loss stays quiet during automatic recovery',not scheduler_status.get('action_required'))
                deadline=time.monotonic()+45
                while time.monotonic()<deadline:
                    scheduler_status=js(window,"fetch('/api/scheduler-status').then(r=>r.json())")
                    if scheduler_status.get('running') and scheduler_status['pid']!=original_pid:break
                    time.sleep(.2)
                check('hidden desktop automatically replaced a stopped scheduler',
                      scheduler_status.get('running') and scheduler_status['pid']!=original_pid)
                check('recovered scheduler owns every registered realm',bool(scheduler.lock_holder(other)))
            font_testing = bool(successor or config.get('font_only'))
            if font_testing: font_checks(window, js, check)
            for route in ('/settings','/docs','/agent/captain/threads','/alexander'):
                response = js(window,'fetch('+json.dumps(route)+').then(async r=>({status:r.status,body:await r.text()}))')
                check('authenticated real page '+route,response['status']==200 and '/static/brand.css' in response['body'])
            for route in ('/settings','/docs','/agent/captain/threads'):
                window.load_url(f'http://127.0.0.1:{info.get("port", app._app_url.split(":")[-1].strip("/"))}'+route)
                deadline = time.monotonic()+15
                while time.monotonic()<deadline:
                    if window.evaluate_js('location.pathname')==route and window.evaluate_js("!!document.querySelector('link[href*=\"/static/brand.css\"]')"): break
                    time.sleep(.2)
                else: raise AssertionError('Real navigation failed: '+route)
                check('actual navigation '+route,window.evaluate_js('location.pathname')==route)
                if font_testing:
                    check('reference font survives navigation '+route,window.evaluate_js('mcFontSize.get()')==18)
                    if route=='/settings':
                        check('settings reference control matches saved size',window.evaluate_js(
                            'document.getElementById("mc-font-size").value')=='18')
            if font_testing: js(window,'mcFontSize.save(13)')
            usage = js(window,"fetch('/api/usage').then(async r=>({status:r.status,data:await r.json()}))")
            check('actual Usage endpoint',usage['status']==200 and not usage['data'].get('error'))
            check('production Alexander opener',app.open_alexander())
            deadline = time.monotonic()+15
            while time.monotonic()<deadline:
                if app._alex_window and app._alex_window.evaluate_js("!!document.querySelector('link[href*=\"/static/brand.css\"]')"): break
                time.sleep(.2)
            else: raise AssertionError('Actual companion did not authenticate')
            check('Usage survives actual companion',js(window,"fetch('/api/usage').then(r=>r.status)")==200)
            if font_testing:
                js(window,'mcFontSize.save(18)')
                deadline=time.monotonic()+5
                while time.monotonic()<deadline and app._alex_window.evaluate_js('mcFontSize.get()')!=18: time.sleep(.05)
                check('Alexander receives saved reference without reload',app._alex_window.evaluate_js('mcFontSize.get()')==18)
                js(window,'mcFontSize.save(13)')
                deadline=time.monotonic()+5
                while time.monotonic()<deadline and app._alex_window.evaluate_js('mcFontSize.get()')!=13: time.sleep(.05)
                check('Alexander receives current size without reload',app._alex_window.evaluate_js('mcFontSize.get()')==13)
            app._alex_window.destroy()
            if config.get('font_only'):
                Path(config['output']).write_text(json.dumps({'ok':True,'checks':checks}),encoding='utf-8')
                return
            if not successor:
                (home/'pre-update-checks.json').write_text(json.dumps(checks),encoding='utf-8')
                result = js(window,"fetch('/api/check-update').then(r=>r.json())")
                check('signed candidate staged through app',result.get('staged')==config['after'])
                check('normal update request',js(window,"fetch('/update',{method:'POST'}).then(r=>r.json())").get('ok'))
                return
            check('browser acknowledged installed startup',js(window,"fetch('/api/instance').then(r=>r.json())").get('desktop_ready'))
            deadline=time.monotonic()+10
            while (root/'.armada-update-health.json').exists() and time.monotonic()<deadline:time.sleep(.1)
            check('health transaction committed only with the real scheduler ready',
                  not (root/'.armada-update-health.json').exists() and schedsvc.ready())
            app.save_window_state()
            check('selected thread persists in restart state',app.window_state().get('route','').startswith('/agent/captain/threads'))
            deadline = time.monotonic()+15
            while time.monotonic()<deadline:
                status = json.loads((home/'.armada/restart-status.json').read_text())
                if status.get('phase') == 'complete': break
                time.sleep(.2)
            else: raise AssertionError('The production restart monitor did not acknowledge success')
            check('restart monitor completed',status['phase']=='complete')
            previous_checks = json.loads((home/'pre-update-checks.json').read_text())
            result = {'ok':True,'checks':['before: '+label for label in previous_checks]+['after: '+label for label in checks],
                      'before':config['before'],'after':config['after']}
            Path(config['output']).write_text(json.dumps(result),encoding='utf-8')
        except Exception:
            Path(config['output']).write_text(json.dumps({'ok':False,'error':traceback.format_exc(),'checks':checks}),encoding='utf-8')
        finally:
            if successor or Path(config['output']).exists():
                if app._main_window: app._quit_windows(app._main_window)
    def wait_then_exercise():
        while app._main_window is None: time.sleep(.1)
        time.sleep(.5)
        exercise()
    threading.Thread(target=wait_then_exercise,daemon=True).start()
    if successor:
        import runpy
        plan = json.loads(Path(successor).read_text())
        sys.argv = [str(Path(plan['log']).parent/'restart_worker.py'),'--launch',str(successor)]
        runpy.run_path(sys.argv[0],run_name='__main__')
    else:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
        import runpy
        entry = root/'armada_bootstrap.py'
        sys.argv = [str(entry),'app',str(realm),'--port',str(port)]
        runpy.run_path(str(entry),run_name='__main__')


def isolated_scheduler_child():
    """Real scheduler/bootstrap with only the native account lookup isolated."""
    config=json.loads(Path(os.environ['ARMADA_UPGRADE_PROBE']).read_text())
    root,home=Path(config['root']),Path(config['home'])
    sys.path.insert(0,str(root))
    from armada import instance
    instance._account_directory=lambda:home/'.armada'
    import runpy
    sys.argv=[str(root/'armada_bootstrap.py'),'schedule',*sys.argv[2:]]
    runpy.run_path(sys.argv[0],run_name='__main__')


if __name__ == '__main__':
    if sys.argv[1:2] == ['--scheduler']:
        isolated_scheduler_child()
        raise SystemExit(0)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--child',action='store_true')
    parser.add_argument('--successor',type=Path)
    parser.add_argument('--stage',type=Path)
    parser.add_argument('--previous',type=Path)
    parser.add_argument('--candidate',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.child or args.successor: child(args.successor)
    else: verify(args.stage,args.previous,args.candidate,args.output)
