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


_ENGINE_ROW_LABEL = {'claude': 'Claude', 'codex': 'Codex'}
_ENGINE_NAME = {'claude': 'Claude', 'codex': 'Codex', 'gemini': 'Gemini'}


def _row_service(cap: dict) -> str:
    """The curated service a realm row stands for, if any ('' when it is something else)."""
    sid = str(cap.get('native_service') or cap.get('service_id') or '')
    if sid:
        return sid
    cid = str(cap.get('id') or '')
    for prefix in ('claude.ai ', 'claude_ai_'):
        if cid.lower().startswith(prefix):
            tail = cid[len(prefix):].replace('_', ' ').strip().lower()
            return next((s['id'] for s in SERVICES if s['name'].lower() == tail), '')
    url = str(cap.get('mcp_url') or cap.get('command') or '').strip()
    by_url = next((s['id'] for s in SERVICES if s.get('endpoint') and s['endpoint'] == url), '')
    if by_url:
        return by_url
    # Rows ARMADA named "<service> · <engine>" (or older "· native app" / "· ChatGPT app" ones).
    name = str(cap.get('name') or '').lower()
    return next((s['id'] for s in SERVICES if name.startswith(s['name'].lower() + ' · ')), '')


def added_for(realm_root) -> dict:
    """{service id: set of engines it is already added for} — 'any' for an open server."""
    from . import capabilities, capreach
    out: dict = {}
    try:
        rows = capabilities.catalogue(realm_root).get('connectors') or []
    except (OSError, ValueError):
        return out
    for cap in rows:
        sid = _row_service(cap)
        if sid:
            out.setdefault(sid, set()).add(capreach.reach('connectors', cap).scope)
    return out


def catalogue_entries() -> list:
    """The curated services as Add a capability results, beside the mirrored sources.

    Provider-hosted services (Gmail, Google Drive…) have no public directory ARMADA can search:
    Anthropic publishes none, and Codex's app directory sits behind a browser challenge. These are
    the ones ARMADA knows how to set up per engine. Everything else with an MCP server is in the
    MCP registry results.
    """
    out = []
    for s in SERVICES:
        engines = list(PROVIDERS) if s.get('endpoint') else ['claude', 'codex']
        out.append({'key': 'engine-app:' + s['id'], 'id': s['id'], 'name': s['name'],
                    'kind': 'connectors', 'source': 'engine-apps', 'category': s['category'],
                    'description': s['description'], 'aliases': s.get('aliases', ''), 'author': '',
                    'curated': 'armada', 'service': s['id'], 'engines': engines, 'notes': dict(s['engines']),
                    'reach': 'any' if s.get('endpoint') else 'per-engine'})
    return out



def save(realm_root, *, name='', url='', provider='', server_name='', capability='', service='', account_label='',
         engine=''):
    """Add a remote connector or explicitly link one existing engine registration.

    A provider-hosted service (Gmail, Google Drive…) is added for ONE engine: "Gmail · Claude" or
    "Gmail · Codex". The two are different services behind one brand, so they never share a
    row (docs/dev/CAPABILITIES_UPGRADE.md). An open server is one row for every engine.
    """
    from . import capabilities
    if not isinstance(name, str) or len(name) > 120 or any(ord(c) < 32 for c in name):
        raise ValueError('Use a connector name of at most 120 characters.')
    if not isinstance(account_label, str) or len(account_label) > 80 or any(ord(c) < 32 for c in account_label):
        raise ValueError('Use an account label of at most 80 characters.')
    account_label = account_label.strip()
    if engine not in ('', 'claude', 'codex'):
        raise ValueError('Provider connectors can be added for Claude or Codex.')
    selected = None
    reach = ''
    if service:
        entry = next((s for s in SERVICES if s['id'] == service), None)
        if entry is None:
            # Connect on a row added from the ChatGPT plugin directory: not one of the curated
            # services, but the row already names its plugin, so only the app id is resolved here.
            from .codex_apps import valid_plugin
            if not capability or not valid_plugin(service):
                raise ValueError('Unknown provider connector.')
            entry = {'id': service, 'name': ''}
        name = entry['name'] + (' · ' + account_label if account_label else '')
        if not capability:
            have = added_for(realm_root).get(service, set())
            want = 'any' if entry.get('endpoint') else engine
            if want and (want in have or 'any' in have):
                raise ValueError(f"{entry['name']} is already in this realm"
                                 + ('.' if want == 'any' or 'any' in have else f' for {_ENGINE_NAME[want]}.'))
        if entry.get('endpoint'):
            if capability:
                raise ValueError('Link an existing engine connection to this service.')
            url, service = entry['endpoint'], ''
        elif not capability:
            if not engine:
                raise ValueError('Choose which engine this connection is for: Claude or Codex.')
            reach = engine
            name = f"{entry['name']} · {_ENGINE_ROW_LABEL[engine]}" + (' · ' + account_label if account_label else '')
        # Adding "<service> · Codex" calls no provider: Connect on its Codex row resolves the
        # app later, so a realm can be set up before Codex is installed.
        if service and capability:
            from . import codex_apps
            info = codex_apps.service(service, cwd=realm_root)
            provider, server_name = 'codex', 'app:' + info['app_id']
            selected = {'app_id': info['app_id']}
        elif service:
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
        if cap is not None and selected:
            # One row reaches one service (docs/dev/CAPABILITIES_UPGRADE.md): a ChatGPT app never
            # shares a row with a Claude connector or a public server, in either direction.
            from . import capreach
            current = capreach.bindings(cap)
            servers = any('server_name' in r for r in current.values())
            what = cap.get('name') or cap.get('id')
            if selected.get('app_id') and (capreach.endpoint(cap) or servers or capreach.is_claude_import(cap)):
                raise ValueError(f'{what} is not the Codex version of this service, so Codex can\'t use it. '
                                 'To use the service with Codex, add it for Codex in Add a capability.')
            if not selected.get('app_id') and any('app_id' in r for r in current.values()):
                raise ValueError(f'{what} is the Codex version of this service and works only with Codex. '
                                 'To use the service with another engine, add it for that engine in Add a capability.')
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
        if cap is None and url and not selected:
            same = next((r for r in rows if url in (r.get('mcp_url'), r.get('command'))), None)
            if same is not None:
                raise ValueError(f"{same.get('name') or same.get('id')} already uses this address.")
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
        if service and not capability:
            cap['connection_type'] = 'provider-native'
            cap['description'] = ('A native app in your ChatGPT account; only Codex models can use it.'
                                  if reach == 'codex' else
                                  'A connector in your Claude account; only Claude models can use it.'
                                  if reach == 'claude' else
                                  'A provider connector; each engine has its own version and sign-in.')
        if reach:
            cap['reach'] = reach
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


