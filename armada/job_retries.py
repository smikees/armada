"""Bounded job retries with durable attempt evidence and conservative replay rules."""
from __future__ import annotations
import copy
import datetime as dt
import math
import re
import time
import uuid
from pathlib import Path
from . import util

BACKOFF = (30, 60, 120)


def count(job):
    if 'retries' in job:
        return validate(job['retries'])
    # Preserve the specific legacy choice, not the editor's old invented default.
    match = re.fullmatch(r'Retry\s*[×x]?\s*([0-3])(?:, then alert me)?',
                         str(job.get('on_failure', '')).strip(), re.I)
    return int(match[1]) if match else 0


def validate(value):
    if type(value) is not int or value not in range(4):
        raise ValueError('Retries must be 0, 1, 2 or 3.')
    return value


def retryable(report):
    result = report.get('result') or {}
    execution = result.get('execution')
    if result.get("startup_failure") or report.get('engine') == 'unknown' or result.get('detail_level') == 'unstructured':
        # Admission/configuration failures and malformed terminal results cannot
        # establish which side effects occurred. Do not burn retries on them.
        return False
    if execution not in ('failed', 'timed_out'):
        return False
    # An audit warning is not an execution failure; ambiguous or already-sent
    # delivery needs reconciliation, not another invocation of the whole job.
    delivery = result.get('delivery', [])
    if any(d.get('status') in ('sent', 'unknown') for d in delivery):
        return False
    if any(r.get('status') == 'sent' for r in result.get('evidence', {}).get('delivery_receipts', [])):
        return False
    return True


def state_path(root, agent, job):
    return Path(root) / 'agents' / agent / 'runs' / 'retries' / f'{job}.json'


def pending(root, agent, job):
    data = util.read_json_state(state_path(root, agent, job), default=dict)
    return _waiting(data)


def _waiting(data):
    if not isinstance(data, dict):
        raise util.StateError('Invalid retry journal; inspect before retrying.')
    if data.get('state') != 'waiting':
        return None
    try:
        if (data['schema_version'] != 1 or not isinstance(data['attempts'], list)
                or not 1 <= len(data['attempts']) <= validate(data['max_retries'])
                or not isinstance(data['last_report'], dict) or not retryable(data['last_report'])):
            raise ValueError('Unsafe retry state')
        for key in ('started_at', 'next_at'):
            if type(data[key]) not in (int, float) or not math.isfinite(data[key]):
                raise ValueError('Invalid retry time')
            dt.datetime.fromtimestamp(data[key])
    except (KeyError, TypeError, ValueError, AttributeError, OSError, OverflowError) as exc:
        raise util.StateError('Invalid or unsafe retry journal; inspect before retrying.') from exc
    return data


def execute(root, agent, job_id, job, run, *, sleep=time.sleep, clock=time.time):
    """One logical invocation, including retries. Unknown crash outcomes stay held.

    A waiting journal is safe to resume after restart: the previous attempt already
    finished and passed replay checks. A running journal is deliberately not resumed.
    """
    from . import realmops
    path = state_path(root, agent, job_id)
    # Also prevents overlapping manual/automatic invocations of this job.
    with util.file_lock(path, timeout=.05):
        previous = util.read_json_state(path, default=dict)
        resume = _waiting(previous) is not None
        journal = previous if resume else {'schema_version': 1, 'series_id': uuid.uuid4().hex,
            'attempts': [], 'max_retries': count(job), 'started_at': clock()}
        maximum = min(journal['max_retries'], count(job))
        while True:
            if resume:
                # Bounded slices let disabling/archiving a job stop a queued retry.
                while clock() < journal['next_at']:
                    current = util.read_json_state(Path(root)/'agents'/agent/'jobs'/f'{job_id}.json')
                    if current.get('enabled') is False or realmops.archived(root) or len(journal['attempts']) > count(current):
                        journal.update(state='cancelled', reason='Retry cancelled by current job or realm settings.')
                        util.write_json_atomic(path, journal)
                        return journal['last_report']
                    sleep(min(1, journal['next_at']-clock()))
                current = util.read_json_state(Path(root)/'agents'/agent/'jobs'/f'{job_id}.json')
                if current.get('enabled') is False or realmops.archived(root) or len(journal['attempts']) > count(current):
                    journal.update(state='cancelled', reason='Retry cancelled by current job settings.')
                    util.write_json_atomic(path, journal)
                    return journal['last_report']
            attempt_job = copy.deepcopy(job)
            attempt_job["_retry_series"] = {"series_id": journal["series_id"],
                "attempt": len(journal["attempts"])+1, "max_retries": maximum,
                "started_at": journal["started_at"]}
            # Keep approved instructions byte-for-byte: grants are bound to this
            # prompt. The dedicated job thread already retains previous attempts.
            journal.update(state='running', next_at=None)
            util.write_json_atomic(path, journal)  # admission before side effects
            try:
                report = run(attempt_job)
            except BaseException:
                journal.update(state='uncertain', reason='Execution raised before a terminal report; automatic replay held.')
                util.write_json_atomic(path, journal)
                raise
            journal['attempts'].append({'run_id': report.get('run_id'), 'status': report.get('status'),
                                        'summary': report.get('summary'), 'finished_at': clock()})
            journal['last_report'] = report
            if len(journal['attempts']) > maximum or not retryable(report):
                journal.update(state='finished', finished_at=clock())
                util.write_json_atomic(path, journal)
                return report
            journal.update(state='waiting', next_at=clock()+BACKOFF[len(journal['attempts'])-1])
            util.write_json_atomic(path, journal)
            resume = True
