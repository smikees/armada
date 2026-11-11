"""Machine-local owner choices, approval seals and fail-closed API reservations.

Realm-authored files are never authority for spending, fallback or priority grants.
No credentials are stored in this module's policy or accounting files.
"""
import calendar
import datetime as dt
import math
from pathlib import Path
from . import util

JOB_FIELDS = ('timeout', 'plan_limit_action', 'connector_limit_action', 'critical', 'api_model', 'api_run_ceiling_usd')
ACTIONS = ('api', 'wait', 'fail')


def _path():
    return util.data_dir() / 'run-policy.json'


def _read():
    return util.read_json_state(_path(), default=lambda: {'providers': {}, 'scopes': {}, 'jobs': {}})


def scope_id(root, agent=''):
    return str(Path(root).resolve()).casefold() + ('|' + agent if agent else '')


def validate_job(job):
    value = job.get('timeout')
    if value not in (None, '') and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0):
        raise ValueError('Time limit must be a positive number of seconds, or empty for No limit.')
    for field in ('plan_limit_action', 'connector_limit_action'):
        if job.get(field) not in (None, '', *ACTIONS) or field == 'connector_limit_action' and job.get(field) == 'api':
            raise ValueError('Choose use API key, wait for reset, or fail; unavailable connectors may only wait or fail.')
    if 'critical' in job and type(job['critical']) is not bool:
        raise ValueError('Critical must be true or false.')
    if job.get('api_run_ceiling_usd') not in (None, ''):
        _positive(job['api_run_ceiling_usd'], 'API per-run ceiling')
    if job.get('api_model') and not str(job['api_model']).startswith(('claude-', 'Claude ', 'opus', 'sonnet', 'haiku', 'fable')):
        raise ValueError('Choose a Claude model for the Claude API lane.')


def _positive(value, name):
    if isinstance(value, bool):
        raise ValueError(f'{name} must be a finite positive number.')
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f'{name} must be a finite positive number.')
    return number


def seal_job(root, agent, job):
    from .job_access import identity, fingerprint
    validate_job(job)
    with util.file_lock(_path()):
        state = _read()
        state.setdefault('jobs', {})[identity(root, agent, job['id'])] = fingerprint(job)
        util.write_json_atomic(_path(), state)
    audit('approve-job-controls', root, agent=agent, job=job['id'], values={k: job.get(k) for k in JOB_FIELDS})


def verify_job(root, agent, job):
    from .job_access import identity, fingerprint
    validate_job(job)
    state=_read()
    seal = state.get('jobs', {}).get(identity(root, agent, job.get('id', '')))
    if seal and seal != fingerprint(job):
        raise ValueError('Job instructions or run controls changed after approval. Review and save the job before running.')
    imported=scope_id(root) in state.get('legacy_imported', [])
    if not seal and (any(job.get(k) for k in JOB_FIELDS if k != 'timeout') or imported and job.get('timeout')):
        raise ValueError('The owner must approve time limits, fallback and critical-job controls in Jobs before this job runs.')
    return bool(seal)


