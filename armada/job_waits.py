"""Durable pre-execution waits. Waiting owns no provider, worker or invocation lock."""
import datetime as dt
import hashlib
from pathlib import Path
import time

from . import util, job_rules


def _path(root):
    key = hashlib.sha256(str(Path(root).resolve()).casefold().encode()).hexdigest()
    return util.data_dir() / 'job-waits' / (key + '.json')


def state(root):
    return util.read_json_state(_path(root), default=dict)


def pending(root, agent, job):
    row = state(root).get(agent + '/' + job, {})
    return row if row.get('state') in ('waiting', 'ready', 'queued') else None


def _save(root, key, row):
    with util.file_lock(_path(root)):
        data = state(root)
        data[key] = row
        util.write_json_atomic(_path(root), data)
        util.write_json_atomic(Path(root) / 'job-waits.json', data)


def bounds(job, fire):
    start = fire
    window = job.get('start_window')
    if window:
        hour, minute = map(int, window['from'].split(':'))
        start = fire.replace(hour=hour, minute=minute, second=0, microsecond=0)
        hour, minute = map(int, window['until'].split(':'))
        end = start.replace(hour=hour, minute=minute)
        if end <= start:
            end += dt.timedelta(days=1)
    else:
        end = start + dt.timedelta(minutes=job.get('start_deadline_minutes', 90))
    connector_end = start + dt.timedelta(minutes=job.get('start_deadline_minutes', 90))
    return start, end, min(end, connector_end)


def _finish_time(report):
    try:
        stamp = dt.datetime.fromisoformat(report.get('finished_at') or report['ts'])
        return stamp.timestamp() if stamp.tzinfo else None
    except (KeyError, TypeError, ValueError, OverflowError):
        return None


def dependency_errors(root, job, now):
    from . import job_history, execution_admission, run_activity
    errors = []
    reports_by_agent = {}
    def reports(agent):
        if agent not in reports_by_agent:
            reports_by_agent[agent] = job_history.reports(Path(root)/'agents'/agent)
        return reports_by_agent[agent]
    from . import job_triggers
    fallback_agents = {r['agent'] for r in job_triggers.history(root) if r.get('fallback_for')}
    for dependency in job.get('after', []):
        agent, jid = job_rules.reference(dependency)
        path = Path(root) / 'agents' / agent
        # Any active newer invocation supersedes older successful data.
        marker = path / 'runs' / '.running' / (jid + '.json')
        if (execution_admission.view(root, agent, job_history.thread_name(jid))
                or marker.exists() and run_activity.marker_live(marker, util.read_json_state(marker))):
            errors.append(f'{agent}/{jid} is still running or queued')
            continue
        rows = [r for r in reports(agent) if r.get('task') == jid]
        # Successful fallback reports are linked to the original invocation by Armada.
        rows += [r for aid in fallback_agents for r in reports(aid)
                 if (r.get('fallback_for') or {}).get('agent') == agent
                 and (r.get('fallback_for') or {}).get('job') == jid]
        finished = [(stamp, row) for row in rows if (stamp := _finish_time(row)) is not None and stamp <= now]
        latest = max(finished, key=lambda pair: pair[0], default=None)
        if latest and latest[1].get('status') in dependency.get('outcome', ['ok', 'warn']) and now-latest[0] <= dependency.get('max_age_minutes', 60)*60:
            continue
        detail = (latest[1].get('summary') or latest[1].get('status', 'unknown')) if latest else 'no completed run'
        if latest and latest[1].get('status') in ('ok', 'warn'):
            detail = 'the last successful result is too old'
        errors.append(f'{agent}/{jid}: {detail}')
    return errors


