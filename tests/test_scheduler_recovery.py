import json
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock

import pytest

from armada import app, schedsvc, scheduler, updater


@pytest.fixture
def recovery(tmp_path, monkeypatch):
    root = tmp_path / 'Ready realm'
    root.mkdir()
    (root/'realm.json').write_text('{"name":"Ready realm"}')
    monkeypatch.setattr(schedsvc, '_watchdog', None)
    monkeypatch.setattr(schedsvc, '_child', None)
    monkeypatch.setattr(schedsvc, '_last_spawn', 0)
    monkeypatch.setattr(schedsvc, 'eligible_realms', lambda initial='': [str(root)])
    monkeypatch.setattr(schedsvc, 'autostart_enabled', lambda: True)
    monkeypatch.setattr(updater, 'apply_requested', lambda: False)
    monkeypatch.setattr(scheduler, 'lock_holder', lambda root: None)
    now = [100.0]
    monkeypatch.setattr(schedsvc.time, 'monotonic', lambda: now[0])
    watch = schedsvc.Supervisor(str(root))
    monkeypatch.setattr(schedsvc, '_watchdog', watch)
    return root, watch, now


def test_delayed_lease_stays_quiet_then_proves_ready(recovery, monkeypatch):
    root, watch, now = recovery
    start = Mock(return_value={'ok':True,'starting':True})
    monkeypatch.setattr(schedsvc, 'start', start)
    watch.step()
    assert schedsvc.status(root)['action_required'] is False
    assert not schedsvc.ready()
    now[0] += 10
    watch.step()
    assert start.call_count == 1
    monkeypatch.setattr(scheduler, 'lock_holder', lambda root: {'pid':123})
    watch.step()
    assert schedsvc.ready()
    assert schedsvc.status(root)['recovery'] == 'running'
    assert not schedsvc.status(root)['action_required']


def test_crash_recovers_and_new_realm_is_monitored(recovery, monkeypatch):
    root, watch, now = recovery
    held = {str(root): {'pid':123}}
    monkeypatch.setattr(scheduler, 'lock_holder', lambda root: held.get(str(root)))
    start = Mock(return_value={'ok':True,'starting':True})
    monkeypatch.setattr(schedsvc, 'start', start)
    watch.step()
    assert not start.called
    held.clear()
    watch.step()
    assert start.call_count == 1
    held[str(root)] = {'pid':456}
    other = root.parent/'Other realm'
    monkeypatch.setattr(schedsvc, 'eligible_realms', lambda initial='': [str(root),str(other)])
    now[0] += 20
    watch.step()
    assert start.call_count == 2
    assert watch.snapshot(root)['recovery'] == 'running'
    assert not watch.snapshot(other)['action_required']
    assert not schedsvc.ready(), 'Every eligible realm must have its real lease.'


def test_three_launch_failures_require_action_and_preserve_reason(recovery, monkeypatch):
    root, watch, now = recovery
    start = Mock(return_value={'ok':False,'error':'[WinError 5] Access denied'})
    monkeypatch.setattr(schedsvc, 'start', start)
    for i in range(3):
        watch.step()
        assert watch.snapshot(root)['action_required'] == (i == 2)
        now[0] += 20
    for _ in range(4):
        watch.step()
    assert start.call_count == 3
    assert watch.snapshot(root)['error'] == '[WinError 5] Access denied'
    schedsvc.retry_start()
    watch.step()
    assert not watch.snapshot(root)['action_required']
    assert start.call_count == 5


def test_popen_success_without_a_lease_is_not_success(recovery, monkeypatch):
    root, watch, now = recovery
    monkeypatch.setattr(schedsvc, 'start', Mock(return_value={'ok':True,'starting':True}))
    monkeypatch.setattr(schedsvc, '_child', Mock(poll=Mock(return_value=2)))
    for _ in range(4):
        watch.step()
        now[0] += 20
    assert watch.snapshot(root)['action_required']
    assert 'exited with code 2' in watch.snapshot(root)['error']
    # A late successful lease clears even an exhausted recovery warning.
    monkeypatch.setattr(scheduler, 'lock_holder', lambda root: {'pid':456})
    watch.step()
    assert not watch.snapshot(root)['action_required']


@pytest.mark.parametrize('pause,enabled,expected',[(True,True,'paused'),(False,False,'disabled')])
def test_update_drain_and_explicit_disable_never_respawn(recovery, monkeypatch, pause, enabled, expected):
    root, watch, now = recovery
    monkeypatch.setattr(updater, 'apply_requested', lambda: pause)
    monkeypatch.setattr(schedsvc, 'autostart_enabled', lambda: enabled)
    start = Mock()
    monkeypatch.setattr(schedsvc, 'start', start)
    watch.step()
    assert not start.called
    assert watch.snapshot(root)['recovery'] == expected
    assert watch.snapshot(root)['action_required'] == (not enabled)
    if not enabled:
        assert schedsvc.ready()