def import_legacy(root):
    """Once on upgrade, preserve existing owner ceilings without changing job files."""
    from .job_access import identity, fingerprint
    from . import appconfig
    import hashlib
    import json
    identity_root = scope_id(root)
    grant_updates = []
    with util.file_lock(_path()):
        state = _read()
        imported = state.setdefault('legacy_imported', [])
        if identity_root in imported:
            return
        realm = util.read_json_state(Path(root)/'realm.json', default=dict)
        ceiling = realm.get('default_job_timeout')
        if type(ceiling) in (int, float) and math.isfinite(ceiling) and ceiling > 0:
            state.setdefault('scopes', {}).setdefault(identity_root, {}).setdefault('default_job_timeout', ceiling)
        for path in sorted((Path(root)/'agents').glob('*/jobs/*.json')):
            try:
                job = util.read_json_state(path)
                legacy_id = job.get('id')
                job.setdefault('id', path.stem)
                validate_job(job)
                if any(job.get(k) for k in JOB_FIELDS if k != 'timeout'):
                    continue  # New controls never acquire approval through legacy import.
            except (OSError, ValueError):
                continue  # A damaged job retains its individual repair/hold state.
            state.setdefault('jobs', {}).setdefault(identity(root, path.parent.parent.name, path.stem), fingerprint(job))
            old = {key:job.get(key) for key in ('id','kind','prompt','allow_tools')}
            old['id'] = legacy_id
            old_hash = hashlib.sha256(json.dumps(old,sort_keys=True,ensure_ascii=False).encode('utf-8')).hexdigest()
            grant_updates.append((identity(root,path.parent.parent.name,path.stem),old_hash,fingerprint(job)))
        imported.append(identity_root)
        util.write_json_atomic(_path(), state)
    def upgrade_grants(config):
        for key,old_hash,new_hash in grant_updates:
            entry = config.get('job_access',{}).get(key)
            if isinstance(entry,dict) and entry.get('fingerprint') == old_hash:
                entry['fingerprint'] = new_hash
    if grant_updates:
        util.mutate_json(appconfig._path(),upgrade_grants,default=dict)
    audit('import-existing-job-controls', root)


def settings(root=None, agent='', job=None, provider='claude'):
    state = _read()
    from .provider_keys import configured
    result = {'plan_limit_action': 'api' if configured(provider) else 'fail', 'connector_limit_action': 'fail',
              'monthly_cap_usd': 100, 'cycle_day': 1, 'reserve_percent': 30, 'api_run_ceiling_usd': 5,
              'agent_inactivity_minutes': 30, 'agent_soft_mark_minutes': 60, 'critical_usage_percent': 80,
              'critical': False, 'api_model': '', 'default_job_timeout':None}
    result.update(state.get('providers', {}).get(provider, {}))
    if root:
        scopes = state.get('scopes', {})
        for identity in (scope_id(root), scope_id(root, agent)) if agent else (scope_id(root),):
            result.update(scopes.get(identity, {}))
        if job and verify_job(root, agent, job):
            result.update({k: job[k] for k in JOB_FIELDS if job.get(k) not in (None, '')})
    return result


def save(root, values, *, provider='claude', agent='', global_provider=False):
    allowed = {'plan_limit_action', 'connector_limit_action', 'api_model', 'api_run_ceiling_usd',
               'agent_inactivity_minutes', 'agent_soft_mark_minutes', 'critical_usage_percent'}
    if global_provider:
        allowed |= {'monthly_cap_usd', 'cycle_day', 'reserve_percent'}
    elif not agent:
        allowed.add('default_job_timeout')
    clean = {k: v for k, v in values.items() if k in allowed and v not in (None, '')}
    validate_job(clean)
    for key in ('monthly_cap_usd', 'agent_inactivity_minutes', 'api_run_ceiling_usd', 'default_job_timeout'):
        if key in clean:
            clean[key] = _positive(clean[key], key)
    for key, maximum in (('reserve_percent', 100), ('critical_usage_percent', 100), ('cycle_day', 31), ('agent_soft_mark_minutes', 10080)):
        if key in clean:
            value = clean[key]
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= maximum or key == 'cycle_day' and (value < 1 or int(value) != value):
                raise ValueError(f'Invalid {key}.')
    with util.file_lock(_path()):
        state = _read()
        bucket = state.setdefault('providers' if global_provider else 'scopes', {})
        identity = provider if global_provider else scope_id(root, agent)
        # This endpoint replaces the visible choices; empty fields inherit defaults.
        bucket[identity] = clean
        util.write_json_atomic(_path(), state)
    audit('save-run-controls', root, provider=provider, agent=agent, values=clean)


def audit(action, root=None, **values):
    path = util.data_dir() / 'run-controls-audit.jsonl'
    import json
    with util.file_lock(path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'at': dt.datetime.now(dt.timezone.utc).isoformat(), 'action': action,
                                    'realm': scope_id(root) if root else '', **values})+'\n')


