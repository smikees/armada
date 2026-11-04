"""Owner-triggered, no-model connector discovery for closed tool policies."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import time

from . import capabilities, tool_admission, util
from .connector_registry import provider_cap
from .engine.mcp import registration_id, server_id


def claude_inventory(engine, cwd):
    from .engine.process import supervise_rpc
    rows = {}
    polls = 0
    def request(send, rid, subtype):
        send({'type': 'control_request', 'request_id': str(rid), 'request': {'subtype': subtype}})
    def accept(message, send):
        nonlocal polls
        if message.get('type') == 'control_request':
            send({'type': 'control_response', 'response': {'subtype': 'error',
                  'request_id': message['request_id'], 'error': 'Inventory only; no actions permitted.'}})
        if message.get('type') != 'control_response':
            return False
        reply = message.get('response', {})
        if reply.get('subtype') == 'error':
            raise ValueError('Claude cannot read its live connector tool inventory.')
        if reply.get('request_id') == '1':
            request(send, 2, 'mcp_status')
            return False
        servers = reply.get('response', {}).get('mcpServers', [])
        if any(row.get('status') == 'pending' for row in servers):
            polls += 1
            if polls >= 100:
                raise ValueError('Claude connectors are still starting. Wait for them, then refresh tool names again.')
            time.sleep(.2)
            request(send, polls + 2, 'mcp_status')
            return False
        for row in servers:
            if row.get('status') == 'connected' and isinstance(row.get('tools'), list):
                rows[server_id(row['name'])] = [t['name'] for t in row['tools']]
        return True
    args = engine._launcher() + ['-p', '--input-format', 'stream-json', '--output-format', 'stream-json',
        '--verbose', '--tools', '', '--disable-slash-commands', '--permission-mode', 'dontAsk']
    args += engine._mcp_args([], cwd)
    result = supervise_rpc(args, start=lambda send: request(send, 1, 'initialize'),
                           on_message=accept, timeout=45, cwd=str(cwd), env=engine._env())
    if result.error:
        raise ValueError('Claude tool inventory could not be read: ' + result.error)
    return rows


def gemini_inventory(engine, cwd):
    """Read the CLI startup envelope without ever sending a user/model turn."""
    from .engine.process import supervise_rpc
    rows = {}
    with tempfile.TemporaryDirectory(prefix='armada-inventory-') as folder:
        agent = Path(folder) / '.agents/agents/armada-turn.md'
        agent.parent.mkdir(parents=True)
        agent.write_text(engine._agent('Connector inventory only.', True, []), encoding='utf-8')
        def accept(message, send):
            if message.get('event') != 'init':
                return False
            data = message.get('init', message)
            for row in data.get('mcp_servers', []):
                if isinstance(row, dict) and isinstance(row.get('tools'), list):
                    rows[row['name']] = [t['name'] if isinstance(t, dict) else t for t in row['tools']]
            # Some CLI versions expose fully-qualified names in the startup tools list.
            for tool in data.get('tools', []):
                name = tool.get('name', '') if isinstance(tool, dict) else tool
                for sid in engine.allowed_mcp_ids:
                    prefix = 'mcp__' + sid + '__'
                    if isinstance(name, str) and name.startswith(prefix):
                        rows.setdefault(sid, []).append(name[len(prefix):])
            return True
        result = supervise_rpc(engine._launcher() + ['--agent', 'armada-turn', '--disable-slash-commands',
            '--input-format', 'stream-json', '--output-format', 'stream-json'], start=lambda send: None,
            on_message=accept, timeout=45, cwd=folder)
        if result.error:
            raise ValueError('Gemini tool inventory could not be read: ' + result.error)
    return rows


def refresh(root, agent, provider):
    from .engine import get_engine
    from .engine.contracts import ExecutionPolicy
    if provider not in ('claude', 'codex', 'gemini'):
        raise ValueError('Choose Claude, Codex or Gemini to refresh tools.')
    agent = util.safe_seg(agent, 'agent')
    policy = capabilities.execution_policy(root, agent)
    translated = capabilities.provider_policy(policy, provider)
    engine = get_engine(provider).configure(ExecutionPolicy(translated.allowed_mcp_ids))
    if provider == 'claude':
        rows = claude_inventory(engine, root)
    elif provider == 'gemini':
        rows = gemini_inventory(engine, root)
    else:
        from .connector_runtime import codex_live_inventory
        data = codex_live_inventory(root, engine) or {}
        rows = {sid: row['tool_names'] for sid, row in data.items()
                if row.get('runtime_state') == 'ready' and isinstance(row.get('tool_names'), list)}
    count = 0
    for kind, cap in capabilities.catalogue_flat(root):
        if cap.get('id') not in policy.allowed_mcp_ids:
            continue
        actual = provider_cap(cap, provider)
        sid = server_id(actual['id']) if provider == 'claude' else registration_id(actual['id'])
        if sid in rows:
            tool_admission.remember(root, cap['id'], rows[sid], provider)
            count += 1
    if not count:
        raise ValueError('The engine returned no verified connector tool names. Check sign-in and connector startup, then refresh again. Existing policy remains enforced.')
    return {'ok': True, 'connectors': count}