def evaluate(root, agent, job, fire, now, *, provider, refresh=True, request_id=''):
    """Return ready/waiting/failed; a terminal wait never silently opens again."""
    from . import run_policy, job_access, connector_health
    if not any(job.get(k) for k in ('after', 'requires_connectors', 'start_window')):
        return {'state': 'ready', 'reason': ''}
    run_policy.verify_job(root, agent, job)
    start, end, connector_end = bounds(job, fire)
    key = agent + '/' + job['id'] + ('/' + request_id if request_id else '')
    fingerprint = job_access.fingerprint(job)
    previous = state(root).get(key, {})
    same = previous.get('fire') == fire.isoformat()
    if same and previous.get('fingerprint') != fingerprint:
        return {'state': 'failed', 'reason': 'Job instructions changed during the start window. Run now after owner review.'}
    if same and previous.get('state') in ('failed', 'cancelled', 'started'):
        return previous
    if not same:
        previous = {'day': fire.date().isoformat(), 'fire': fire.isoformat(), 'since': start.timestamp(),
                    'deadline': end.timestamp(), 'fingerprint': fingerprint, 'notified': False,
                    'agent': agent, 'job': job['id'], 'state': 'waiting', 'health_after': now.timestamp()-300}
    if now < start:
        return {**previous, 'state': 'waiting', 'reason': f'Start window opens at {start:%H:%M}'}
    dependencies = dependency_errors(root, job, now.timestamp())
    connectors = []
    unhealthy = False
    ids = job.get('requires_connectors', [])
    health = connector_health.request(root, provider, ids, max_age=300, not_before=previous['health_after']) if ids and refresh else {
        cid: connector_health.snapshot(root)['connectors'].get(provider+':'+cid, {}) for cid in ids}
    for cid in ids:
        row = health.get(cid, {})
        fresh = row.get('checked_at', 0) >= previous['health_after'] and 0 <= now.timestamp()-row.get('checked_at', 0) < 300
        if not fresh or row.get('state') != 'up':
            unhealthy = unhealthy or (fresh and row.get('state') in ('down', 'missing', 'failed'))
            detail = row.get('reason') or 'Health not verified'
            connectors.append(f'{cid}: ' + (detail if fresh else 'waiting for a fresh connector check; last result: '+detail))
    deadline = now >= end
    connector_expired = bool(connectors) and now >= connector_end
    failure = connector_expired or deadline and job.get('on_window_end', 'fail') == 'fail'
    waiting = bool(connectors or dependencies) and not (deadline and not connectors and job.get('on_window_end') == 'run_anyway')
    reason = '; '.join(connectors + dependencies)
    if failure and not reason:
        reason = 'Prerequisites were not satisfied and execution admitted before the start window closed.'
    row = {**previous, 'state': 'failed' if failure else 'waiting' if waiting else 'ready',
           'reason': reason, 'checked_at': now.timestamp(), 'missing_dependencies': dependencies,
           'missing_connectors': connectors, 'warning': reason if not waiting and reason else ''}
    if failure:
        row['reason'] = f'Start window expired ({start:%H:%M}–{min(end, connector_end) if connector_expired else end:%H:%M}): ' + reason
    from . import notify
    if row['state'] == 'waiting' and not row['notified'] and (unhealthy or now.timestamp()-row['since'] >= (300 if connectors else 900)):
        row['notified'] = True
        notify.emit(root, 'job_wait', f'{job.get("name") or job["id"]} is waiting', reason, f'/agent/{agent}/jobs?job={job["id"]}')
    if row['state'] == 'failed' and previous.get('state') != 'failed':
        notify.emit(root, 'job_wait', f'{job.get("name") or job["id"]} could not start', row['reason'], f'/agent/{agent}/jobs?job={job["id"]}')
    _save(root, key, row)
    return row


def transition(root, agent, jid, status, *, request_id=''):
    key = agent + '/' + jid + ('/' + request_id if request_id else '')
    row = state(root).get(key)
    if not row:
        return
    if status == 'started' and row.get('notified') and row.get('state') != 'started':
        from . import notify
        notify.emit(root, 'job_wait', f'{jid} started after waiting', row.get('reason', ''), f'/agent/{agent}/jobs?job={jid}')
    _save(root, key, {**row, 'state': status, 'updated_at': time.time()})


def context(root, agent, jid):
    row = state(root).get(agent + '/' + jid, {})
    return ('Owner allowed this job to run when its window closed. Unmet prerequisites: ' + row['warning']) if row.get('warning') else ''


def override_warning(root, job, *, provider=''):
    from . import connector_health
    errors = dependency_errors(root, job, time.time())
    rows = connector_health.snapshot(root)['connectors'].values()
    for cid in job.get('requires_connectors', []):
        matched = [r for r in rows if r['id'] == cid and (not provider or r['provider'] == provider)]
        if not any(r.get('state') == 'up' and time.time()-r.get('checked_at',0) <= 300 for r in matched):
            errors.append(f'{cid} has no fresh healthy connector reading')
    return '; '.join(errors)
