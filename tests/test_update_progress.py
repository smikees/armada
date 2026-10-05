import json
import os
from pathlib import Path

from armada import activerealm, execution, instance, updater, util
from test_updater import inst, _release


def test_idle_scheduler_is_not_reported_as_running_jobs(inst, monkeypatch):
    updater.check(fetch=_release())
    monkeypatch.setattr(updater, 'scheduler_running', lambda: True)
    result = updater.request_apply()
    assert result['phase'] == 'preparing'
    assert result['blockers'] == []
    assert 'scheduler' in result['message']
    assert 'jobs' not in result['message']


def test_work_in_another_realm_blocks_update_but_stale_work_does_not(inst, tmp_path, monkeypatch):
    realm = tmp_path/'another realm'
    marker = realm/'agents/research/runs/.running/digest.json'
    marker.parent.mkdir(parents=True)
    marker.write_text(json.dumps({'owner_pid': os.getpid()}))
    monkeypatch.setattr(activerealm, 'every', lambda: [realm])
    updater.check(fetch=_release())
    assert updater.request_apply()['phase'] == 'waiting_tasks'
    marker.write_text(json.dumps({'owner_pid': os.getpid(), 'status': 'finished'}))
    assert updater.progress()['phase'] == 'restarting'
    marker.write_text(json.dumps({'owner_pid': 99999999}))
    assert updater.progress()['phase'] == 'restarting'


def test_claimed_system_job_needs_a_live_execution_lock(inst, tmp_path, monkeypatch):
    realm = tmp_path/'realm'
    realm.mkdir()
    (realm/'system_jobs.json').write_text(json.dumps({'refresh': {'attempt': {'state': 'claimed', 'owner_pid': os.getpid()}}}))
    monkeypatch.setattr(activerealm, 'every', lambda: [realm])
    updater.check(fetch=_release())
    assert updater.request_apply()['phase'] == 'restarting'
    with util.file_lock(realm/'.scheduler/system/refresh.json', validate_state=False):
        assert updater.progress()['phase'] == 'waiting_tasks'
    assert updater.progress()['phase'] == 'restarting'


def test_restart_uses_registered_port(monkeypatch):
    monkeypatch.setattr(instance, 'current', lambda: {'port': 8890})
    requests = []
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
    monkeypatch.setattr(updater.urllib.request, 'urlopen', lambda request, **kw: requests.append(request.full_url) or Response())
    assert updater._restart_window()
    assert requests == ['http://127.0.0.1:8890/restart']


def test_postpone_reopens_admission_but_preserves_staged_release(inst):
    updater.check(fetch=_release())
    updater.request_apply()
    assert updater.apply_requested()
    assert updater.cancel_apply()['ok']
    assert not updater.apply_requested()
    assert updater.staged_version() == '1.1.0'
