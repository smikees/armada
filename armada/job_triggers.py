"""Audited, bounded requests to run sealed jobs; never accepts execution instructions."""
import datetime as dt
import hashlib
import os
from pathlib import Path
import threading
import uuid
from . import util

_workers = threading.BoundedSemaphore(16)
_wait_for_health = threading.Event().wait


def _path(root):
    key = hashlib.sha256(str(Path(root).resolve()).casefold().encode()).hexdigest()
    return util.data_dir() / 'job-triggers' / (key + '.json')


def history(root):
    rows = util.read_json_state(_path(root), default=lambda: {'requests': []})['requests']
    return [{**row, 'state': 'interrupted', 'error': 'The requesting process stopped; review before using Run now.'}
            if row.get('state') in ('queued', 'running') and not util.pid_alive(row.get('owner_pid', 0))
            else row for row in rows]


def _update(root, identity, **values):
    with util.file_lock(_path(root)):
        rows = history(root)
        for row in rows:
            if row['id'] == identity:
                row.update(values)
        util.write_json_atomic(_path(root), {'requests': rows})


def active(root, agent, job):
    return any(r['agent'] == agent and r['job'] == job and r['state'] in ('queued', 'running')
               and util.pid_alive(r.get('owner_pid', 0)) for r in history(root))


def validate_coordinator(root, agent, job, coordinator):
    """Recheck owner authorization both at request time and after admission queues."""
    from . import records, run_policy, job_access
    records.admit_agent(root, coordinator)
    if not records.read(Path(root)/'agents'/coordinator/'agent.json', 'agent').get('coordinator'):
        raise ValueError('Only the realm coordinator may request a job run.')
    if not job.get('coordinator_may_start'):
        raise ValueError('The owner has not allowed coordinator starts for this job.')
    grants = run_policy._read().get('coordinator_starters', {})
    if coordinator not in grants.get(job_access.identity(root, agent, job['id']), []):
        raise ValueError('The owner must approve this coordinator for the job. Review and save its coordinator permission.')


def prerequisites(root, job, request):
    """Automatic fallback starts obey their own approved prerequisites and deadline."""
    from . import job_waits, scheduler, run_policy, job_access
    from .engine.selection import engine_for
    if not job.get('enabled', True) or job_access.fingerprint(job) != request['fingerprint']:
        raise ValueError('The approved fallback job changed or was disabled while waiting.')
    run_policy.verify_job(root, request['agent'], job)
    return job_waits.evaluate(root, request['agent'], job, dt.datetime.fromisoformat(request['at']),
        scheduler.now_in(util.read_json_state(Path(root)/'realm.json')),
        provider=engine_for(root, request['agent'], job), request_id=request['id'])


def wait_for_prerequisites(root, request):
    from . import records, realmops, updater
    while True:
        realmops.assert_active(root)
        if updater.installed() and updater.apply_requested():
            raise ValueError('Update preparation interrupted the fallback wait; review before using Run now.')
        current = records.read(Path(root)/'agents'/request['agent']/'jobs'/(request['job']+'.json'), 'job')
        current.setdefault('id', request['job'])
        ready = prerequisites(root, current, request)
        _update(root, request['id'], wait_reason=ready.get('reason', ''))
        if ready['state'] == 'ready':
            return ready.get('warning', '')
        if ready['state'] != 'waiting':
            raise ValueError(ready.get('reason') or 'Fallback start was cancelled.')
        # A bounded control worker waits here; no execution ticket or lock is held.
        _wait_for_health(5)


