"""Owner API fallback choices; the provider enforces externally managed budgets.

Keys stay in provider_keys, never in this policy, a realm, or a transcript. Local
usage is an observation of Armada calls, not the provider's authoritative balance.
"""
import datetime as dt
import math
import time
from pathlib import Path
from . import util, provider_keys

SUPPORTED = ('claude',)
CLAUDE_API_ORIGIN = 'https://api.anthropic.com'


def _path():
    return util.data_dir() / 'api-fallback.json'


def _read():
    state = util.read_json_state(_path(), default=lambda: {'providers': {}, 'agents': {}})
    if not isinstance(state.get('providers'), dict) or not isinstance(state.get('agents'), dict):
        raise util.StateError('Invalid API fallback settings; preserve the file before repairing it.')
    for config in state['providers'].values():
        if not isinstance(config, dict) or type(config.get('enabled')) is not bool:
            raise util.StateError('Invalid API fallback engine settings.')
    for agents in state['agents'].values():
        if not isinstance(agents, dict) or any(not isinstance(row, dict) or row.get('key_source') not in ('engine', 'agent', 'off') for row in agents.values()):
            raise util.StateError('Invalid API fallback agent settings.')
    return state


def _identity(root, agent):
    from .run_policy import scope_id
    return scope_id(root, agent)


def managed(provider):
    if provider not in SUPPORTED:
        return False
    try:
        return provider in _read().get('providers', {})
    except OSError:
        return True  # A damaged policy cannot restore implicit legacy spending.


def settings(provider='claude', root=None, agent=''):
    error = ''
    try:
        state = _read() if provider in SUPPORTED else {}
    except OSError:
        state = {'providers': {provider: {'enabled': False}}, 'agents': {}}
        error = 'API fallback settings are unreadable. Restore or repair their saved file before enabling fallback.'
    config = state.get('providers', {}).get(provider, {})
    own = state.get('agents', {}).get(provider, {}).get(_identity(root, agent), {}) if agent else {}
    source = own.get('key_source', 'engine')
    saved = provider_keys.configured(provider, root, agent) if source == 'agent' else provider_keys.configured(provider)
    enabled = config.get('enabled', False) and source != 'off'
    agent_keys = sum(row.get('key_source') == 'agent' and provider_keys.configured(provider, *identity.rsplit('|', 1))
                     for identity, row in state.get('agents', {}).get(provider, {}).items())
    return {'provider': provider, 'supported': provider in SUPPORTED,
            'enabled': bool(enabled), 'critical_only': True, 'key_source': source,
            'key_saved': saved, 'engine_key_saved': provider_keys.configured(provider),
            'agent_key_saved': provider_keys.configured(provider, root, agent) if agent else False,
            'engine_enabled': bool(config.get('enabled', False)),
            'managed': provider in state.get('providers', {}),
            'error': error,
            'agent_keys_configured': agent_keys,
            'ready': bool(enabled and (saved or not agent and agent_keys))}


def save(provider, *, enabled=None, root=None, agent='', key_source=None, api_key=None, remove_key=False):
    if provider not in SUPPORTED:
        raise ValueError('API usage fallback is currently available for Claude only.')
    if enabled is not None and type(enabled) is not bool:
        raise ValueError('Choose whether API fallback is enabled.')
    if agent:
        util.safe_seg(agent, 'agent')
        if not root or not (Path(root)/'agents'/agent/'agent.json').is_file():
            raise ValueError('This agent is no longer available.')
        if key_source not in ('engine', 'agent', 'off'):
            raise ValueError('Choose the engine key, a separate agent key, or no fallback.')
        if api_key and key_source != 'agent':
            raise ValueError('Choose a separate agent key before entering one.')
    if api_key is not None and (not isinstance(api_key, str) or not api_key.startswith('sk-ant-') or any(c.isspace() for c in api_key)):
        raise ValueError('Enter an Anthropic API key, or leave it empty to keep the saved key.')
    if api_key and api_key.startswith('sk-ant-admin'):
        raise ValueError('Use a workspace API key, not an administrator key.')
    with util.file_lock(_path()):
        state = _read()
        first_setup = provider not in state.get('providers', {})
        # Stage disabled before writing a key: a failed first save must not enable
        # the old implicit, all-run fallback just because a key now exists.
        state.setdefault('providers', {}).setdefault(provider, {'enabled': False, 'critical_only': True})
        if agent:
            agents = state.setdefault('agents', {}).setdefault(provider, {})
            agents[_identity(root, agent)] = {'key_source': 'off'}
        else:
            state['providers'][provider] = {'enabled': False, 'critical_only': True}
        util.write_json_atomic(_path(), state)
        if api_key:
            provider_keys.save(provider, api_key, root, agent, managed_externally=True)
        if remove_key:
            provider_keys.save(provider, '', root, agent, managed_externally=True)
        saved = provider_keys.configured(provider, root, agent) if agent and key_source == 'agent' else provider_keys.configured(provider)
        own_keys = any(provider_keys.configured(provider, *identity.rsplit('|', 1))
                       for identity, row in state.get('agents', {}).get(provider, {}).items()
                       if row.get('key_source') == 'agent')
        if (enabled if not agent else key_source == 'agent') and not (saved or not agent and own_keys):
            raise ValueError('Add an API key before enabling this fallback.')
        if agent:
            agents[_identity(root, agent)] = {'key_source': key_source}
            if first_setup and key_source == 'agent':
                state['providers'][provider]['enabled'] = True
        else:
            state['providers'][provider] = {'enabled': bool(enabled), 'critical_only': True}
        util.write_json_atomic(_path(), state)
    from .run_policy import audit
    audit('save-api-fallback', root, provider=provider, agent=agent,
          enabled=enabled, key_source=key_source, external_budget=True)
    return settings(provider, root, agent)


