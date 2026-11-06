"""Slow synthetic work cannot stop scheduler discovery or independent realms."""
import datetime as dt
import json
import threading
import time

import pytest

from armada import dispatch, execution_admission as admission, preflight, runner
from armada import scheduler, scheduler_state, sysjobs, util
from armada.job_history import thread_name
from armada.request_context import RealmContext, RunContext

AT = dt.datetime(2026, 11, 6, 9, 0)


def realm(tmp_path, name, provider='claude', jobs=1):
    root = tmp_path / name
    ad = root / 'agents/a'
    (ad / 'jobs').mkdir(parents=True)
    util.write_json_atomic(root / 'realm.json', {'schema_version': 2, 'provider': provider})
    util.write_json_atomic(ad / 'agent.json', {'id': 'a'})
    for n in range(jobs):
        util.write_json_atomic(ad / 'jobs' / f'job{n}.json',
                               {'id': f'job{n}', 'schedule': 'daily 09:00', 'prompt': 'synthetic'})
    return root


@pytest.fixture
def isolated(monkeypatch):
    monkeypatch.setattr(preflight, 'hold_reason', lambda *a: '')
    monkeypatch.setattr(sysjobs, 'JOBS', [])


def drain(pool, seconds=15):
    # This checks eventual cleanup, not disk-speed latency. A shared Windows CI
    # runner can take several seconds to flush the five durable job results.
    until = time.monotonic() + seconds
    while (pool.pending or pool.running) and time.monotonic() < until:
        pool.pump()
        time.sleep(.01)
    assert not pool.pending and not pool.running


def test_slow_provider_does_not_occupy_workers_needed_by_another_realm(tmp_path, monkeypatch, isolated):
    roots = [realm(tmp_path, 'slow', jobs=4), realm(tmp_path, 'other', 'gemini')]
    leases = [scheduler_state.acquire(root) for root in roots]
    pool = dispatch.Dispatcher()
    started, finished, release = threading.Event(), threading.Event(), threading.Event()
    calls = []
    def run(root, agent, job, **kw):
        calls.append((root.name, job))
        if root == roots[0]:
            started.set()
            assert release.wait(5)
        else:
            finished.set()
        return {'status': 'ok'}
    monkeypatch.setattr(runner, 'run_job', run)
    try:
        for root, lease in zip(roots, leases):
            records = scheduler.tick(root, at=AT, _lease=lease, _dispatch=pool)
            assert all(r['status'] == 'queued' for r in records)
        assert calls == []  # Discovery never executes on its caller.
        pool.pump()
        assert started.wait(3) and finished.wait(3)
        assert sum(name == 'slow' for name, _ in calls) == 2
        # Another discovery pass does not create or run duplicate attempts.
        scheduler.tick(roots[0], at=AT, _lease=leases[0], _dispatch=pool)
        assert len(pool.pending) == 2
        release.set()
        drain(pool)
        assert len(calls) == len(set(calls)) == 5
    finally:
        release.set()
        pool.close()
        for lease in leases:
            lease.close()


def test_cancel_queued_job_records_stopped_without_launch_or_replay(tmp_path, monkeypatch, isolated):
    root = realm(tmp_path, 'realm')
    lease = scheduler_state.acquire(root)
    pool = dispatch.Dispatcher()
    monkeypatch.setattr(runner, 'run_job', lambda *a, **kw: pytest.fail('cancelled work launched'))
    try:
        scheduler.tick(root, at=AT, _lease=lease, _dispatch=pool)
        identity = RealmContext.capture(root).realm_id
        assert admission.cancel(identity, agent='a', thread=thread_name('job0')) == 1
        pool.pump()
        attempt = scheduler_state.inspect_attempt(root, 'a', 'job0', AT.date().isoformat())
        assert attempt['state'] == 'finished' and attempt['status'] == 'stopped'
        assert scheduler.tick(root, at=AT, _lease=lease, _dispatch=pool) == []
    finally:
        pool.close()
        lease.close()


