"""Startup commit, crash-safe rollback, account scope and bounded resource use."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
import armada_bootstrap as b
from armada import app, instance, restart, updater, util
from test_updater import inst, _release
from test_update_recovery import installation
REAL_FETCH = updater._fetch


def test_profile_override_cannot_change_instance_identity(monkeypatch, tmp_path):
    original = instance._path()
    monkeypatch.setenv('ARMADA_DATA_DIR', str(tmp_path/'other-profile'))
    assert util.data_dir() != original.parent
    assert instance._path() == original


def test_library_entry_claims_instance_before_opening_window(monkeypatch):
    from contextlib import contextmanager
    @contextmanager
    def secondary(*args): yield False
    monkeypatch.setattr(instance, 'claim', secondary)
    owned = Mock()
    monkeypatch.setattr(app, '_run_owned', owned)
    assert app.run('Other realm', 8899) == 0
    owned.assert_not_called()


def test_browser_commit_checks_exact_package(installation):
    root = installation
    b.apply(root)
    assert (root/b.HEALTH).exists()
    with pytest.raises(OSError, match='acknowledgement'):
        b.confirm_health(root, '1.0.0')
    b.confirm_health(root, '1.1.0')
    assert not (root/b.HEALTH).exists()
    with b.install_lock(root): assert b.rollback_locked(root, 'late provider outage') == ''
    assert b.version(root/'armada') == '1.1.0'


def test_startup_uses_the_async_browser_result_instead_of_a_promise_handle():
    class Browser:
        def evaluate_js(self, script, callback):
            callback({'status':200,'data':{'nonce':'current'}})
            return {}  # pywebview's immediate Promise handle is not the response.
    assert app._browser_result(Browser(), 'fetch()') == {'status':200,'data':{'nonce':'current'}}


@pytest.mark.parametrize('point', ['journal', 'failed_moved', 'previous_moved'])
def test_rollback_recovers_after_each_interruption(installation, monkeypatch, point):
    root = installation
    b.apply(root)
    record, replace = b.atomic_json, b.replace
    def write(path, data):
        record(path, data)
        if point == 'journal' and data.get('rollback'): raise KeyboardInterrupt()
    def move(source, target):
        replace(source, target)
        if ((point == 'failed_moved' and source.name == 'armada') or
                (point == 'previous_moved' and source.name == 'armada.previous')):
            raise KeyboardInterrupt()
    with monkeypatch.context() as patch:
        patch.setattr(b, 'atomic_json', write)
        patch.setattr(b, 'replace', move)
        with b.install_lock(root), pytest.raises(KeyboardInterrupt):
            b.rollback_locked(root, 'Browser could not authenticate')
    with b.install_lock(root): b.recover_locked(root)
    assert b.version(root/'armada') == '1.0.0'
    assert not (root/b.HEALTH).exists()
    assert json.loads((root/b.ERROR).read_text())['error'] == 'Browser could not authenticate'
    assert json.loads((root/b.QUARANTINE).read_text())['version'] == '1.1.0'


def test_damaged_previous_version_is_not_restored(installation):
    root = installation
    b.apply(root)
    (root/'armada.previous/__init__.py').write_text('corrupt')
    with b.install_lock(root), pytest.raises(OSError, match='cannot be verified'):
        b.rollback_locked(root, 'startup failed')
    assert b.version(root/'armada') == '1.1.0'


def test_bootstrap_blocks_a_quarantined_version_even_with_an_older_updater(installation):
    root=installation
    saved=root.parent/'original-stage'
    shutil.copytree(root/'armada.staged', saved)
    b.apply(root)
    with b.install_lock(root): b.rollback_locked(root, 'Startup failed')
    shutil.copytree(saved, root/'armada.staged')
    with pytest.raises(OSError, match='quarantined'): b.apply(root)
    assert b.version(root/'armada') == '1.0.0'


def test_low_disk_space_keeps_current_app_and_stage_intact(inst, monkeypatch):
    monkeypatch.setattr(updater.shutil, 'disk_usage', lambda root: type('Disk', (), {'free':1})())
    result = updater.check(fetch=_release())
    assert not result['ok'] and 'disk space' in result['error']
    assert b.version(updater.PKG) == '1.0.0'
    assert not updater.STAGED.exists()


def test_new_bootstrap_requirement_uses_installer_without_fetching_zip(inst):
    result = updater.check(fetch=_release(manifest_extra={'min_bootstrap':b.PROTOCOL+1}))
    assert result['needs_installer'] and not updater.STAGED.exists()


def test_quarantined_release_is_not_staged_again(inst):
    b.atomic_json(updater.ROOT/b.QUARANTINE, {'version':'1.1.0'})
    result = updater.check(fetch=_release())
    assert not result['ok'] and 'failed startup' in result['error']
    assert not updater.STAGED.exists()


def test_work_admission_stays_paused_until_browser_commit(inst):
    assert not updater.admission_paused()
    b.atomic_json(updater.ROOT/b.HEALTH, {'version':'1.1.0'})
    assert updater.admission_paused()


def test_system_job_cannot_dispatch_before_browser_commit(inst, tmp_path, monkeypatch):
    from armada import sysjobs
    realm=tmp_path/'realm';realm.mkdir()
    (realm/'realm.json').write_text('{"schema_version":2}')
    b.atomic_json(updater.ROOT/b.HEALTH, {'version':'1.1.0'})
    monkeypatch.setitem(sysjobs._BY_ID['prune-history'],'run',lambda *a:pytest.fail('Unhealthy startup dispatched work'))
    result=sysjobs.run_one(realm,'prune-history',manual=True)
    assert result['status']=='skipped' and result['reason']=='update-pending'


def test_transient_network_error_retries_but_invalid_transport_does_not(monkeypatch):
    import urllib.error
    attempts = []
    def failure(*args, **kw):
        attempts.append(1)
        raise urllib.error.HTTPError('https://example.test', 503, 'Busy', {}, None)
    monkeypatch.setattr(updater.urllib.request, 'urlopen', failure)
    monkeypatch.setattr(updater.time, 'sleep', lambda n: None)
    with pytest.raises(urllib.error.HTTPError): REAL_FETCH('https://example.test', 1024)
    assert len(attempts) == 3
    with pytest.raises(ValueError): REAL_FETCH('http://example.test', 1024)
    assert len(attempts) == 3


def test_restart_state_discards_malformed_bounds_and_auth_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(util, 'data_dir', lambda:tmp_path)
    (tmp_path/'desktop-state.json').write_text(json.dumps({'width':'bad','height':700,'route':'/settings'}))
    assert app.window_state() == {'height':700,'route':'/settings'}


@pytest.mark.skipif(shutil.which('node') is None, reason='Node required for browser delivery check')
def test_companion_delivery_is_idempotent_after_lost_acknowledgement():
    script=app._alexander_delivery_script({'message':'Help'},'request-one')
    other=app._alexander_delivery_script({'message':'Help'},'request-two')
    harness='const window={};const calls=[];const script='+json.dumps(script)+';'
    harness+="if(eval(script)!==false)throw Error('Receiver absent');window.mcAlexReceive=p=>calls.push(p);"
    harness+="if(eval(script)!==true||eval(script)!==true)throw Error('Acknowledgement');"
    harness+='eval('+json.dumps(other)+');if(calls.length!==2)throw Error(JSON.stringify(calls));'
    result=subprocess.run([shutil.which('node')],input=harness,text=True,capture_output=True)
    assert result.returncode==0,result.stderr


def test_cleanup_retains_current_monitor_and_skips_linked_folders(tmp_path, monkeypatch):
    monkeypatch.setattr(util, 'data_dir', lambda:tmp_path)
    for i in range(8):
        folder = tmp_path/'restart'/str(i)
        folder.mkdir(parents=True)
        os.utime(folder, (100+i,100+i))
    util.write_json_atomic(tmp_path/'restart-status.json', {'nonce':'0','monitor_pid':os.getpid()})
    restart.cleanup(keep=2, days=999999)
    assert {p.name for p in (tmp_path/'restart').iterdir()} == {'0','6','7'}


def test_restart_monitor_restores_and_verifies_previous_code(tmp_path, monkeypatch):
    """Exercise the copied worker, real leases and HTTP readiness after startup rollback."""
    from armada import restart_worker as worker
    from armada.background import process_options
    root, data = tmp_path/'install', tmp_path/'data'
    root.mkdir(); data.mkdir()
    shutil.copy2(b.__file__, root/'armada_bootstrap.py')
    (root/'installed.json').write_text('{}')
    (data/'realm-memory.md').write_text('Owner work after the update must survive')
    script = '''
import json,os,sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler,HTTPServer
from armada import __version__
data=Path(sys.argv[2])
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  self.send_response(200);self.end_headers()
  self.wfile.write(json.dumps({'version':__version__,'desktop_ready':True}).encode())
 def log_message(self,*args):pass
server=HTTPServer(('127.0.0.1',0),Handler)
(data/'instance.json').write_text(json.dumps({'pid':os.getpid()}))
(data/'auth.json').write_text(json.dumps({'token':'fixture','port':server.server_port}))
server.serve_forever()
'''
    for name,version in [('armada','1.0.0'),('armada.staged','1.1.0')]:
        folder=root/name;folder.mkdir()
        (folder/'__init__.py').write_text(f'__version__ = "{version}"\n')
        (folder/'__main__.py').write_text(script)
    staged=root/'armada.staged'
    b.atomic_json(staged/'.staged.json',{'version':'1.1.0','files':b.inventory(staged)})
    b.apply(root)
    copied=data/'restart_worker.py';shutil.copy2(worker.__file__,copied)
    plan={'root':str(root),'realm':str(data),'port':0,'owner_pid':0,'version':'1.1.0',
          'scheduler_required':False,'instance':str(data/'instance.json'),'auth':str(data/'auth.json'),
          'status':str(data/'status.json'),'nonce':'rollback-test','executable':sys._base_executable,
          'log':str(data/'startup.log')}
    path=data/'plan.json';path.write_text(json.dumps(plan))
    children=[]
    def launch(plan,path):
        children.append(subprocess.Popen([sys._base_executable,str(copied),'--launch',str(path)],
                        cwd=root,**process_options()))
    original=worker.reading
    def reading(plan,route):
        auth=json.loads(Path(plan['auth']).read_text())
        return original({**plan,'port':auth['port']},route)
    monkeypatch.setattr(worker,'launch_successor',launch)
    monkeypatch.setattr(worker,'reading',reading)
    try:
        assert worker.recover_failure(plan,path,'Browser session failed',timeout=10)
        assert b.version(root/'armada')=='1.0.0'
        assert json.loads((data/'status.json').read_text())['phase']=='rolled_back'
        assert json.loads((root/b.ERROR).read_text())['error']=='Browser session failed'
        assert (data/'realm-memory.md').read_text()=='Owner work after the update must survive'
    finally:
        for child in children:
            if child.poll() is None:child.kill()
            child.wait(timeout=10)