def _ledger_path(provider):
    if provider not in ('claude', 'codex', 'gemini'):
        raise ValueError('Unknown API provider.')
    return util.data_dir() / f'{provider}-api-ledger.json'


def cycle(settings, now=None):
    from . import clock
    now = now or clock.now().astimezone(dt.timezone.utc)
    day = int(settings['cycle_day'])
    def anchor(month):
        return month.replace(day=min(day,calendar.monthrange(month.year,month.month)[1]),hour=0,minute=0,second=0,microsecond=0)
    start = anchor(now)
    if now < start:
        start = anchor(start.replace(day=1)-dt.timedelta(days=1))
    following = anchor(start.replace(day=1)+dt.timedelta(days=32))
    return start.isoformat(), following.isoformat()


def _ledger(provider):
    path = _ledger_path(provider)
    if not path.exists() and _read().get('api_accounting_initialized',{}).get(provider):
        raise util.StateError('API accounting is missing; the API lane is closed. Restore its ledger before spending.')
    state = util.read_json_state(path, default=lambda: {'runs': {}})
    if not isinstance(state.get('runs'), dict):
        raise util.StateError('API accounting is unreadable; the API lane is closed.')
    for row in state['runs'].values():
        try:
            if not isinstance(row,dict) or row.get('state') not in ('reserved','finished') or not isinstance(row.get('cycle'),str):
                raise ValueError('Invalid reservation')
            _positive(row['ceiling'], 'Recorded reservation')
            if type(row.get('charged')) not in (int, float) or not math.isfinite(row['charged']) or row['charged'] < 0:
                raise ValueError('Invalid charge')
        except (ValueError,TypeError,KeyError):
            raise util.StateError('API accounting is invalid; the API lane is closed.') from None
    return state


def initialise_ledger(provider):
    """Only owner key setup creates the first ledger; a missing used ledger stays closed."""
    path = _ledger_path(provider)
    with util.file_lock(path):
        state = _ledger(provider)
        if not path.exists():
            util.write_json_atomic(path,state)
        with util.file_lock(_path()):
            policy = _read()
            policy.setdefault('api_accounting_initialized',{})[provider] = True
            util.write_json_atomic(_path(),policy)


def credit(provider='claude', config=None):
    config = config or settings(provider=provider)
    start, reset = cycle(config)
    with util.file_lock(_ledger_path(provider)):
        state = _ledger(provider)
    # Running/uncertain reservations survive a cycle boundary: a process can still spend them.
    rows = list(state['runs'].values())
    spent = sum(r['charged'] for r in rows if _in_cycle(r,start) and r.get('state') == 'finished')
    reserved = sum(r['ceiling'] for r in rows if r.get('state') != 'finished')
    available = max(0, config['monthly_cap_usd']-spent-reserved)
    from .provider_keys import configured
    reason = 'No API key configured.' if not configured(provider) else 'Monthly API cap reached or reserved.' if available <= 0 else ''
    return {'cap_usd': config['monthly_cap_usd'], 'spent_usd': round(spent, 6), 'reserved_usd': round(reserved, 6),
            'remaining_usd': round(available, 6), 'resets_at': reset, 'open': not reason, 'reason': reason}


def _stamp():
    from . import clock
    return clock.now().astimezone(dt.timezone.utc).isoformat()


def _in_cycle(row, start):
    if row.get('finished_at'):
        return row['finished_at'] >= start
    # Older reservations lack completion timestamps. Count their whole overlapping
    # month rather than erase spending when an owner changes the cycle day.
    try:
        old = dt.datetime.fromisoformat(row['cycle'])
        end = (old.replace(day=1)+dt.timedelta(days=32)).replace(day=1)
        return end > dt.datetime.fromisoformat(start)
    except (ValueError,KeyError):
        raise util.StateError('API accounting dates are invalid; the API lane is closed.') from None


