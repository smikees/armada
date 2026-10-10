"""Logical connectors with explicit provider-local registrations; no credential copying."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit

from . import util
from .engine.mcp import registration_id, server_id

PROVIDERS = ('claude', 'codex', 'gemini')
SERVICES = (
    {'id': 'google-drive', 'name': 'Google Drive', 'category': 'Files & documents',
     'aliases': 'docs sheets slides documents spreadsheets presentations storage google workspace',
     'description': 'Find files and work with documents, spreadsheets and presentations.',
     'engines': {'claude': 'Claude connector · document editing may need separate Docs, Sheets or Slides connectors.',
                 'codex': 'OpenAI native app · includes document, spreadsheet and presentation workflows.',
                 'gemini': 'Requires a compatible MCP integration; Claude and Codex apps cannot be reused.'}},
    {'id': 'gmail', 'name': 'Gmail', 'category': 'Email & calendar', 'aliases': 'email mail inbox google workspace',
     'description': 'Find messages and work with your email through your engine’s Gmail integration.',
     'engines': {'claude': 'Claude connector · review available actions and permissions during sign-in.',
                 'codex': 'OpenAI native app · review available actions and permissions during sign-in.',
                 'gemini': 'Requires a compatible MCP integration; Claude and Codex apps cannot be reused.'}},
    {'id': 'notion', 'name': 'Notion', 'category': 'Files & documents', 'aliases': 'notes wiki pages databases knowledge',
     'description': 'Search your workspace and create or update pages with Notion’s official MCP server.',
     'endpoint': 'https://mcp.notion.com/mcp',
     'engines': {p: 'Notion official MCP · separate workspace sign-in for each engine.' for p in PROVIDERS}},
    *({'id': sid, 'name': name, 'category': category, 'aliases': aliases, 'description': description,
       'engines': {'claude': 'Claude connector directory · review publisher, available actions and permissions before sign-in.',
                   'codex': 'Codex native app · review publisher, available actions and permissions before sign-in.',
                   'gemini': 'Requires a compatible MCP integration; Claude and Codex apps cannot be reused.'}}
      for sid, name, category, aliases, description in (
          ('google-calendar', 'Google Calendar', 'Email & calendar', 'events meetings schedule google workspace', 'Work with events and schedules in your Google calendar.'),
          ('slack', 'Slack', 'Communication', 'chat messages channels team', 'Find conversations and work with your Slack workspace.'),
          ('github', 'GitHub', 'Development', 'code repositories issues pull requests', 'Work with repositories, issues and pull requests.'))),
)
NATIVE_SERVICES = frozenset(s['id'] for s in SERVICES if not s.get('endpoint'))
PRESETS = (
    ('notion', 'Notion', 'https://mcp.notion.com/mcp',
     'https://developers.notion.com/guides/mcp/get-started-with-mcp',
     'Official Notion MCP. Sign in separately for each engine and select your workspace.'),

)


def endpoint(value):
    """Only shareable HTTPS endpoints belong in a portable realm, never URL credentials."""
    if not isinstance(value, str) or len(value) > 2048:
        return ''
    try:
        url = urlsplit(value)
        if (url.scheme != 'https' or not url.hostname or url.username or url.password
                or url.query or url.fragment or any(c.isspace() or ord(c) < 32 for c in value)):
            return ''
        url.port  # reject malformed ports
    except ValueError:
        return ''
    return value


def valid_name(value, provider):
    if not isinstance(value, str) or not value or value.startswith('-') or len(value) > 200 or value != value.strip():
        return False
    if provider == 'claude':
        return not any(ord(c) < 32 or c in '*?()[]{}\\"' for c in value)
    return bool(re.fullmatch(r'[A-Za-z0-9_-]+', value))


def _public_endpoint(value):
    """Imported private proxy paths can embed credentials; retain only known public routes."""
    safe = endpoint(value)
    return safe if safe and urlsplit(safe).path.rstrip('/') in ('/mcp', '/sse', '/mcp/v1') else ''


def binding(cap, provider):
    rows = cap.get('provider_bindings') or {}
    row = rows.get(provider, {}) if isinstance(rows, dict) else {}
    return row if isinstance(row, dict) else {}


def provider_cap(cap, provider):
    """Runtime facade; preserve the logical capability identity in grants/UI."""
    if cap.get('_bound_registration'):
        return cap
    row = binding(cap, provider)
    if row.get('disabled') is True:
        return {**cap, '_unbound': True}
    if not row:
        return {**cap, '_unbound': True} if cap.get('connection_type') in ('provider-mcp', 'provider-native') and not cap.get('mcp_url') else cap
    if row.get('app_id'):
        return {**cap, 'id': row['app_id'], '_native_app': True, '_bound_registration': True}
    return {**cap, 'id': row['server_name'], 'name': row['server_name'],
            'command': row.get('endpoint', ''), 'mcp_url': row.get('endpoint', ''),
            'provider_bindings': {}, '_bound_registration': True}


def policy_bindings(cap):
    rows = cap.get('provider_bindings', {})
    if not isinstance(rows, dict) or any(p not in PROVIDERS for p in rows):
        raise ValueError('Invalid connector provider bindings.')
    result = []
    for provider, row in rows.items():
        if row == {'disabled': True}:
            result.append((str(cap.get('id') or ''), provider, ''))
            continue
        if isinstance(row, dict) and 'app_id' in row:
            from .codex_apps import valid_id
            if provider != 'codex' or set(row) != {'app_id'} or not valid_id(row['app_id']):
                raise ValueError('Invalid native connector binding.')
            result.append((str(cap.get('id') or ''), provider, 'app:' + row['app_id']))
            continue
        if (not isinstance(row, dict) or set(row) - {'server_name', 'endpoint'}
                or not valid_name(row.get('server_name'), provider)
                or (row.get('endpoint') and not endpoint(row['endpoint']))):
            raise ValueError('Invalid connector registration. Reconnect it in Capabilities.')
        name = row['server_name']
        result.append((str(cap.get('id') or ''), provider,
                       server_id(name) if provider == 'claude' else name))
    if cap.get('connection_type') in ('provider-mcp', 'provider-native') and not cap.get('mcp_url'):
        result.extend((cap['id'], p, '') for p in PROVIDERS if p not in rows)
    return tuple(result)


def inventory(provider, realm_root=None):
    """Names and safe remote URLs only. Headers, env, OAuth and local commands stay private."""
    from . import connector_runtime as runtime
    if provider == 'claude':
        rows = runtime._claude_rows(realm_root)
        if rows is None:
            raise ValueError('Could not read Claude registrations. Recheck the engine in App settings.')
        return [{'server_name': r['name'], 'endpoint': _public_endpoint(r.get('endpoint', '')),
                 'state': 'ready' if r['ready'] else 'failed'} for r in rows
                if r.get('remote') and valid_name(r['name'], provider)]
    if provider == 'codex':
        from . import codex_apps
        native = [{'server_name': 'app:' + r['id'], 'endpoint': '',
                   'label': (r.get('runtimeName') or r['id']) + ' · native app',
                   'app_id': r['id'], 'state': 'ready' if r['callable'] else 'configured'}
                  for r in codex_apps.inventory(cwd=realm_root)]
        rows = runtime.codex_inventory()
        if rows is None:
            raise ValueError('Could not read Codex registrations. Recheck the engine in App settings.')
        return native + [{'server_name': name, 'endpoint': _public_endpoint((r.get('transport') or {}).get('url', '')),
                 'state': 'configured'} for name, r in rows.items()
                if isinstance(r.get('transport'), dict) and r['transport'].get('url')
                and valid_name(name, provider)]
    if provider == 'gemini':
        rows = runtime.gemini_inventory()
        if rows is None:
            raise ValueError('Could not read Gemini registrations. Check its MCP configuration.')
        return [{'server_name': name, 'endpoint': _public_endpoint(r.get('serverUrl', '')),
                 'state': 'configured'} for name, r in rows.items()
                if isinstance(r, dict) and r.get('serverUrl') and valid_name(name, provider)]
    raise ValueError('Unknown connector engine.')


def verify_registrations(requirements, registrations):
    """A linked name cannot silently start pointing an agent at another service."""
    for name, expected in requirements.items():
        if name not in registrations:
            raise ValueError(f'Connector {name} is missing or disabled in this engine. Reconnect it in Capabilities.')
        if expected and registrations[name] != expected:
            raise ValueError(f'Connector {name} has different settings in this engine. Review its connection in Capabilities.')


def save(realm_root, *, name='', url='', provider='', server_name='', capability='', service='', account_label=''):
    """Add a remote connector or explicitly link one existing engine registration."""
    from . import capabilities
    if not isinstance(name, str) or len(name) > 120 or any(ord(c) < 32 for c in name):
        raise ValueError('Use a connector name of at most 120 characters.')
    if not isinstance(account_label, str) or len(account_label) > 80 or any(ord(c) < 32 for c in account_label):
        raise ValueError('Use an account label of at most 80 characters.')
    account_label = account_label.strip()
    selected = None
    if service:
        entry = next((s for s in SERVICES if s['id'] == service), None)
        if entry is None:
            raise ValueError('Unknown provider connector.')
        name = entry['name'] + (' · ' + account_label if account_label else '')
        if entry.get('endpoint'):
            if capability:
                raise ValueError('Link an existing engine connection to this service.')
            url, service = entry['endpoint'], ''
        if capability:
            from . import codex_apps
            info = codex_apps.service(service, cwd=realm_root)
            provider, server_name = 'codex', 'app:' + info['app_id']
            selected = {'app_id': info['app_id']}
        else:
            provider = ''
    elif provider:
        from .codex_apps import valid_id
        native = provider == 'codex' and isinstance(server_name, str) and server_name.startswith('app:') and valid_id(server_name[4:])
        if provider not in PROVIDERS or not (valid_name(server_name, provider) or native):
            raise ValueError('Choose an existing connector registration.')
        selected = next((r for r in inventory(provider, realm_root) if r['server_name'] == server_name), None)
        if selected is None:
            raise ValueError('That registration is no longer available. Refresh the list.')
    elif not endpoint(url):
        raise ValueError('Enter an HTTPS MCP server URL without a query, fragment or embedded credentials. Configure private URLs in the engine and import its registration instead.')
    path = Path(realm_root) / 'realm.json'
    with util.file_lock(path):
        data = util.read_json_state(path)
        toolkit = data.setdefault('toolkit', {})
        rows = toolkit.setdefault('connectors', [])
        cap = next((r for r in rows if r.get('id') == capability), None) if capability else None
        if capability and cap is None:
            raise ValueError('Connector is no longer in this realm.')
        if selected:
            # One engine registration must never be granted through two logical capabilities.
            sid = selected.get('app_id') or (server_id(server_name) if provider == 'claude' else server_name)
            for kind in capabilities.MCP_KINDS:
                for other in toolkit.get(kind, []):
                    if other is cap:
                        continue
                    facade = provider_cap(other, provider)
                    other_sid = (server_id(facade.get('id', '')) if provider == 'claude'
                                 else registration_id(facade.get('id', '')))
                    if other_sid == sid:
                        raise ValueError('This registration already belongs to another capability. Use that connector instead.')
        if cap is None:
            label = name.strip() or ((selected.get('label') or server_name) if selected else '')
            if not label:
                raise ValueError('Enter a connector name.')
            base = registration_id(label.lower().replace(' ', '-'))
            if base.startswith('-'):
                base = 'armada' + base
            used = {r.get('id') for kind in capabilities.KINDS for r in toolkit.get(kind, [])}
            cid, i = base, 2
            while cid in used:
                cid, i = f'{base}-{i}', i + 1
            cap = {'id': cid, 'name': label, 'source': 'custom', 'enabled': True,
                   'status': 'configured', 'runs': 'service', 'touch': ['network'],
                   'description': 'Remote MCP connector with independent engine connections.',
                   'connection_type': 'provider-mcp', 'provider_bindings': {}}
            rows.append(cap)
            if account_label:
                cap['account_label'] = account_label
            if entry_id := next((s['id'] for s in SERVICES if s['id'] == service or s.get('endpoint') == url), None):
                cap['service_id'] = entry_id
        if service:
            cap['native_service'] = service
            if not capability:
                cap['connection_type'] = 'provider-native'
            cap['description'] = 'Provider connectors with separate engine sign-in and shared agent grants.'
        if selected:
            cap.setdefault('provider_bindings', {})[provider] = ({'app_id': selected['app_id']}
                if selected.get('app_id') else {'server_name': server_name, 'endpoint': selected['endpoint']})
            if account_label:
                cap.setdefault('connection_labels', {})[provider] = account_label
        elif not service:
            cap['mcp_url'] = url
            cap['command'] = url
        policy_bindings(cap)
        util.write_json_atomic(path, data)
    return {'ok': True, 'capability': cap['id']}


def unlink(realm_root, capability, provider):
    """Remove this realm's binding only; never revoke shared provider credentials."""
    if provider not in PROVIDERS:
        raise ValueError('Unknown connector engine.')
    path = Path(realm_root) / 'realm.json'
    with util.file_lock(path):
        data = util.read_json_state(path)
        cap = next((c for c in data.get('toolkit', {}).get('connectors', []) if c.get('id') == capability), None)
        if cap is None:
            raise ValueError('Connector not found in this realm.')
        cap.setdefault('provider_bindings', {})[provider] = {'disabled': True}
        cap.get('connection_labels', {}).pop(provider, None)
        util.write_json_atomic(path, data)
    return {'ok': True, 'capability': capability}


def model_change_warning(realm_root, agent, before, after):
    """Explain a provider switch before saving; runtime preflight remains authoritative."""
    if before == after:
        return ''
    from . import capabilities
    policy = capabilities.execution_policy(realm_root, agent)
    caps = [c for c in capabilities.catalogue(realm_root)['connectors'] if c.get('id') in policy.allowed_mcp_ids]
    if not caps:
        return ''
    missing = [c.get('name') or c['id'] for c in caps if provider_cap(c, after).get('_unbound')]
    message = f'This changes the engine from {before.title()} to {after.title()}. '
    if missing:
        message += 'Connect these services in the new engine before running: ' + ', '.join(missing) + '. '
    message += ('Each engine has its own sign-in, account and available operations. Review the connector rows in '
                'Capabilities; ARMADA will not transfer credentials or substitute another engine. Save this model choice?')
    return message
