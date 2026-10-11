"""Turn-scoped connector setup alongside normal tools; never grants data access."""
from __future__ import annotations

import copy
import json
import secrets

from . import capabilities, connector_runtime, providers
from .managed_tools import ManagedTools, _tool, _string


class ConnectorTools(ManagedTools):
    """Prepare already-approved connectors; the owner completes provider sign-in."""

    def __init__(self, root, agent, *, cancelled=None):
        super().__init__(root, agent, cancelled=cancelled)
        self.server_name = 'armada_setup_' + secrets.token_hex(8)
        self.actions = []

    def tools(self):
        return [
            _tool('list_connectors', 'List your realm-approved connectors and independent engine connection states. No credentials.'),
            _tool('connect_connector', 'Prepare/sign in an existing connector approved for you. The owner completes browser sign-in. Never changes grants, disabled realm capabilities, endpoints or other registrations. Newly connected tools load next turn.',
                  {'capability': _string('Exact connector ID from list_connectors'),
                   'provider': {'type': 'string', 'enum': ['claude', 'codex', 'gemini']}},
                  ('capability', 'provider'), read_only=False),
            _tool('request_connector_access', 'Ask the owner to approve access to an existing realm connector. A coordinator can request it for another agent; never grants it automatically.',
                  {'capability': _string('Exact connector ID'), 'agent': _string('Agent ID; omit for yourself'),
                   'reason': _string('Why access is needed')}, ('capability', 'reason'), read_only=False),
        ]

    def _approved(self):
        policy = capabilities.execution_policy(self.root, self.agent)
        return [c for c in capabilities.catalogue(self.root)['connectors']
                if c.get('id') in policy.allowed_mcp_ids and capabilities.realm_enabled(c)]

    def call(self, name, arguments):
        with self.lock:
            self._authorize()
            schema = next((t['inputSchema'] for t in self.tools() if t['name'] == name), None)
            if (not schema or not isinstance(arguments, dict) or set(arguments) - set(schema['properties'])
                    or any(k not in arguments for k in schema['required'])
                    or any(not isinstance(v, str) or len(v) > 1000 for v in arguments.values())):
                raise ValueError('Unknown connector tool or invalid arguments.')
            if name == 'list_connectors':
                approved = self._approved()
                if not approved:
                    return {'connectors': []}
                snapshot = connector_runtime.connection_snapshot(self.root)
                return {'connectors': [{'id': c['id'], 'name': c.get('name') or c['id'],
                        'connections': {p: {k: v for k, v in
                                            (snapshot['connectors'].get(c['id'], {}).get('details', {}).get(p) or {}).items()
                                            if k in ('state', 'reason', 'tool_names')}
                                        for p in ('claude', 'codex', 'gemini')}} for c in approved]}
            cid = arguments['capability']
            kind, cap = capabilities.find(self.root, cid)
            if kind != 'connectors' or not cap:
                raise ValueError('Connector is not in this realm. Ask the owner to add/review it in Capabilities.')
            if name == 'request_connector_access':
                target = arguments.get('agent') or self.agent
                from . import util
                agent = util.read_json_state(self.root / 'agents' / self.agent / 'agent.json')
                if target != self.agent and not agent.get('coordinator'):
                    raise ValueError('Only the coordinator can request access for another agent.')
                target = util.safe_seg(target, 'agent')
                if not (self.root / 'agents' / target / 'agent.json').is_file():
                    raise ValueError('Agent is not in this realm.')
                result = capabilities.request(self.root, target, cid, arguments['reason'])
            else:
                provider = arguments['provider']
                if provider not in ('claude', 'codex', 'gemini'):
                    raise ValueError('Unknown connector provider.')
                if cid not in {c['id'] for c in self._approved()}:
                    raise ValueError('Connector is disabled or not approved for you. Request owner approval first.')
                from . import capreach
                if not capreach.reach('connectors', cap).available_on(provider):
                    raise ValueError('This connector does not work with that engine. Use its supported connection.')
                providers.require_allowed(provider)
                if providers.status(provider, force=True).get('connected') is not True:
                    raise ValueError('Connect this engine in Settings → App first.')
                connect = {'claude': connector_runtime.connect_claude, 'codex': connector_runtime.connect_codex,
                           'gemini': connector_runtime.connect_gemini}[provider]
                result = connect(cap, self.root, authenticate=True) if provider == 'gemini' else connect(cap, self.root)
                result = {k: v for k, v in result.items() if k != 'login_url'}
                if result.get('ok'):
                    result = {**result, 'note': 'The owner completes sign-in. Recheck with list_connectors; data tools load on the next conversation turn.'}
            # Audit identities and state only, never authorization URLs or credentials.
            self.actions.append({'tool': name, 'capability': cid, 'provider': arguments.get('provider', ''),
                                 'agent': arguments.get('agent') or self.agent,
                                 'ok': result.get('ok') is True, 'state': result.get('state', '')})
            return result

    def __enter__(self):
        super().__enter__()
        self.config_path.write_text(json.dumps({'mcpServers': {self.server_name: self.server_config}}), encoding='utf-8')
        return self

    def configure(self, engine):
        configured = copy.copy(engine)
        configured.connector_tools = self
        return configured


def claude_args(tools):
    return ['--mcp-config', str(tools.config_path), '--allowedTools', f'mcp__{tools.server_name}__*']


def codex_args(tools):
    args = []
    for key in ('command', 'args', 'env'):
        value = tools.server_config[key]
        if key == 'env':
            value = '{' + ','.join(json.dumps(k) + '=' + json.dumps(v) for k, v in value.items()) + '}'
        else:
            value = json.dumps(value)
        args += ['-c', f'mcp_servers.{tools.server_name}.{key}={value}']
    return args + ['-c', f'mcp_servers.{tools.server_name}.enabled=true',
                   '-c', f'mcp_servers.{tools.server_name}.default_tools_approval_mode="approve"',
                   '-c', f'mcp_servers.{tools.server_name}.tool_timeout_sec=180']