def reserve(provider, invocation, config):
    path = _ledger_path(provider)
    with util.file_lock(path):
        # Re-read monetary controls at admission: an owner lowering the cap while
        # a plan attempt is running must not leave that attempt an old spending grant.
        current = settings(provider=provider)
        config = {**config, **{key:current[key] for key in ('monthly_cap_usd','cycle_day','reserve_percent')}}
        start, _ = cycle(config)
        state = _ledger(provider)
        if invocation in state['runs']:
            raise ValueError('Only one API fallback is allowed per invocation.')
        used = sum(r['charged'] if r.get('state') == 'finished' else r['ceiling'] for r in state['runs'].values()
                   if _in_cycle(r,start) or r.get('state') != 'finished')
        floor = 0 if config.get('critical') else config['monthly_cap_usd']*config['reserve_percent']/100
        ceiling = min(config['api_run_ceiling_usd'], config['monthly_cap_usd']-used-floor)
        # Round down: never authorise even a fraction above the available credit.
        ceiling = math.floor((ceiling+1e-10)*10000)/10000
        if ceiling <= 0:
            raise ValueError('API credit is closed: the monthly cap or critical-job reserve is reached.')
        state['runs'][invocation] = {'cycle': start, 'ceiling': ceiling, 'charged': ceiling, 'state': 'reserved','started_at':_stamp()}
        util.write_json_atomic(path, state)
    return ceiling


def settle(provider, invocation, cost):
    path = _ledger_path(provider)
    with util.file_lock(path):
        state = _ledger(provider)
        row = state['runs'][invocation]
        real = type(cost) in (int, float) and math.isfinite(cost) and cost >= 0
        row.update(state='finished', charged=float(cost) if real else row['ceiling'], real_cost_usd=cost if real else None,finished_at=_stamp())
        util.write_json_atomic(path, state)


def notify_once(root, key, message):
    path = util.data_dir() / 'api-notifications.json'
    with util.file_lock(path):
        seen = util.read_json_state(path, default=dict)
        if key in seen:
            return
        seen[key] = dt.datetime.now(dt.timezone.utc).isoformat()
        util.write_json_atomic(path, seen)
    from . import notify
    notify.emit(root, 'api_credit', 'Claude API credit', message, '/settings?tab=app')


def admission(root, agent, thread, provider):
    """Scheduling hints derived only from approved jobs and owner choices."""
    from .job_history import JOB_PREFIX
    from .job_access import identity, fingerprint
    state = _read()
    seals = state.get('jobs', {})
    current_root = scope_id(root)
    reserve_slot = reserve_provider = reserve_realm = False
    critical = False
    for key, seal in seals.items():
        job_root, aid, jid = key.rsplit('|', 2)
        value = util.read_json_state(Path(job_root)/'agents'/aid/'jobs'/f'{jid}.json', default=dict)
        value.setdefault('id',jid)
        if value.get('enabled') is False or not value.get('critical') or seal != fingerprint(value):
            continue
        from .engine.selection import engine_for
        reserve_slot = True
        reserve_realm |= job_root == current_root
        same_provider=engine_for(job_root, aid, value) == provider
        reserve_provider |= same_provider
        critical |= same_provider and job_root == current_root and agent == aid and thread == JOB_PREFIX+jid
    deferred = False
    if not critical:
        from .usage_snapshot import trusted_read as read
        usage = read(root).get(provider, {})
        config = settings(root, agent, provider=provider)
        session = usage.get('session') or {}
        deferred = (reserve_provider and time_now()-usage.get('at', 0) <= 1800
                    and session.get('pct', 0) >= config['critical_usage_percent'])
    return {'critical':bool(critical), 'reserve_slot':reserve_slot, 'reserve_provider':reserve_provider,
            'reserve_realm':reserve_realm, 'usage_deferred':bool(deferred)}


def time_now():
    import time
    return time.time()
