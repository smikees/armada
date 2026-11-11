"""Compile glob policy to closed, concrete provider tool lists.

Inventories are names only, never credentials. Exact allowlists prevent a newly
added server tool from acquiring access until its inventory has been refreshed.
"""
from __future__ import annotations

from pathlib import Path
import re

from . import access_policy, capabilities, util
from .connector_registry import provider_cap
from .engine.mcp import registration_id, server_id

TOOL_NAME = re.compile(r'[A-Za-z0-9_.-]{1,200}')


def native_limits(names, entry, allow_key, deny_key):
    """Intersect ARMADA grants with existing provider restrictions."""
    selected = set(names)
    if not isinstance(entry, dict):
        raise access_policy.error('invalid provider connector configuration.')
    for key in (allow_key, deny_key):
        values = entry.get(key)
        if values is None:
            continue
        if not isinstance(values, list) or any(not isinstance(n, str) or not TOOL_NAME.fullmatch(n) for n in values):
            raise access_policy.error('invalid provider tool restrictions; repair the connector configuration.')
        selected = selected & set(values) if key == allow_key else selected - set(values)
    return sorted(selected)


def inventory(root):
    path = Path(root) / '.armada' / 'tool-inventory.json'
    return util.read_json_state(path) if path.exists() else {}


def remember(root, connector, names, provider):
    if not isinstance(names, list) or any(not isinstance(n, str) or not TOOL_NAME.fullmatch(n) for n in names):
        raise access_policy.error('connector returned an invalid tool inventory.')
    save_names(root, connector, names)
    path = Path(root) / '.armada' / 'tool-inventory.json'
    with util.file_lock(path):
        data = inventory(root)
        data.setdefault(connector, {})[provider] = sorted(set(names))
        util.write_json_atomic(path, data)


def save_names(root, connector, names):
    """Owner-confirmed inventory for providers without a no-model listing API."""
    from . import clock
    if not isinstance(names, list) or len(names) > 5000 or any(
            not isinstance(n, str) or not TOOL_NAME.fullmatch(n) for n in names):
        raise access_policy.error('tool names must be a list of exact names, without globs.')
    path = Path(root) / 'realm.json'
    with util.file_lock(path):
        realm = capabilities._policy_json(path)
        cap = next((c for kind in capabilities.MCP_KINDS for c in realm.get('toolkit', {}).get(kind, [])
                    if c.get('id') == connector), None)
        if cap is None:
            raise access_policy.error('unknown connector.')
        before = cap.get('tool_names', [])
        cap['tool_names'] = sorted(set(names))
        realm.setdefault('_policy_changes', []).append({'ts': clock.now().isoformat(timespec='seconds'),
            'actor': 'owner', 'connector': connector, 'before_tool_names': before, 'after_tool_names': cap['tool_names']})
        util.write_json_atomic(path, realm)
    return {'ok': True}


def known_names(root, cap, provider):
    data = inventory(root).get(cap['id'], {})
    # Bindings are owner-confirmed instances of the same logical connector. Names
    # from another binding may be absent, but cannot authorize a different name.
    values = cap.get('tool_names', [])
    if not isinstance(values, list):
        raise access_policy.error('connector tool_names must be a list.')
    values = list(values)
    if 'tool_names' not in cap:
        for names in data.values():
            if not isinstance(names, list):
                raise access_policy.error('invalid saved connector tool inventory; refresh it.')
            values.extend(names)
    if any(not isinstance(n, str) or not TOOL_NAME.fullmatch(n) for n in values):
        raise access_policy.error('invalid saved connector tool inventory; refresh it.')
    return sorted(set(values))


