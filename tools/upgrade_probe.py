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

ROOT = Path(__file__).resolve().parents[1]


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


def verify(stage, previous, candidate, output):
    old, archive = validate_assets(previous)
    new, _ = validate_assets(candidate)
    if old['version'] == new['version']: raise RuntimeError('An upgrade must cross versions')
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
        process = subprocess.Popen([str(root/'python/ARMADA.exe'),str(Path(__file__).resolve()),'--child'],
            cwd=root, env=env, creationflags=0x08000000)
        try:
            deadline = time.monotonic()+180
            while time.monotonic() < deadline:
                if output.exists():
                    result = json.loads(output.read_text(encoding='utf-8'))
                    if not result.get('ok'): raise RuntimeError(result.get('error','Upgrade probe failed'))
                    result['previous_sha256'] = old['sha256']
                    result['candidate_sha256'] = new['sha256']
                    result['commit'] = new['commit']
                    output.write_text(json.dumps(result,indent=2),encoding='utf-8')
                    print(f"Native upgrade: {len(result['checks'])} real-page/restart checks passed",flush=True)
                    return result
                time.sleep(.5)
            raise RuntimeError('Packaged upgrade gate timed out')
        finally:
            # Never touch user processes: stop only children tagged with this probe's folder.
            marker = Path(scratch)/'home/.armada/desktop-instance.json'
            if marker.exists():
                owner = json.loads(marker.read_text())
                if owner.get('pid') != process.pid:
                    subprocess.run(['taskkill','/PID',str(owner['pid']),'/T','/F'],capture_output=True,creationflags=0x08000000)
            if process.poll() is None: process.kill()
            process.wait(timeout=10)


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
    appconfig.save({'auto_update':False,'scheduler_autostart':False,'keep_in_tray':False})
    realm = home/'Test realm'
    (realm/'agents/captain').mkdir(parents=True,exist_ok=True)
    if not (realm/'realm.json').exists():
        (realm/'realm.json').write_text(json.dumps({'name':'Upgrade test','default_engine':'codex','members':['captain']}))
        (realm/'agents/captain/agent.json').write_text(json.dumps({'id':'captain','display':'Captain','coordinator':True}))
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
            usage = js(window,"fetch('/api/usage').then(async r=>({status:r.status,data:await r.json()}))")
            check('actual Usage endpoint',usage['status']==200 and not usage['data'].get('error'))
            check('production Alexander opener',app.open_alexander())
            deadline = time.monotonic()+15
            while time.monotonic()<deadline:
                if app._alex_window and app._alex_window.evaluate_js("!!document.querySelector('link[href*=\"/static/brand.css\"]')"): break
                time.sleep(.2)
            else: raise AssertionError('Actual companion did not authenticate')
            check('Usage survives actual companion',js(window,"fetch('/api/usage').then(r=>r.status)")==200)
            app._alex_window.destroy()
            if not successor:
                (home/'pre-update-checks.json').write_text(json.dumps(checks),encoding='utf-8')
                result = js(window,"fetch('/api/check-update').then(r=>r.json())")
                check('signed candidate staged through app',result.get('staged')==config['after'])
                check('normal update request',js(window,"fetch('/update',{method:'POST'}).then(r=>r.json())").get('ok'))
                return
            check('browser acknowledged installed startup',js(window,"fetch('/api/instance').then(r=>r.json())").get('desktop_ready'))
            check('health transaction committed',not (root/'.armada-update-health.json').exists())
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


if __name__ == '__main__':
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
