"""Codex-native connected apps, discovered through the CLI's app-server protocol."""
from __future__ import annotations

import re

from .engine.codex import CodexEngine, _feature_args
from .engine.process import supervise_rpc


def rpc(method, params, *, cwd=None, config=()):
    engine = CodexEngine()
    launcher = engine._launcher()
    if not launcher:
        raise ValueError('Codex CLI is not installed.')
    answer = {}

    def start(send):
        send({'id': 1, 'method': 'initialize', 'params': {
            'clientInfo': {'name': 'armada', 'version': '1.0'},
            'capabilities': {'experimentalApi': True}}})

    def accept(message, send):
        if 'method' in message and 'id' in message:
            send({'id': message['id'], 'error': {'code': -32601, 'message': 'Metadata checks do not approve actions.'}})
        elif message.get('id') == 1:
            if message.get('error'):
                raise ValueError('Codex could not initialize native connector discovery.')
            send({'method': 'initialized', 'params': {}})
            send({'id': 2, 'method': method, 'params': params})
        elif message.get('id') == 2:
            if message.get('error'):
                from .connector_login import _error
                raise ValueError(_error(str(message['error'].get('message', 'Native connector discovery failed.'))))
            answer.update(message.get('result') or {})
            return True
        return False

    result = supervise_rpc(launcher + ['app-server'] + _feature_args() +
        ['-c', 'features.apps=true', *config], start=start, on_message=accept, timeout=45, cwd=cwd)
    if not answer:
        raise ValueError(result.error or 'Codex did not return its native connector inventory.')
    return answer


def valid_id(value):
    return isinstance(value, str) and bool(re.fullmatch(r'(?:connector_|asdk_app_)[A-Za-z0-9_-]{1,180}', value))


def inventory(*, force=False, cwd=None):
    """Runtime inventory, not the entire public app directory or its display metadata."""
    result = rpc('app/installed', {'forceRefresh': force}, cwd=cwd)
    rows = result.get('apps')
    if not isinstance(rows, list) or any(not isinstance(r, dict) or not valid_id(r.get('id')) for r in rows):
        raise ValueError('Codex returned an invalid native connector inventory.')
    return rows


def service(plugin, *, cwd=None):
    from .connector_registry import NATIVE_SERVICES
    if plugin not in NATIVE_SERVICES:
        raise ValueError('Unknown provider connector.')
    result = rpc('plugin/read', {'pluginName': plugin,
        'remoteMarketplaceName': 'openai-curated-remote'}, cwd=cwd,
        config=['-c', 'features.plugins=true'])
    apps = (result.get('plugin') or {}).get('apps') or []
    if len(apps) != 1 or not valid_id(apps[0].get('id')):
        raise ValueError('This provider plugin does not expose one independently grantable connector.')
    return {'app_id': apps[0]['id'], 'name': apps[0].get('name') or plugin,
            'install_url': f'https://chatgpt.com/plugins/{plugin}?open_in_app'}


def scoped_args(allowed, *, cwd=None):
    """Invocation-only app policy. Preserve per-tool restrictions in the owner's config."""
    if any(not valid_id(sid) for sid in allowed):
        raise ValueError('Invalid native connector grant.')
    rows = inventory(cwd=cwd)
    config = rpc('config/read', {'includeLayers': False}, cwd=cwd).get('config', {}).get('apps') or {}
    if any(isinstance(config.get(sid), dict) and config[sid].get('enabled') is False for sid in allowed):
        raise ValueError('A granted native connector is disabled in Codex. Enable it there before running this agent.')
    ids = {r['id'] for r in rows} | (set(config) - {'_default'}) | set(allowed)
    args = ['-c', 'features.apps=true', '-c', 'apps._default.enabled=false']
    for sid in sorted(ids):
        # CLI -c splits dotted paths literally; TOML-quoting a key creates a different app ID.
        if not re.fullmatch(r'[A-Za-z0-9_-]+', sid):
            raise ValueError('Codex has an app policy key that ARMADA cannot safely scope.')
        key = 'apps.' + sid
        args += ['-c', key + '.enabled=' + ('true' if sid in allowed else 'false')]
        if sid in allowed:
            args += ['-c', key + '.default_tools_approval_mode="approve"']
    return args


def verify_snapshot(result, allowed):
    """Check the actual thread before sending any prompt to the model. Never trust UI metadata."""
    rows = result.get('apps')
    if not isinstance(rows, list) or any(not isinstance(r, dict) or not valid_id(r.get('id'))
            or type(r.get('callable')) is not bool or type(r.get('enabled')) is not bool for r in rows):
        raise ValueError('Codex could not verify native connector permissions for this turn.')
    callable_ids = {r['id'] for r in rows if r['callable']}
    if callable_ids - set(allowed):
        raise ValueError('Codex exposed an ungranted native connector; the turn was blocked.')
    if set(allowed) - callable_ids:
        raise ValueError('A required native Codex connector is unavailable. Sign in or recheck it in Capabilities.')
