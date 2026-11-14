"""No-model connector heartbeats with durable history and bounded background checks."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit, urlunsplit

from . import capabilities, util

_lock = threading.Lock()
_active = set()
_slots = threading.BoundedSemaphore(3)


def _key(root):
    return hashlib.sha256(str(Path(root).resolve()).casefold().encode()).hexdigest()


def _path(root):
    return util.data_dir() / 'connector-health' / (_key(root) + '.json')


def settings(root):
    return util.read_json_state(util.data_dir() / 'connector-watches.json', default=dict).get(_key(root), {})


def save(root, values):
    """Owner endpoint only. Watching never grants an agent access to a connector."""
    watches = values.get('watched', [])
    ids = {c['id'] for c in capabilities.catalogue(root)['connectors']}
    if not isinstance(watches, list) or any(v not in ids for v in watches):
        raise ValueError('Choose watched connectors from this realm.')
    clean = {'watched': sorted(set(watches))}
    for key, default in (('interval_minutes', 15), ('near_job_minutes', 5), ('lead_minutes', 30)):
        value = values.get(key, default)
        if type(value) is not int or not 1 <= value <= 1440:
            raise ValueError('Heartbeat intervals must be 1 to 1440 minutes.')
        clean[key] = value
    util.mutate_json(util.data_dir() / 'connector-watches.json', lambda data: data.update({_key(root): clean}), default=dict)
    from .run_policy import audit
    audit('connector-watches', root, values=clean)
    return clean


def snapshot(root):
    return util.read_json_state(_path(root), default=lambda: {'connectors': {}})


def public_error(text):
    """Preserve error codes/text, removing transport URLs and credential-like values."""
    text = re.sub(r'https?://[^\s<>"\']+', '[endpoint]', str(text))
    text = re.sub(r'(?i)(bearer\s+|(?:token|api[_-]?key|password|secret)\s*[:=]\s*)[^\s,;]+', r'\1[redacted]', text)
    return text[:2000]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def server_check(endpoint):
    """An unauthenticated transport check proves reachability only, never tool access."""
    parsed = urlsplit(endpoint or '')
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        return {'state': 'unknown', 'error': 'No public HTTPS health endpoint configured.'}
    url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', ''))
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'ARMADA-connector-heartbeat'})
        with urllib.request.build_opener(_NoRedirect).open(request, timeout=10) as response:
            code = response.status
    except urllib.error.HTTPError as exc:
        code = exc.code
    except (OSError, ValueError) as exc:
        return {'state': 'down', 'error': public_error(exc)}
    return {'state': 'up' if code in (200, 204, 400, 401, 403, 405, 406) else 'down',
            'http_status': code, 'error': '' if code < 500 else f'HTTP {code}'}


def incident_check():
    try:
        with urllib.request.urlopen('https://status.claude.com/api/v2/summary.json', timeout=10) as response:
            data = json.loads(response.read(512000))
        return {'state': data.get('status', {}).get('indicator', 'unknown'),
                'incidents': [{'name': public_error(row.get('name', '')), 'status': row.get('status', '')}
                              for row in data.get('incidents', [])[:20]]}
    except (OSError, ValueError) as exc:
        return {'state': 'unknown', 'error': public_error(exc), 'incidents': []}


def probe(root, provider, ids):
    """Only inventory/control messages; never sends a user turn or calls a broker tool."""
    from . import connector_runtime as runtime, tool_inventory
    from .connector_registry import provider_cap
    from .engine import get_engine
    from .engine.contracts import ExecutionPolicy
    from .engine.mcp import server_id, registration_id
    caps = [c for c in capabilities.catalogue(root)['connectors'] if c.get('id') in ids]
    bindings = {c['id']: provider_cap(c, provider) for c in caps}
    servers = frozenset(server_id(c['id']) if provider == 'claude' else registration_id(c['id']) for c in bindings.values())
    tools, inventory, inventory_error = {}, None, ''
    try:
        if provider == 'claude':
            inventory = runtime._claude_rows(root)
            engine = get_engine(provider).configure(ExecutionPolicy(servers, (str(Path(root).resolve()),), False))
            engine.connector_requirements = {server_id(c['id']): runtime.codex_endpoint(c) for c in bindings.values() if c.get('_bound_registration')}
            tools = tool_inventory.claude_inventory(engine, root)
        elif provider == 'codex':
            inventory = runtime.codex_live_inventory(root)
        elif provider == 'gemini':
            inventory = runtime.gemini_inventory()
            engine = get_engine(provider).configure(ExecutionPolicy(servers, (str(Path(root).resolve()),), False))
            engine.connector_requirements = {registration_id(c['id']): runtime.codex_endpoint(c) for c in bindings.values() if c.get('_bound_registration')}
            tools = tool_inventory.gemini_inventory(engine, root)
    except (OSError, ValueError, RuntimeError) as exc:
        inventory_error = public_error(exc)
    incident = incident_check() if provider == 'claude' else None
    results = {}
    for cap in caps:
        bound = bindings[cap['id']]
        sid = server_id(bound['id']) if provider == 'claude' else registration_id(bound['id'])
        transport = server_check(runtime.codex_endpoint(bound))
        listing = {'state': 'up', 'error': ''}
        live = {'state': 'unknown', 'error': inventory_error or 'Tools were not fetched.', 'tool_count': 0}
        if provider == 'claude':
            rows = inventory or []
            row = next((r for r in rows if server_id(r['name']) == sid), None)
            if row is None:
                native = sid.startswith('claude_ai_')
                absent_list = not any(r['name'].startswith('claude.ai ') for r in rows)
                listing = {'state': 'missing', 'error': 'The claude.ai connector list was not returned.'
                           if native and absent_list else 'Granted connector absent from the engine inventory.'}
            elif not row['ready']:
                live = {'state': row['state'], 'error': public_error(row.get('error') or 'CLI health check failed.'), 'tool_count': 0}
            if tools.get(sid) and row and row['ready']:
                live = {'state': 'up', 'error': '', 'tool_count': len(tools[sid])}
            if row and bound.get('_bound_registration') and runtime.codex_endpoint(bound) and row.get('endpoint') != runtime.codex_endpoint(bound):
                listing = {'state': 'different', 'error': 'The engine registration points to a different endpoint.'}
        elif provider == 'codex':
            row = (inventory or {}).get(sid, {})
            state = runtime.codex_connection(cap, inventory)
            callable_tools = row.get('callable') is True if bound.get('_native_app') else bool(row.get('tool_names'))
            live = {'state': 'up' if state == 'ready' and callable_tools else 'unknown' if state == 'ready' else state,
                    'error': public_error(row.get('runtime_error') or inventory_error),
                    'tool_count': None if bound.get('_native_app') else len(row.get('tool_names', []))}
        elif tools.get(sid):
            live = {'state': 'up', 'error': '', 'tool_count': len(tools[sid])}
        if bound.get('_unbound'):
            live = {'state': 'missing', 'error': 'This connector is not linked to this engine.', 'tool_count': 0}
        if not capabilities.realm_enabled(cap):
            live = {'state': 'disabled', 'error': 'Connector is disabled in the realm.', 'tool_count': 0}
        # HTTP 401 is only a positive transport result. Ready requires fetched tools.
        ready = listing['state'] == 'up' and live['state'] == 'up' and transport['state'] != 'down'
        failed = next(((name, link) for name, link in (('provider server', transport), ('connector list', listing), ('live tools', live))
                       if link['state'] not in ('up', 'unknown') or name == 'live tools' and link['state'] != 'up'), None)
        results[cap['id']] = {'id': cap['id'], 'name': cap.get('name') or cap['id'], 'provider': provider,
            'state': 'up' if ready else 'down', 'links': {'server': transport, 'listing': listing, 'tools': live},
            'reason': '' if ready else (f'{failed[0]}: {failed[1]["error"] or failed[1]["state"]}' if failed else inventory_error or 'Health not verified.'),
            'provider_incident': incident}
    for missing in set(ids) - set(results):
        results[missing] = {'id': missing, 'name': missing, 'provider': provider, 'state': 'down', 'links': {},
                            'reason': 'Required connector is missing from the realm catalogue.'}
    return results


def record(root, provider, rows, now=None):
    now = time.time() if now is None else now
    changes = []
    with util.file_lock(_path(root)):
        data = snapshot(root)
        for cid, row in rows.items():
            key = provider + ':' + cid
            old = data['connectors'].get(key, {})
            row = {**row, 'checked_at': now, 'last_up_at': now if row['state'] == 'up' else old.get('last_up_at'),
                   'down_since': None if row['state'] == 'up' else old.get('down_since') or now}
            checks = [check for check in old.get('checks', []) if check['at'] >= now - 30 * 86400]
            checks.append({'at': now, 'up': row['state'] == 'up'})
            row.update(checks=checks, uptime_percent=round(100 * sum(c['up'] for c in checks) / len(checks), 1))
            data['connectors'][key] = row
            if old.get('state') != row['state'] and (old or row['state'] != 'up'):
                changes.append(row)
            history = _path(root).with_suffix('.jsonl')
            history.parent.mkdir(parents=True, exist_ok=True)
            with history.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps({k: v for k, v in row.items() if k != 'checks'}) + '\n')
        util.write_json_atomic(_path(root), data)
        util.write_json_atomic(Path(root) / 'connector-health.json', {'connectors': {
            k: {field: value for field, value in v.items() if field != 'checks'} for k, v in data['connectors'].items()}})
    from . import notify
    for row in changes:
        when = dt.datetime.fromtimestamp(row.get('down_since') or row['checked_at'], dt.timezone.utc).astimezone().strftime('%H:%M')
        notify.emit(root, 'connector_health', row['name'] + (' is back' if row['state'] == 'up' else ' is unavailable'),
                    ('Back at ' if row['state'] == 'up' else 'Down since ') + when + ': ' +
                    (row.get('reason') or 'Connector tools are available again.'), '/skills')
    return data


def request(root, provider, ids, *, max_age=300, not_before=0):
    """Coalesce checks across processes. Pending work consumes no execution ticket."""
    ids = sorted(set(ids))
    rows = snapshot(root)['connectors']
    def outdated(rows, cid):
        checked = rows.get(provider + ':' + cid, {}).get('checked_at', 0)
        return checked < not_before or time.time() - checked >= max_age
    stale = [cid for cid in ids if outdated(rows, cid)]
    key = (_key(root), provider)
    if stale:
        with _lock:
            if key not in _active and _slots.acquire(blocking=False):
                _active.add(key)
                def work():
                    try:
                        with util.file_lock(_path(root).with_suffix('.probe-' + provider), timeout=.05):
                            current = snapshot(root)['connectors']
                            todo = [cid for cid in stale if outdated(current, cid)]
                            if todo:
                                record(root, provider, probe(root, provider, todo))
                    except util.FileLockTimeout:
                        pass  # Another process owns this provider check.
                    except Exception as exc:
                        import logging
                        logging.getLogger(__name__).warning('Connector heartbeat failed: %s', public_error(exc))
                        record(root, provider, {cid: {'id': cid, 'name': cid, 'provider': provider, 'state': 'down',
                            'reason': public_error(exc), 'links': {}} for cid in stale})
                    finally:
                        _slots.release()
                        from .scheduler import _work_changed
                        _work_changed.set()
                        with _lock:
                            _active.discard(key)
                try:
                    threading.Thread(target=work, daemon=True, name='connector-heartbeat').start()
                except BaseException:
                    _slots.release()
                    _active.discard(key)
                    raise
    return {cid: rows.get(provider + ':' + cid, {}) for cid in ids}


def context(root):
    try:
        return _context(root)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        import logging
        logging.getLogger(__name__).warning('Connector health context unavailable: %s', public_error(exc))
        return 'Connector health readings are unavailable; do not assume connectors are healthy.'


def _context(root):
    rows = snapshot(root)['connectors'].values()
    return '\n'.join(f"{r['name']} ({r['provider']}): {r['state']}; last checked "
                     f"{dt.datetime.fromtimestamp(r['checked_at'], dt.timezone.utc).astimezone():%Y-%m-%d %H:%M %Z}"
                     + (' (stale — older than 30 minutes)' if time.time()-r['checked_at'] > 1800 else '')
                     + (f"; down since {dt.datetime.fromtimestamp(r['down_since'], dt.timezone.utc).astimezone():%Y-%m-%d %H:%M %Z}" if r.get('down_since') else '')
                     + (f"; {r['reason']}" if r.get('reason') else '') for r in rows)


def tick(root, now=None):
    """Weekday watches plus faster checks around jobs, without blocking discovery."""
    from . import scheduler, job_waits
    from .engine.selection import engine_for
    config = util.read_json_state(Path(root)/'realm.json')
    now = now or scheduler.now_in(config)
    choices = settings(root)
    watches = set(choices.get('watched', []))
    regular = choices.get('interval_minutes', 15) * 60
    rapid = choices.get('near_job_minutes', 5) * 60
    lead = choices.get('lead_minutes', 30)
    wanted = {}
    for agent, jid, job in scheduler.iter_jobs(Path(root)):
        if job.get('enabled') is False or job.get('_record_error'):
            continue
        required = set(job.get('requires_connectors', []))
        if not required:
            continue
        provider = engine_for(root, agent, job)
        prior = job_waits.pending(root, agent, jid)
        upcoming = scheduler._due_time(job, now+dt.timedelta(minutes=lead), lead)
        near = prior is not None or upcoming is not None
        if near and prior is None and upcoming and scheduler.ran_today(root, agent, jid, upcoming.date().isoformat(), not_before=upcoming):
            near = False
        for cid in required:
            if near or now.weekday() < 5 and cid in watches:
                wanted[provider, cid] = min(wanted.get((provider, cid), regular), rapid if near else regular)
    # Watches that no job requires still receive the regular weekday heartbeat.
    if now.weekday() < 5:
        from .connector_registry import provider_cap
        for cap in capabilities.catalogue(root)['connectors']:
            if cap.get('id') in watches:
                for provider in ('claude', 'codex', 'gemini'):
                    if not provider_cap(cap, provider).get('_unbound'):
                        wanted.setdefault((provider, cap['id']), regular)
    for provider in ('claude', 'codex', 'gemini'):
        for interval in set(v for (p, _), v in wanted.items() if p == provider):
            request(root, provider, [cid for (p, cid), value in wanted.items() if p == provider and value == interval], max_age=interval)
    return {'ok': True, 'detail': f'{len(watches)} watched connectors; checks use no model tokens.'}