def test_concurrent_starts_and_hung_live_child_do_not_duplicate(recovery, monkeypatch):
    root, watch, now = recovery
    child = Mock(pid=456,poll=Mock(return_value=None))
    popen = Mock(return_value=child)
    monkeypatch.setattr(schedsvc.subprocess, 'Popen', popen)
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert all(result['ok'] for result in pool.map(lambda _:schedsvc.start(),range(8)))
    now[0] += 100
    assert schedsvc.start()['pid'] == 456
    assert popen.call_count == 1
    watch.stop.set()
    assert not schedsvc.start()['ok']
    assert popen.call_count == 1


def test_watch_installs_one_supervisor_per_desktop_lifetime(monkeypatch):
    monkeypatch.setattr(schedsvc, '_watchdog', None)
    thread=Mock();monkeypatch.setattr(schedsvc.threading,'Thread',thread)
    first=schedsvc.watch('Initial')
    assert schedsvc.watch('Other') is first
    assert thread.call_count == 1
    first.stop.set()
    assert schedsvc.watch('Initial') is not first
    assert thread.call_count == 2


def test_eligibility_includes_other_ready_realms_but_not_setup_or_archive(tmp_path, monkeypatch):
    from armada import activerealm
    roots=[]
    for name, fields in [('Ready',{}),('Setup',{'setup':{'step':'tour'}}),('Archived',{'archived':True})]:
        root=tmp_path/name;root.mkdir()
        (root/'realm.json').write_text(json.dumps({'name':name,**fields}))
        roots.append(str(root))
    monkeypatch.setattr(activerealm, 'every', lambda: roots)
    assert schedsvc.eligible_realms(roots[1]) == [roots[0]]


def test_supervisor_reports_repeated_state_errors_without_exiting(recovery, monkeypatch):
    root, watch, now = recovery
    monkeypatch.setattr(scheduler, 'lock_holder', Mock(side_effect=OSError('Invalid ownership state')))
    count=[0]
    def wait(interval):
        count[0]+=1
        if count[0] == 3: watch.stop.set()
    monkeypatch.setattr(watch.stop, 'wait', wait)
    watch.run()
    assert watch.snapshot(root)['action_required']
    assert watch.snapshot(root)['error'] == 'Invalid ownership state'


def test_update_health_waits_for_scheduler_before_acknowledgement(tmp_path, monkeypatch):
    import armada_bootstrap as bootstrap
    (tmp_path/bootstrap.HEALTH).write_text('{}')
    monkeypatch.setattr(updater, 'ROOT', tmp_path)
    monkeypatch.setattr(updater, 'installed', lambda: True)
    monkeypatch.setattr(app, '_quitting', False)
    monkeypatch.setattr(schedsvc, 'ready', Mock(side_effect=[False,True]))
    monkeypatch.setattr(app.time, 'sleep', lambda _:None)
    confirm=Mock()
    monkeypatch.setattr(bootstrap, 'confirm_health', confirm)
    app._confirm_startup_health()
    assert schedsvc.ready.call_count == 2
    assert confirm.call_count == 1


def test_scheduler_failure_retains_update_rollback_health_marker(tmp_path, monkeypatch):
    import armada_bootstrap as bootstrap
    marker=tmp_path/bootstrap.HEALTH;marker.write_text('{}')
    monkeypatch.setattr(updater, 'ROOT', tmp_path)
    monkeypatch.setattr(updater, 'installed', lambda: True)
    monkeypatch.setattr(app, '_quitting', False)
    monkeypatch.setattr(schedsvc, 'ready', lambda:False)
    confirm=Mock();monkeypatch.setattr(bootstrap, 'confirm_health', confirm)
    app._confirm_startup_health(timeout=0)
    assert marker.exists() and not confirm.called


def test_scheduler_banner_waits_for_automatic_recovery():
    node=shutil.which('node')
    if not node:pytest.skip('Node required for browser checks')
    result=subprocess.run([node,str(Path(__file__).with_name('scheduler_banner_harness.js'))],
                          capture_output=True,text=True,timeout=30)
    assert result.returncode == 0,result.stderr


def test_native_probe_daemon_uses_its_isolated_account_record(tmp_path, monkeypatch):
    import runpy,sys
    from armada import instance
    from tools import upgrade_probe
    config=tmp_path/'probe.json'
    config.write_text(json.dumps({'root':str(tmp_path/'install'),'home':str(tmp_path/'home')}))
    monkeypatch.setenv('ARMADA_UPGRADE_PROBE',str(config))
    monkeypatch.setattr(sys,'argv',['upgrade_probe.py','--scheduler','--engine','auto','--app-owner','42'])
    monkeypatch.setattr(sys,'path',list(sys.path))
    monkeypatch.setattr(instance,'_account_directory',instance._account_directory)
    run=Mock();monkeypatch.setattr(runpy,'run_path',run)
    upgrade_probe.isolated_scheduler_child()
    assert instance._account_directory() == tmp_path/'home/.armada'
    assert sys.argv == [str(tmp_path/'install/armada_bootstrap.py'),'schedule',
                        '--engine','auto','--app-owner','42']
    run.assert_called_once_with(str(tmp_path/'install/armada_bootstrap.py'),run_name='__main__')