def compile_rules(root, provider, policy, grants):
    """Pure local compilation shared by execution and owner previews; does not grant access."""
    compiled, denied, logical = {}, {}, {}
    for kind, cap in capabilities.catalogue_flat(root):
        cid = cap.get('id')
        if kind not in capabilities.MCP_KINDS or not cid or cid not in grants.allowed_mcp_ids:
            continue
        actual = provider_cap(cap, provider)
        if actual.get('_unbound'):
            continue
        from .capreach import reach
        if provider in ('claude', 'codex', 'gemini') and not reach(kind, cap).available_on(provider):
            continue
        sid = server_id(actual['id']) if provider == 'claude' else registration_id(actual['id'])
        if cid not in dict(policy.tools) and not (policy.scoped and cid in grants.native_filesystem_ids):
            continue
        if actual.get('_native_app'):
            raise access_policy.error('tool policies require an MCP connection; native apps cannot enforce this policy.')
        names = known_names(root, cap, provider)
        rule = policy.rule(cid)
        # Literal grants need no discovery. Glob grants never invent tool names.
        names = sorted(set(names) | {p for p in rule.allow or () if TOOL_NAME.fullmatch(p)})
        blocked_filesystem = policy.scoped and cid in grants.native_filesystem_ids
        if not names and not blocked_filesystem and rule.allow != ():
            raise access_policy.error(f'No tool inventory for {cid}. Refresh connector tools before running this policy.')
        allowed = set(n for n in names if rule.permits(n)) if not blocked_filesystem else set()
        # Multiple logical capabilities pointing to the same registration intersect.
        compiled[sid] = sorted(allowed & set(compiled.get(sid, allowed)))
        denied[sid] = sorted(set(denied.get(sid, ())) | (set(names) - allowed))
        logical.setdefault(sid, []).append(cid)
    return compiled, denied, logical


def describe_access(root, provider, policy, grants):
    """Local presentation of compiled access; provider login/CLI capability is checked at run time."""
    from .capreach import reach
    normalize = server_id if provider == 'claude' else registration_id
    provider_grants = capabilities.provider_policy(grants, provider)
    offered_servers = {normalize(s) for s in provider_grants.allowed_mcp_ids}
    run_error = ''
    try:
        compiled, _, _ = compile_rules(root, provider, policy, grants)
    except ValueError as exc:
        compiled, run_error = {}, str(exc)
    rows = []
    for kind, cap in capabilities.catalogue_flat(root):
        cid = cap.get('id')
        if kind not in capabilities.MCP_KINDS or not cid:
            continue
        known = known_names(root, cap, provider)
        rule = policy.rule(cid)
        literals = {p for p in rule.allow or () if TOOL_NAME.fullmatch(p)}
        names = sorted(set(known) | literals)
        actual = provider_cap(cap, provider)
        sid = normalize(actual.get('id') or cid)
        reason = run_error
        offered = actual['id'] in provider_grants.allowed_app_ids if actual.get('_native_app') else sid in offered_servers
        if not reason and (cid not in grants.allowed_mcp_ids or not offered):
            reason = 'This connector is not granted for this engine.'
        if not reason and (actual.get('_unbound') or not reach(kind, cap).available_on(provider)):
            reason = 'This connector has no supported connection for this engine.'
        if not reason and policy.scoped and cid in grants.native_filesystem_ids:
            reason = 'The guarded file tool replaces this connector for restricted file access.'
        allowed = [n for n in names if not reason and rule.permits(n)
                   and (sid not in compiled or n in compiled[sid])]
        rows.append({'id': cid, 'name': cap.get('name') or cid, 'can_call': allowed,
                     'cannot_call': [n for n in names if n not in allowed],
                     'inventory_known': bool(known), 'literal_names': sorted(literals - set(known)),
                     'reason': reason})
    return rows


