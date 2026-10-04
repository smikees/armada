"""Recovery runs through the normal stable entry point after abrupt process termination."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

import armada_bootstrap as bootstrap
from armada import execution, updater
from test_updater import inst, _release

FLAGS = 0x08000000 if os.name == 'nt' else 0


@pytest.fixture
def installation(tmp_path):
    root = tmp_path/'install'
    root.mkdir()
    shutil.copy2(Path(bootstrap.__file__), root/'armada_bootstrap.py')
    (root/'installed.json').write_text('{}')
    for folder,version in [('armada','1.0.0'),('armada.staged','1.1.0')]:
        package = root/folder
        package.mkdir()
        (package/'__init__.py').write_text(f'__version__ = "{version}"\n')
        (package/'__main__.py').write_text('import sys\nfrom pathlib import Path\nfrom armada import __version__\nPath(sys.argv[1]).write_text(__version__)\n')
    staged = root/'armada.staged'
    bootstrap.atomic_json(staged/'.staged.json',{'version':'1.1.0','files':bootstrap.inventory(staged)})
    return root


def run(root, *args):
    return subprocess.run([sys.executable,*map(str,args)],cwd=root,capture_output=True,text=True,
                          timeout=20,creationflags=FLAGS)


@pytest.mark.parametrize('point',['prepared','live_moved','old_moved','stage_moved','new_live'])
def test_next_launch_recovers_after_each_durable_step(installation, point):
    root=installation
    code='''
import os,sys
from pathlib import Path
import armada_bootstrap as b
point=sys.argv[1]
atomic,replace=b.atomic_json,b.replace
def record(path,state):
 atomic(path,state)
 if state.get('phase')==point:os._exit(77)
def move(src,dst):
 replace(src,dst)
 if (point=='live_moved' and Path(src).name=='armada') or (point=='stage_moved' and Path(src).name=='armada.staged'):os._exit(77)
b.atomic_json=record;b.replace=move
b.apply(Path.cwd())
'''
    stopped=run(root,'-c',code,point)
    assert stopped.returncode==77,stopped.stderr
    marker=root/'launched.txt'
    result=run(root,root/'armada_bootstrap.py',marker)
    assert result.returncode==0,result.stderr
    assert marker.read_text()=='1.1.0'
    assert bootstrap.version(root/'armada.previous')=='1.0.0'
    assert not (root/bootstrap.JOURNAL).exists()


def test_damaged_stage_rolls_back_a_missing_live_package(installation):
    root=installation
    state={'format':1,'phase':'old_moved','version':'1.1.0','old_version':'1.0.0',
           'new_files':bootstrap.inventory(root/'armada.staged'),'old_files':bootstrap.inventory(root/'armada')}
    bootstrap.atomic_json(root/bootstrap.JOURNAL,state)
    (root/'armada').rename(root/'armada.previous')
    (root/'armada.staged/__main__.py').unlink()
    marker=root/'launched.txt'
    result=run(root,root/'armada_bootstrap.py',marker)
    assert result.returncode==0,result.stderr
    assert marker.read_text()=='1.0.0'
    assert (root/'armada.staged').exists(), 'damaged evidence is preserved'


def test_another_process_lease_blocks_replacement_and_crash_releases_it(installation):
    root=installation
    code='''
from pathlib import Path
import armada_bootstrap as b
import time
with b.install_lock(Path.cwd()):b.acquire_lease(Path.cwd())
print('leased',flush=True)
time.sleep(30)
'''
    owner=subprocess.Popen([sys.executable,'-c',code],cwd=root,stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE,text=True,creationflags=FLAGS)
    try:
        assert owner.stdout.readline().strip()=='leased'
        with pytest.raises(OSError,match='still using'):bootstrap.apply(root)
        assert bootstrap.version(root/'armada')=='1.0.0'
        owner.kill();owner.communicate(timeout=10)
        assert bootstrap.apply(root)=='1.1.0'
    finally:
        if owner.poll() is None:owner.kill()
        owner.communicate(timeout=10)


def test_simultaneous_startups_do_not_apply_beneath_each_other(installation):
    root=installation
    with ThreadPoolExecutor(2) as pool:
        results=list(pool.map(lambda i:run(root,root/'armada_bootstrap.py',root/f'launch-{i}'),range(2)))
    assert all(result.returncode==0 for result in results),[result.stderr for result in results]
    assert [(root/f'launch-{i}').read_text() for i in range(2)]==['1.1.0','1.1.0']


def test_concurrent_downloads_cannot_replace_a_newer_stage(inst):
    with ThreadPoolExecutor(2) as pool:
        results=list(pool.map(lambda version:updater.check(fetch=_release(version)),['1.1.0','1.2.0']))
    assert all(r['ok'] for r in results)
    assert updater.staged_version()=='1.2.0'
    assert updater.apply_staged()=='1.2.0'


def test_update_request_during_active_work_is_refused(inst,monkeypatch):
    updater.check(fetch=_release())
    monkeypatch.setattr(execution,'ACTIVE_RUNS',{'running':object()})
    result=updater.request_apply()
    assert not result['ok'] and 'current tasks' in result['error']
    assert not updater.apply_requested()
    assert bootstrap.version(inst/'armada')=='1.0.0'


def test_rejected_update_is_visible_and_can_be_replaced(inst):
    updater.check(fetch=_release())
    bootstrap.atomic_json(inst/bootstrap.ERROR, {'error':'The staged package changed after verification'})
    assert updater.staged_version() == ''
    assert updater.status()['status'] == 'error'
    assert 'changed after verification' in updater.status()['detail']
    assert updater.check(fetch=_release())['ok']
    assert not (inst/bootstrap.ERROR).exists()
    assert updater.apply_staged() == '1.1.0'


def test_bootstrap_refuses_a_verified_but_older_stage(installation):
    root = installation
    (root/'armada/__init__.py').write_text('__version__ = "1.2.0"\n')
    with pytest.raises(OSError, match='must be newer'): bootstrap.apply(root)
    assert bootstrap.version(root/'armada') == '1.2.0'
