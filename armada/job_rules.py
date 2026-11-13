"""Validated, owner-approved prerequisites for unattended jobs; no execution here."""
from pathlib import Path
import re

FIELDS = ('requires_connectors', 'start_deadline_minutes', 'start_window', 'after',
          'on_window_end', 'retry_backoff_seconds', 'fallback_job', 'secrets',
          'coordinator_may_start', 'coordinator_daily_cap')
SEALED = (*FIELDS, 'schedule', 'cron', 'run', 'command', 'retries')


def cadence(job):
    """Present a window's opening time while preserving its scheduled days."""
    schedule = job.get('schedule') or job.get('cron') or 'manual'
    window = job.get('start_window')
    if not window or schedule == 'manual':
        return schedule
    from .scheduler import is_cron, parse_schedule
    if is_cron(schedule):
        parts = schedule.split()
        hour, minute = window['from'].split(':')
        return ' '.join([str(int(minute)), str(int(hour)), *parts[2:]])
    return schedule.rsplit(' ', 1)[0]+' '+window['from'] if parse_schedule(schedule) else schedule


def reference(value):
    from .util import safe_seg
    if not isinstance(value, dict) or not value.get('agent') or not value.get('job'):
        raise ValueError('Each job reference needs an agent and job ID.')
    return safe_seg(value['agent'], 'agent'), safe_seg(value['job'], 'job')


def validate(job):
    """Reject ambiguous windows, unbounded waits and malformed automation controls."""
    for key in ('requires_connectors', 'secrets'):
        values = job.get(key, [])
        if not isinstance(values, list) or len(values) > 50 or any(
                not isinstance(v, str) or not re.fullmatch(r'[^\x00-\x1f]{1,200}', v) for v in values):
            raise ValueError(f'{key} must be a list of connector or secret IDs.')
        if len(values) != len(set(values)):
            raise ValueError(f'{key} contains duplicates.')
    if job.get('secrets') and job.get('kind') != 'command':
        raise ValueError('Only command jobs can receive named secrets.')
    if any(not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', name) for name in job.get('secrets', [])):
        raise ValueError('Secret names use lowercase letters, numbers and underscores.')
    if 'start_deadline_minutes' in job:
        value = job['start_deadline_minutes']
        if type(value) is not int or not 1 <= value <= 1440:
            raise ValueError('Start deadline must be between 1 and 1440 minutes.')
    window = job.get('start_window')
    if window is not None:
        if (not isinstance(window, dict) or set(window) != {'from', 'until'}
                or any(not isinstance(v, str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', v)
                       for v in window.values()) or window['from'] == window['until']):
            raise ValueError('Start window needs different from and until times in HH:MM format.')
    if job.get('on_window_end', 'fail') not in ('fail', 'run_anyway'):
        raise ValueError('At the window end choose fail or run_anyway.')
    dependencies = job.get('after', [])
    if not isinstance(dependencies, list) or len(dependencies) > 50:
        raise ValueError('Dependencies must be a list of at most 50 jobs.')
    seen = set()
    for dependency in dependencies:
        identity = reference(dependency)
        if identity in seen:
            raise ValueError('A dependency is listed more than once.')
        seen.add(identity)
        if set(dependency) - {'agent', 'job', 'outcome', 'max_age_minutes'}:
            raise ValueError('Unknown dependency field.')
        outcomes = dependency.get('outcome', ['ok', 'warn'])
        if not isinstance(outcomes, list) or not outcomes or any(v not in ('ok', 'warn') for v in outcomes):
            raise ValueError('Accepted dependency outcomes are ok and warn.')
        age = dependency.get('max_age_minutes', 60)
        if type(age) is not int or not 1 <= age <= 10080:
            raise ValueError('Dependency freshness must be 1 to 10080 minutes.')
    if job.get('fallback_job') is not None:
        reference(job['fallback_job'])
        if set(job['fallback_job']) != {'agent', 'job'}:
            raise ValueError('A fallback job takes only agent and job IDs.')
    if 'coordinator_may_start' in job and type(job['coordinator_may_start']) is not bool:
        raise ValueError('Coordinator permission must be true or false.')
    if 'coordinator_daily_cap' in job and (type(job['coordinator_daily_cap']) is not int
                                         or not 1 <= job['coordinator_daily_cap'] <= 100):
        raise ValueError('Coordinator daily cap must be between 1 and 100.')
    if 'retry_backoff_seconds' in job:
        from .job_retries import backoff
        backoff(job)


def validate_graph(root, agent, job):
    """Check proposed dependency/fallback edges against the complete saved graph."""
    from . import records
    validate(job)
    current = (agent, job['id'])
    graph = {current: job}
    active, done = set(), set()
    def visit(identity):
        if identity in active:
            raise ValueError('Job dependencies and fallbacks cannot contain a cycle.')
        if identity in done:
            return
        if identity not in graph:
            path = Path(root)/'agents'/identity[0]/'jobs'/(identity[1]+'.json')
            if not path.is_file():
                raise ValueError(f'Referenced job {identity[0]}/{identity[1]} does not exist.')
            graph[identity] = records.read(path, 'job')
        active.add(identity)
        item = graph[identity]
        for ref in [*item.get('after', []), *([item['fallback_job']] if item.get('fallback_job') else [])]:
            visit(reference(ref))
        active.remove(identity)
        done.add(identity)
    visit(current)
    if job.get('requires_connectors'):
        from . import capabilities
        allowed = capabilities.execution_policy(root, agent).allowed_mcp_ids
        unknown = set(job['requires_connectors']) - set(allowed)
        if unknown:
            raise ValueError('Required connectors must already be granted to this agent: ' + ', '.join(sorted(unknown)))