def credential(provider, root, agent):
    config = settings(provider, root, agent)
    if not config['ready']:
        raise ValueError('Claude API fallback is off or its selected key has not been saved.')
    return provider_keys.key(provider, root, agent) if config['key_source'] == 'agent' else provider_keys.key(provider)


def verify(provider, *, api_key=None, root=None, agent='', key_source=None):
    """Free model-list authentication check; never make a generation request."""
    if provider not in SUPPORTED:
        raise ValueError('API usage fallback is currently available for Claude only.')
    import urllib.request
    import urllib.error
    secret = api_key or (provider_keys.key(provider, root, agent)
                        if agent and key_source == 'agent' else provider_keys.key(provider))
    if not secret:
        raise ValueError('Enter an API key, or save one first.')
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    request = urllib.request.Request(CLAUDE_API_ORIGIN+'/v1/models',
        headers={'x-api-key': secret, 'anthropic-version': '2023-06-01'})
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=12) as response:
            if response.status != 200:
                raise ValueError('Claude could not verify this API key.')
        return 'Key accepted. This free check verifies sign-in; manage credit and spending limits in Claude Console.'
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise ValueError('Claude did not accept this key. Create a workspace API key in the linked Console organization.') from None
        raise ValueError(f'Claude could not check the key (HTTP {exc.code}). Try again later.') from None
    except OSError:
        raise ValueError('Could not reach Claude to check the key. Check your connection and try again.') from None


def redact(value, secret):
    if isinstance(value, str):
        return value.replace(secret, '[API key removed]') if secret else value
    if isinstance(value, dict):
        return {redact(k, secret): redact(v, secret) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, secret) for v in value]
    return value


def _usage_path(provider):
    if provider not in SUPPORTED:
        raise ValueError('Unknown API fallback provider.')
    return util.data_dir() / f'{provider}-fallback-usage.json'


def _usage(provider):
    state = util.read_json_state(_usage_path(provider), default=lambda: {'runs': {}})
    rows = state.get('runs')
    if not isinstance(rows, dict) or any(not isinstance(row, dict) for row in rows.values()):
        raise util.StateError('API usage tracking is unreadable.')
    return state


def start(provider, run_id, root, agent):
    path = _usage_path(provider)
    with util.file_lock(path):
        state = _usage(provider)
        if run_id in state['runs']:
            raise ValueError('This invocation has already used API fallback.')
        state['runs'][run_id] = {'started_at': time.time(), 'agent': agent,
                                 'scope': _identity(root, agent), 'status': 'running', 'cost_usd': None}
        util.write_json_atomic(path, state)


def finish(provider, run_id, result):
    path = _usage_path(provider)
    cost = result.raw.get('total_cost_usd')
    known = type(cost) in (int, float) and math.isfinite(cost) and cost >= 0
    with util.file_lock(path):
        state = _usage(provider)
        if run_id not in state['runs']:
            raise util.StateError('The API usage receipt is unavailable.')
        state['runs'][run_id].update(status='finished', finished_at=time.time(),
                                      cost_usd=float(cost) if known else None)
        util.write_json_atomic(path, state)
    return float(cost) if known else None


def credit(provider='claude'):
    now = dt.datetime.now(dt.timezone.utc)
    start_at = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    reset = (start_at+dt.timedelta(days=32)).replace(day=1)
    unavailable = False
    try:
        with util.file_lock(_usage_path(provider)):
            state = _usage(provider)
    except OSError:
        state = {'runs': {}}
        unavailable = True
    rows = [r for r in state['runs'].values() if r.get('status') == 'running'
            or r.get('finished_at', r.get('started_at', 0)) >= start_at.timestamp()]
    def known_cost(row):
        value = row.get('cost_usd')
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    known = [r['cost_usd'] for r in rows if known_cost(r)]
    config = settings(provider)
    own_keys = any(provider_keys.configured(provider, *identity.rsplit('|', 1))
                   for identity, row in _read().get('agents', {}).get(provider, {}).items() if row.get('key_source') == 'agent')
    ready = config['enabled'] and (config['key_saved'] or own_keys)
    return {'budget_managed': 'provider', 'cap_usd': None, 'spent_usd': None if unavailable else round(sum(known), 6),
            'reserved_usd': 0, 'remaining_usd': None, 'resets_at': reset.isoformat(),
            'unknown_runs': sum(not known_cost(r) and r.get('status') == 'finished' for r in rows),
            'accounting_available': not unavailable,
            'active_runs': sum(r.get('status') == 'running' for r in rows),
            'open': bool(ready), 'reason': '' if ready else 'API fallback is off or no API key is configured.'}
