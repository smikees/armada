"""Held-job diagnostics must never terminate the scheduler (0.99.150 regression)."""
import datetime as dt
import json
import threading
from types import SimpleNamespace

import pytest

from armada import preflight, records, runner, run_policy, scheduler, sysjobs, util

AT = dt.datetime(2026, 11, 14, 9, 0)


def realm(path):
    jobs = path / 'agents/a/jobs'
    jobs.mkdir(parents=True)
    util.write_json_atomic(path/'realm.json', {'schema_version': 2})
    util.write_json_atomic(jobs.parent/'agent.json', {'id': 'a'})
    for name in ('held', 'healthy'):
        util.write_json_atomic(jobs/f'{name}.json', {'id': name, 'kind': 'agent',
            'schedule': 'daily 09:00', 'prompt': 'Synthetic work', 'allow_tools': False})
    return path


@pytest.fixture
def isolated(monkeypatch):
    from armada import telegram, usage_snapshot, updater
    monkeypatch.setattr(preflight, 'hold_reason', lambda *a: '')
    monkeypatch.setattr(sysjobs, 'JOBS', [])
    monkeypatch.setattr(telegram, 'start_listener', lambda *a, **kw: None)
    monkeypatch.setattr(usage_snapshot, 'refresh_due', lambda *a: None)
    monkeypatch.setattr(updater, 'admission_paused', lambda: False)
    monkeypatch.setattr(scheduler, '_update_wanted', lambda: False)


@pytest.mark.parametrize('fault', ['record', 'approval', 'approval_io', 'agent', 'retry', 'schedule', 'history'])
@pytest.mark.parametrize('kind', ['agent', 'command'])
def test_early_holds_keep_job_identity_and_kind(tmp_path, monkeypatch, isolated, fault, kind):
    from armada import job_retries
    root = realm(tmp_path/'realm')
    job = {'id': 'held', 'kind': kind, 'schedule': 'daily 09:00', 'prompt': 'Synthetic', 'allow_tools': False}
    monkeypatch.setattr(scheduler, 'iter_jobs', lambda *a: [('a', 'held', job)])
    monkeypatch.setattr(run_policy, 'held_reason', lambda *a: '')
    def fail(*a, **kw):
        raise OSError('Synthetic unreadable record')
    if fault == 'record': job['_record_error'] = 'Synthetic invalid job'
    elif fault == 'approval': monkeypatch.setattr(run_policy, 'held_reason', lambda *a: 'Approval changed')
    elif fault == 'approval_io': monkeypatch.setattr(run_policy, 'held_reason', fail)
    elif fault == 'agent': monkeypatch.setattr(records, 'admit_agent', fail)
    elif fault == 'retry': monkeypatch.setattr(job_retries, 'pending', fail)
    elif fault == 'schedule':
        def bad_schedule(*a): raise ValueError('Synthetic invalid schedule')
        monkeypatch.setattr(scheduler, '_due_time', bad_schedule)
    elif fault == 'history': monkeypatch.setattr(scheduler, 'ran_today', fail)
    result = scheduler.tick(root, at=AT)
    assert len(result) == 1
    row = result[0]
    assert (row['agent'], row['job'], row['kind'], row['status']) == ('a', 'held', kind, 'held')
    assert row['schedule'] == 'daily 09:00' and row['detail']


def test_actual_approval_hold_does_not_stop_other_jobs_realms_or_next_pass(tmp_path, monkeypatch, isolated, capsys):
    roots = [realm(tmp_path/name) for name in ('first', 'second')]
    path = roots[0]/'agents/a/jobs/held.json'
    job = json.loads(path.read_text())
    run_policy.seal_job(roots[0], 'a', job)
    util.write_json_atomic(path, {**job, 'prompt': 'Changed without owner approval'})
    calls, passes = [], []
    completed = threading.Event()
    def run(root, agent, job, **kw):
        calls.append((root.name, job))
        if len(calls) == 3: completed.set()
        return {'status': 'ok'}
    monkeypatch.setattr(runner, 'run_job', run)
    original = scheduler.tick
    def tick(root, **kw):
        rows = original(root, at=AT, **kw)
        passes.append(root.name)
        return rows
    monkeypatch.setattr(scheduler, 'tick', tick)
    def pause(_):
        assert completed.wait(5), 'Healthy jobs were not dispatched'
        if len(passes) >= 4: raise KeyboardInterrupt
        scheduler._work_changed.set()
    monkeypatch.setattr(scheduler, 'time', SimpleNamespace(sleep=pause))
    assert scheduler.run_daemon(roots[0], also=[roots[1]], engine='mock', interval=5) == 0
    assert len(passes) >= 4 and len(passes) % 2 == 0
    assert passes == ['first', 'second'] * (len(passes) // 2)
    assert sorted(calls) == [('first', 'healthy'), ('second', 'healthy'), ('second', 'held')]
    assert all(scheduler.lock_holder(root) is None for root in roots)
    text = capsys.readouterr().out
    assert 'job a/held (agent)' in text and 'held' in text
    assert 'changed after approval' in text


def test_daemon_tolerates_missing_diagnostic_fields(tmp_path, monkeypatch, isolated, capsys):
    root = realm(tmp_path/'realm')
    passes = []
    def tick(*a, **kw):
        passes.append(1)
        return [{'agent': 'a', 'job': 'held', 'status': 'held', 'detail': 'Review required'}, {}]
    monkeypatch.setattr(scheduler, 'tick', tick)
    def pause(_):
        if len(passes) == 2: raise KeyboardInterrupt
        scheduler._work_changed.set()
    monkeypatch.setattr(scheduler, 'time', SimpleNamespace(sleep=pause))
    assert scheduler.run_daemon(root, engine='mock', interval=5) == 0
    assert len(passes) == 2
    assert '(unknown)' in capsys.readouterr().out