def add_codex_plugin(realm_root, plugin, *, name='', description=''):
    """Add a ChatGPT plugin from the directory as its own Codex-only connector row.

    Nothing is installed here: install consent and sign-in are ChatGPT's, and Connect on the row
    resolves the plugin's app (codex_apps.service) once it is installed there.
    """
    from . import capabilities, codex_apps
    if not codex_apps.valid_plugin(plugin):
        raise ValueError('Unknown ChatGPT plugin.')
    label = (str(name or '').strip() or plugin)[:100]
    have = added_for(realm_root).get(plugin, set())
    if 'codex' in have or 'any' in have:
        raise ValueError(f'{label} is already in this realm for Codex.')
    path = Path(realm_root) / 'realm.json'
    with util.file_lock(path):
        data = util.read_json_state(path)
        toolkit = data.setdefault('toolkit', {})
        rows = toolkit.setdefault('connectors', [])
        base = registration_id(f'{label} codex'.lower().replace(' ', '-'))
        if base.startswith('-'):
            base = 'armada' + base
        used = {r.get('id') for kind in capabilities.KINDS for r in toolkit.get(kind, [])}
        cid, i = base, 2
        while cid in used:
            cid, i = f'{base}-{i}', i + 1
        cap = {'id': cid, 'name': f'{label} · Codex', 'source': 'custom', 'enabled': True,
               'status': 'configured', 'runs': 'service', 'touch': ['network'],
               'description': (str(description or '').strip()[:280]
                               or 'A plugin in your ChatGPT account; only Codex models can use it.'),
               'connection_type': 'provider-native', 'provider_bindings': {},
               'native_service': plugin, 'reach': 'codex'}
        policy_bindings(cap)
        rows.append(cap)
        util.write_json_atomic(path, data)
    return {'ok': True, 'capability': cid}


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
    from . import capabilities, capreach
    lost = capreach.impact(realm_root, agent, after)
    policy = capabilities.execution_policy(realm_root, agent)
    gone = {x['id'].lower() for x in lost}
    caps = [c for c in capabilities.catalogue(realm_root)['connectors'] if c.get('id') in policy.allowed_mcp_ids]
    missing = [c.get('name') or c['id'] for c in caps
               if str(c.get('id')).lower() not in gone and provider_cap(c, after).get('_unbound')]
    if not lost and not missing:
        return ''
    a = agent if isinstance(agent, dict) else {}
    who = a.get('display') or (agent if isinstance(agent, str) else '') or 'This agent'
    old, new = capreach.LABEL.get(before, before.title()), capreach.LABEL.get(after, after.title())
    lines = [f'Moving from {old} to {new} changes what {who} can use.']
    if lost:
        lines += ['', f'Not available on {new}:'] + [f'• {x["why"]}' for x in lost]
    if missing:
        lines += ['', f'Needs a {new} sign-in first: ' + ', '.join(missing) + '.']
    lines += ['', 'Fix it in Capabilities: move a one-engine-at-a-time connection, add the '
                  f'{new} version of a service, or keep the current model. ARMADA never copies '
                  'sign-ins between engines. Save this model choice anyway?']
    return '\n'.join(lines)