def test_queue_overflow_does_not_consume_daily_attempt(tmp_path, monkeypatch, isolated):
    root = realm(tmp_path, 'realm', jobs=2)
    lease = scheduler_state.acquire(root)
    pool = dispatch.Dispatcher()
    monkeypatch.setattr(admission, 'PER_REALM_QUEUE', 1)
    try:
        rows = scheduler.tick(root, at=AT, _lease=lease, _dispatch=pool)
        assert [r['status'] for r in rows] == ['queued', 'held']
        assert 'queue is full' in rows[1]['detail']
        assert scheduler_state.inspect_attempt(root, 'a', 'job1', AT.date().isoformat()) is None
    finally:
        pool.close()
        lease.close()


def test_unrecorded_outcome_is_held_not_replayed(tmp_path, monkeypatch, isolated):
    root = realm(tmp_path, 'realm')
    lease = scheduler_state.acquire(root)
    pool = dispatch.Dispatcher()
    calls = []
    monkeypatch.setattr(runner, 'run_job', lambda *a, **kw: calls.append('effect') or {'status': 'ok'})
    def fail(*a):
        raise OSError('injected result write failure')
    try:
        scheduler.tick(root, at=AT, _lease=lease, _dispatch=pool)
        with monkeypatch.context() as m:
            m.setattr(scheduler_state, 'finish', fail)
            drain(pool)
        assert calls == ['effect']
        rows = scheduler.tick(root, at=AT, _lease=lease, _dispatch=pool)
        assert rows[0]['status'] == 'held' and 'no recorded outcome' in rows[0]['detail']
        assert not pool.pending and calls == ['effect']
    finally:
        pool.close()
        lease.close()


def test_update_and_realm_activity_include_queued_tickets(tmp_path, isolated):
    from armada import updater, realmops
    root = realm(tmp_path, 'realm')
    ticket = admission.Ticket(RunContext.capture(root, 'a', 'queued'), 'codex')
    try:
        assert any('queued' in row['label'] for row in updater.pending_work())
        assert realmops.busy(root)
    finally:
        ticket.close()


def test_slow_maintenance_does_not_block_owner_jobs(tmp_path, monkeypatch, isolated):
    root = realm(tmp_path, 'realm')
    lease = scheduler_state.acquire(root)
    pool = dispatch.Dispatcher()
    release, started, job_done = threading.Event(), threading.Event(), threading.Event()
    monkeypatch.setattr(sysjobs, 'JOBS', [{'id': 'test'}])
    monkeypatch.setattr(sysjobs, 'due', lambda *a: True)
    def maintenance(*a):
        started.set()
        assert release.wait(5)
        return {'ok': True}
    monkeypatch.setattr(sysjobs, 'run_one', maintenance)
    monkeypatch.setattr(runner, 'run_job', lambda *a, **k: job_done.set() or {'status': 'ok'})
    try:
        scheduler.tick(root, at=AT, _lease=lease, _dispatch=pool)
        pool.pump()
        assert started.wait(3) and job_done.wait(3)
    finally:
        release.set()
        pool.close()
        lease.close()


def test_manual_job_waits_without_holding_admitted_scheduler_invocation_lock(tmp_path, monkeypatch, isolated):
    root = realm(tmp_path, 'realm')
    context = RunContext.capture(root, 'a', thread_name('job0'))
    ticket = admission.Ticket(context, 'mock')
    calls = []
    monkeypatch.setattr(runner, '_run_job_series', lambda *args: calls.append(threading.current_thread().name) or {'status': 'ok'})
    worker = threading.Thread(name='manual-request', target=lambda: runner.run_job(root, 'a', 'job0'))
    worker.start()
    try:
        until = time.monotonic() + 4
        while len(admission.snapshot()) < 2 and time.monotonic() < until:
            time.sleep(.02)
        assert len(admission.snapshot()) == 2 and ticket.ready()
        with ticket.activate():
            runner.run_job(root, 'a', 'job0')
        assert len(calls) == 1 and calls[0] != 'manual-request'
        ticket.close()
        worker.join(5)
        assert not worker.is_alive() and calls[1] == 'manual-request'
    finally:
        ticket.close()
        worker.join(5)


