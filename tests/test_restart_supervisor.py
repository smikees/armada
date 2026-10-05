"""Native leases and verified handover, without using a real realm or desktop UI."""
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil
import threading
import time
from unittest.mock import Mock

import pytest

import armada_bootstrap as bootstrap
from armada import restart, restart_worker as worker
from armada.background import process_options


def test_live_legacy_lease_is_a_visible_blocker_and_crash_releases_it(tmp_path):
    root = Path(__file__).resolve().parents[1]
    code = '''
import sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import armada_bootstrap as b
with b.install_lock(Path(sys.argv[2])): b.acquire_lease(Path(sys.argv[2]))
print('ready',flush=True)
sys.stdin.readline()
'''
    process = subprocess.Popen([sys._base_executable, '-c', code, str(root), str(tmp_path)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **process_options())
    try:
        assert process.stdout.readline().strip() == 'ready'
        blockers = restart.lease_blockers(tmp_path, {os.getpid()})
        assert blockers[0]['pid'] == process.pid and 'older ARMADA' in blockers[0]['label']
        assert restart.lease_blockers(tmp_path, {process.pid}) == []
        process.kill()
        process.wait(timeout=10)
        assert restart.lease_blockers(tmp_path, set()) == []
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=10)


def test_handover_verifies_version_desktop_and_scheduler(tmp_path, monkeypatch):
    marker = tmp_path/'instance.json'
    marker.write_text(json.dumps({'pid':os.getpid()}))
    plan = {'instance':str(marker), 'owner_pid':99999999, 'version':'1.2.3', 'scheduler_required':True}
    responses = {'api/instance':{'version':'1.2.3','desktop_ready':True}, 'api/scheduler-status':{'running':True}}
    monkeypatch.setattr(worker, 'reading', lambda plan, route: responses[route])
    assert worker.verify(plan)
    responses['api/instance']['version'] = '1.2.2'
    assert not worker.verify(plan)
    assert 'Expected version 1.2.3' in worker.readiness_error(plan)
    responses['api/instance']['version'] = '1.2.3'
    responses['api/instance']['desktop_ready'] = False
    assert not worker.verify(plan)
    responses['api/instance']['desktop_ready'] = True
    responses['api/scheduler-status']['running'] = False
    assert not worker.verify(plan)
    assert 'scheduler' in worker.readiness_error(plan)
    plan['scheduler_required'] = False
    assert worker.verify(plan)
    plan['owner_pid'] = os.getpid()
    assert not worker.verify(plan), 'An old instance cannot prove successful restart.'


def test_invalid_old_restart_record_does_not_block_future_progress(tmp_path, monkeypatch):
    from armada import util
    monkeypatch.setattr(util, 'data_dir', lambda: tmp_path)
    for text in ['[]', 'null', '{broken']:
        (tmp_path/'restart-status.json').write_text(text)
        assert restart.state() == {}


def test_monitor_timeout_preserves_the_specific_readiness_failure(tmp_path, monkeypatch):
    plan = {'root':str(tmp_path),'owner_pid':99999999,'nonce':'test','status':str(tmp_path/'status.json')}
    monkeypatch.setattr(worker, 'launch_successor', lambda *args: None)
    monkeypatch.setattr(worker, 'readiness_error', lambda plan: 'The required scheduler has not started.')
    with pytest.raises(OSError, match='required scheduler has not started'):
        worker.supervise(plan, tmp_path/'plan.json', timeout=.01)


def test_status_commit_retries_a_brief_windows_sharing_violation(tmp_path, monkeypatch):
    replace = Path.replace
    calls = []
    def locked_once(path, destination):
        calls.append(path)
        if len(calls) == 1: raise PermissionError('File is briefly being read')
        return replace(path, destination)
    monkeypatch.setattr(Path, 'replace', locked_once)
    plan = {'status':str(tmp_path/'status.json'), 'nonce':'sharing-test'}
    worker.record(plan, 'complete', 'Verified')
    assert len(calls) == 2
    assert json.loads(Path(plan['status']).read_text())['phase'] == 'complete'


def test_monitor_failure_leaves_current_app_alive(tmp_path, monkeypatch):
    from armada import util
    monkeypatch.setattr(util, 'data_dir', lambda: tmp_path)
    monkeypatch.setattr(restart.desktop_launch, 'spawn', Mock(side_effect=OSError('launch denied')))
    if os.name != 'nt':
        pytest.skip('Windows desktop launch failure')
    with pytest.raises(OSError, match='launch denied'):
        restart.begin(tmp_path, '', 8870, '1.2.3', False)
    assert worker.alive(os.getpid())
    plan = json.loads((tmp_path/'restart-status.json').read_text())
    assert plan['phase'] == 'starting_monitor'
    assert Path(plan['root']) == tmp_path