class ToolAdmission:
    def __init__(self, root, agent, provider, audit):
        self.root, self.agent, self.provider, self.audit = Path(root), agent, provider, audit
        self.policy = access_policy.load(root, agent)
        if (self.policy.tools or self.policy.scoped) and provider not in ('claude', 'codex', 'gemini', 'mock'):
            raise access_policy.error('this engine cannot enforce tool policies or write scopes.')
        grants = capabilities.execution_policy(root, agent)
        self.granted = capabilities.provider_policy(grants, provider).allowed_mcp_ids
        self.seen_attempts = set()
        self.allowed, self.denied, self.logical = compile_rules(root, provider, self.policy, grants)

    def offer(self, sid, names):
        selected = [n for n in names if sid not in self.allowed or n in self.allowed[sid]]
        self.audit.offer(f'mcp__{sid}__{n}' for n in selected)
        return selected

    def observe(self, event):
        if event.get('kind') not in ('tool', 'tool_result'):
            return
        name = event.get('name', '')
        key = (event.get('id'), name)
        if event.get('id'):
            if key in self.seen_attempts:
                return
            self.seen_attempts.add(key)
        granted = {server_id(s) if self.provider == 'claude' else registration_id(s) for s in self.granted}
        if name.startswith('mcp__') and '__' in name[5:]:
            sid = name[5:].split('__', 1)[0]
            if sid not in granted and not sid.startswith('armada_'):
                self.audit.refuse(tool=name, reason='Connector is not granted to this agent.')
                return
        for sid, names in self.allowed.items():
            prefix = f'mcp__{sid}__'
            if name.startswith(prefix) and name[len(prefix):] not in names:
                self.audit.refuse(tool=name, reason='Connector tool is outside the permitted list.')
                return
        if self.allowed and name in ('Agent', 'Task'):
            self.audit.refuse(tool=name, reason='Child agents are unavailable under connector tool restrictions.')
            return
        if self.policy.scoped and name in ('Bash', 'PowerShell', 'Write', 'Edit', 'MultiEdit', 'NotebookEdit', 'Agent', 'Task',
                                           'shell', 'exec_command', 'apply_patch', 'run_command', 'write_to_file',
                                           'replace_file_content', 'multi_replace_file_content'):
            params = event.get('input') or {}
            self.audit.refuse(tool=name, path=params.get('file_path') or params.get('path') or '',
                              reason='Native writes and shell are disabled; use the scoped filesystem tool.')

    def observed_tools(self, names):
        """Record adapter startup evidence, checking it against the compiled policy."""
        if not isinstance(names, list) or any(not isinstance(n, str) for n in names):
            raise access_policy.error('engine returned an invalid offered-tool list.')
        for name in names:
            for sid, allowed in self.allowed.items():
                prefix = f'mcp__{sid}__'
                if name.startswith(prefix) and name[len(prefix):] not in allowed:
                    raise access_policy.error('engine exposed a tool outside the compiled allowlist; run aborted.')
        self.audit.offer(names)


def claude_args(engine):
    admission = getattr(engine, 'tool_admission', None)
    files = getattr(engine, 'policy_tools', None)
    if not admission or (not admission.allowed and not files):
        return []
    # --agent's tools list, unlike --allowedTools, removes unlisted MCP schemas.
    # Do not offer Agent/Task: child agents must not regain a wider native pool.
    builtins = ['Read', 'Glob', 'Grep', 'WebSearch', 'WebFetch']
    if not files:
        builtins += ['Bash', 'Write', 'Edit', 'NotebookEdit']
        from . import worker
        if worker.enabled():
            builtins += ['PowerShell']
    offered = list(builtins)
    for sid in sorted(engine.allowed_mcp_ids):
        sid = server_id(sid)
        if sid in admission.allowed:
            offered.extend(f'mcp__{sid}__{n}' for n in admission.offer(sid, admission.allowed[sid]))
        else:
            offered.append(f'mcp__{sid}__*')
    for toolset in (files, getattr(engine, 'connector_tools', None)):
        if toolset:
            offered.extend(f'mcp__{toolset.server_name}__{t["name"]}' for t in toolset.tools())
    admission.audit.offer(builtins)
    import json
    args = ['--agents', json.dumps({'armada-policy': {'description': 'Current ARMADA agent with owner tool limits.',
             'prompt': '', 'tools': sorted(set(offered))}}), '--agent', 'armada-policy',
            '--disable-slash-commands']
    denied = [f'mcp__{sid}__{n}' for sid, names in admission.denied.items() for n in names]
    if files:
        denied += ['Bash', 'PowerShell', 'Write', 'Edit', 'NotebookEdit', 'Agent', 'Task']
        from .policy_tools import claude_args as file_args
        args += file_args(files)
    if denied:
        args += ['--disallowedTools', *sorted(set(denied))]
    return args


def verify_engine_version(engine):
    """Do not let an older CLI silently ignore newly enforced config keys."""
    admission = getattr(engine, 'tool_admission', None)
    if not admission or (not admission.allowed and not getattr(engine, 'policy_tools', None)):
        return
    minimum = {'codex': (0, 157, 1), 'gemini': (1, 5, 0)}.get(engine.name)
    if minimum is None:
        return  # Claude already validates its minimum in _mcp_args.
    reply = engine._probe(['--version'])
    match = re.search(r'\b(\d+)\.(\d+)\.(\d+)\b', reply.stdout)
    if reply.returncode or not match or tuple(map(int, match.groups())) < minimum:
        raise access_policy.error(f'{engine.name.title()} tool policies require CLI ' + '.'.join(map(str, minimum)) + ' or newer. Update the engine before running this agent.')