def enqueue(root, agent, jid, reason, *, coordinator='', fallback_for=None):
    from . import records, run_policy, job_access, job_rules, execution_admission, job_history, run_activity, scheduler
    root = Path(root)
    agent, jid = job_rules.reference({'agent': agent, 'job': jid})
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise ValueError('Provide a reason of 1 to 1000 characters.')
    if not coordinator and not fallback_for:
        raise ValueError('A coordinator or approved fallback is required.')
    if coordinator:
        coordinator = util.safe_seg(coordinator, 'coordinator')
        records.admit_agent(root, coordinator)
        if not records.read(root/'agents'/coordinator/'agent.json', 'agent').get('coordinator'):
            raise ValueError('Only the realm coordinator may request a job run.')
    job = records.read(root/'agents'/agent/'jobs'/(jid+'.json'), 'job')
    job.setdefault('id', jid)
    if not job.get('enabled', True) or not run_policy.verify_job(root, agent, job):
        raise ValueError('The target job must be enabled and approved by the owner.')
    if coordinator:
        validate_coordinator(root, agent, job, coordinator)
    job_rules.validate_graph(root, agent, job)
    now = scheduler.now_in(util.read_json_state(root/'realm.json'))
    marker = root/'agents'/agent/'runs'/'.running'/(jid+'.json')
    with util.file_lock(_path(root)):
        rows = history(root)
        if (active(root, agent, jid) or execution_admission.view(root, agent, job_history.thread_name(jid))
                or marker.exists() and run_activity.marker_live(marker, util.read_json_state(marker))):
            raise ValueError('This job is already running or queued.')
        if coordinator:
            today = [r for r in rows if r.get('coordinator') and r['day'] == now.date().isoformat()]
            cap = run_policy.settings(root).get('coordinator_daily_cap', 6)
            if len(today) >= cap or sum(r['agent'] == agent and r['job'] == jid for r in today) >= job.get('coordinator_daily_cap', 2):
                raise ValueError('The coordinator daily start allowance has been used.')
        if fallback_for and any(r.get('fallback_for', {}).get('run_id') == fallback_for['run_id'] for r in rows):
            raise ValueError('A fallback was already requested for this invocation.')
        row = {'id': uuid.uuid4().hex, 'agent': agent, 'job': jid, 'day': now.date().isoformat(),
               'at': now.isoformat(), 'reason': reason.strip(), 'coordinator': coordinator,
               'fallback_for': fallback_for or {}, 'fingerprint': job_access.fingerprint(job),
               'state': 'queued', 'owner_pid': os.getpid()}
        rows.append(row)
        util.write_json_atomic(_path(root), {'requests': rows})
    run_policy.audit('request-job-start', root, **row)
    from . import notify
    notify.emit(root, 'coordinator_job', f'{jid} queued', reason, f'/agent/{agent}/jobs?job={jid}')
    def work():
        from . import runner
        try:
            from . import job_waits
            from .engine.selection import engine_for
            warning = (wait_for_prerequisites(root, row) if row.get('fallback_for') else
                       job_waits.override_warning(root, job, provider=engine_for(root, agent, job)))
            result = runner.run_job(root, agent, jid, engine=None, trigger=row, override_reason=warning)
            _update(root, row['id'], state='finished', status=result.get('status'), run_id=result.get('run_id'))
        except BaseException as exc:
            import logging
            from .connector_health import public_error
            message = public_error(exc)
            logging.getLogger(__name__).warning('Requested job could not start: %s', message)
            _update(root, row['id'], state='failed', error=message)
            notify.emit(root, 'job_failed', f'{jid} could not start', message, f'/agent/{agent}/jobs?job={jid}')
        finally:
            try:
                from . import job_waits
                if row.get('fallback_for'):
                    job_waits.transition(root, agent, jid, 'finished', request_id=row['id'])
            finally:
                _workers.release()
                scheduler._work_changed.set()
    if not _workers.acquire(blocking=False):
        _update(root, row['id'], state='failed', error='The job request queue is full.')
        raise ValueError('The job request queue is full. Try again later.')
    try:
        threading.Thread(target=work, name='armada-job-trigger', daemon=True).start()
    except BaseException:
        _workers.release()
        _update(root, row['id'], state='failed', error='Could not start the worker.')
        raise
    return {'ok': True, 'state': 'queued', 'request_id': row['id']}


def fallback(root, agent, job, report):
    from . import job_retries, run_policy, job_access
    target = job.get('fallback_job')
    if not target or not job_retries.retryable(report) or not report.get('run_id'):
        return None
    if report.get('job_fingerprint') and report['job_fingerprint'] != job_access.fingerprint(job):
        raise ValueError('The job changed while queued; its fallback must be reviewed before another run.')
    if not run_policy.verify_job(root, agent, job):
        return None
    return enqueue(root, target['agent'], target['job'], f'Fallback after {agent}/{job["id"]} failed.',
                   fallback_for={'agent': agent, 'job': job['id'], 'run_id': report['run_id']})


def report_fields(job):
    from .job_access import fingerprint
    trigger = job.get('_trigger', {})
    extra = {'job_fingerprint': fingerprint(job)} if job.get('id') else {}
    if job.get('_prerequisite_override'):
        extra['prerequisite_override'] = job['_prerequisite_override']
    if not trigger:
        return extra
    return {**extra, 'trigger': {k: trigger[k] for k in ('id', 'coordinator', 'reason')},
            **({'fallback_for': trigger['fallback_for']} if trigger.get('fallback_for') else {})}