def test_update_pause_withdraws_queued_attempts_instead_of_deadlocking_restart(tmp_path, monkeypatch, isolated):
    from armada import updater
    root = realm(tmp_path, 'realm')
    paused = False
    monkeypatch.setattr(updater, 'admission_paused', lambda: paused)
    monkeypatch.setattr(updater, 'installed', lambda: False)
    monkeypatch.setattr(scheduler, '_update_wanted', lambda: False)
    monkeypatch.setattr(admission.Ticket, 'ready', lambda self: False)
    original = scheduler.tick
    monkeypatch.setattr(scheduler, 'tick', lambda *a, **kw: original(*a, at=AT, **kw))
    def sleep(_):
        nonlocal paused
        if paused:
            raise KeyboardInterrupt
        paused = True
    monkeypatch.setattr(scheduler.time, 'sleep', sleep)
    assert scheduler.run_daemon(root, engine='mock', interval=5) == 0
    attempt = scheduler_state.inspect_attempt(root, 'a', 'job0', AT.date().isoformat())
    assert attempt['status'] == 'stopped' and attempt['state'] == 'finished'
    assert admission.snapshot() == [] and scheduler_state.holder(root) is None


def test_bounded_stress_drains_all_realms_without_exceeding_execution_limits(tmp_path, isolated):
    roots = [realm(tmp_path, f'realm{n}') for n in range(8)]
    pool = dispatch.Dispatcher()
    guard = threading.Lock()
    active, completed, errors = [], [], []
    providers = ['claude', 'codex', 'gemini', 'command']
    def work(identity, provider, item):
        with guard:
            active.append((identity, provider, item))
            if (len(active) > 4 or sum(p == provider for _, p, _ in active) > 2
                    or sum(r == identity for r, _, _ in active) > 2):
                errors.append(list(active))
        time.sleep(.005)
        with guard:
            completed.append(item)
            active.remove((identity, provider, item))
    try:
        for n in range(64):
            context = RunContext.capture(roots[n % 8], 'a', f'work{n}')
            provider = providers[(n // 8) % 4]
            pool.submit(context, provider, lambda c=context, p=provider, n=n:
                (lambda: work(c.realm.realm_id, p, n), lambda reason: errors.append(reason)))
        drain(pool, seconds=15)
        assert not errors and len(completed) == len(set(completed)) == 64
        assert admission.snapshot() == []
    finally:
        pool.close()


@pytest.mark.parametrize('journal_error', [False, True])
def test_stopping_restored_retry_cannot_resurrect_its_old_backoff(tmp_path, monkeypatch, isolated, journal_error):
    from armada import job_retries
    root = realm(tmp_path, 'realm')
    lease = scheduler_state.acquire(root)
    pool = dispatch.Dispatcher()
    journal_path = job_retries.state_path(root, 'a', 'job0')
    util.write_json_atomic(journal_path, {
        'schema_version': 1, 'state': 'waiting', 'series_id': 'previous-series',
        'attempts': [{'run_id': 'previous'}], 'max_retries': 1,
        'started_at': AT.timestamp(), 'next_at': AT.timestamp() + 30,
        'last_report': {'status': 'error', 'result': {'execution': 'failed'}}})
    attempt, _ = scheduler_state.claim(lease, 'a', 'job0', AT.date().isoformat())
    scheduler_state.finish(lease, attempt, 'error')
    monkeypatch.setattr(runner, 'run_job', lambda *a, **kw: pytest.fail('Stopped retry was launched'))
    try:
        assert scheduler.tick(root, at=AT, _lease=lease, _dispatch=pool)[0]['status'] == 'queued'
        if journal_error:
            def fail(*a):
                raise OSError('injected retry journal write failure')
            monkeypatch.setattr(job_retries, 'cancel_waiting', fail)
        admission.cancel(RealmContext.capture(root).realm_id, agent='a', thread=thread_name('job0'))
        pool.pump()
        rows = scheduler.tick(root, at=AT, _lease=lease, _dispatch=pool)
        assert not pool.pending
        assert scheduler_state.inspect_attempt(root, 'a', 'job0', AT.date().isoformat())['status'] == 'stopped'
        if journal_error:
            assert rows[0]['status'] == 'held' and 'stopped' in rows[0]['detail']
        else:
            assert rows == [] and job_retries.pending(root, 'a', 'job0') is None
            # Stopping today's retry must not disable tomorrow's independently due job.
            tomorrow = AT + dt.timedelta(days=1)
            assert scheduler.tick(root, at=tomorrow, _lease=lease, _dispatch=pool)[0]['status'] == 'queued'
    finally:
        pool.close()
        lease.close()