def test_real_bootstrap_handover_waits_for_exit_then_verifies_successor(tmp_path, monkeypatch):
    """The copied worker applies a stage, starts a server and checks its real HTTP readiness."""
    root = tmp_path / "Owner's ARMADA installation"
    root.mkdir()
    shutil.copy2(bootstrap.__file__, root / 'armada_bootstrap.py')
    (root/'installed.json').write_text('{}')
    data = tmp_path/'data'
    data.mkdir()
    for name, version in [('armada', '1.0.0'), ('armada.staged', '1.1.0')]:
        package = root/name
        package.mkdir()
        (package/'__init__.py').write_text(f'__version__ = "{version}"\n')
        (package/'__main__.py').write_text(r'''
import json, os, subprocess, sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from armada import __version__
data = Path(sys.argv[2])
scheduler = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(40)'])
(data/'scheduler.json').write_text(json.dumps({'pid':scheduler.pid}))
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get('Authorization') != 'Bearer test-secret':
            self.send_error(401); return
        result = ({'version':__version__, 'desktop_ready':True} if self.path=='/api/instance'
                  else {'running': scheduler.poll() is None})
        self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(result).encode())
    def log_message(self, *args): pass
server = HTTPServer(('127.0.0.1', 0), Handler)
(data/'instance.json').write_text(json.dumps({'pid':os.getpid()}))
(data/'auth.json').write_text(json.dumps({'token':'test-secret', 'port':server.server_port}))
server.serve_forever()
''')
    staged = root/'armada.staged'
    bootstrap.atomic_json(staged/'.staged.json', {'version':'1.1.0','files':bootstrap.inventory(staged)})
    (root/bootstrap.REQUEST).write_text('1.1.0')
    old = subprocess.Popen([sys._base_executable, '-c', 'import time; time.sleep(40)'], **process_options())
    worker_path = data/'restart_worker.py'
    shutil.copy2(worker.__file__, worker_path)
    plan = {'root':str(root), 'realm':str(data), 'owner_pid':old.pid, 'executable':sys._base_executable,
            'version':'1.1.0','scheduler_required':True,'nonce':'test-handover',
            'status':str(data/'status.json'), 'instance':str(data/'instance.json'),
            'auth':str(data/'auth.json'),'log':str(data/'startup.log'), 'port':0}
    plan_path = data/'plan.json'
    plan_path.write_text(json.dumps(plan))
    children, errors = [], []
    def launch(plan, path):
        children.append(subprocess.Popen([sys._base_executable, str(worker_path), '--launch', str(path)],
                                         cwd=root, **process_options()))
    original_reading = worker.reading
    def reading(plan, route):
        auth = json.loads(Path(plan['auth']).read_text())
        return original_reading({**plan, 'port':auth['port']}, route)
    monkeypatch.setattr(worker, 'launch_successor', launch)
    monkeypatch.setattr(worker, 'reading', reading)
    def supervise():
        try: worker.supervise(plan, plan_path, timeout=20)
        except Exception as exc: errors.append(exc)
    monitor = threading.Thread(target=supervise)
    monitor.start()
    try:
        deadline = time.monotonic()+5
        while not Path(plan['status']).exists() and time.monotonic()<deadline: time.sleep(.05)
        assert json.loads(Path(plan['status']).read_text())['phase'] == 'waiting_exit'
        assert not children and not (data/'instance.json').exists()
        old.kill(); old.wait(timeout=5)
        monitor.join(timeout=25)
        assert not monitor.is_alive() and not errors, errors
        assert json.loads(Path(plan['status']).read_text())['phase'] == 'complete'
        assert bootstrap.version(root/'armada') == '1.1.0'
        assert bootstrap.version(root/'armada.previous') == '1.0.0'
        assert not (root/bootstrap.REQUEST).exists()
        assert worker.verify({**plan, 'port':json.loads((data/'auth.json').read_text())['port']})
    finally:
        if old.poll() is None: old.kill(); old.wait(timeout=5)
        for child in children:
            if child.poll() is None: child.kill()
            child.wait(timeout=5)
        if (data/'scheduler.json').exists():
            pid = json.loads((data/'scheduler.json').read_text())['pid']
            if worker.alive(pid):
                import signal
                os.kill(pid, signal.SIGTERM)
        monitor.join(timeout=25)
