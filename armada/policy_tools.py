"""Invocation-local filesystem tools and durable policy refusal evidence."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import secrets
import threading

from . import access_policy, clock, util
from .managed_tools import ManagedTools, MAX_BYTES, _string, _tool


class PolicyAudit:
    def __init__(self, root, agent):
        self.root, self.agent = Path(root), agent
        self.offered = set()
        self.attempts = []
        self.lock = threading.RLock()

    def offer(self, names):
        with self.lock:
            self.offered.update(names)

    def refuse(self, *, tool='', path='', reason='Denied by owner policy'):
        with self.lock:
            row = {'tool': str(tool), 'path': str(path), 'reason': str(reason),
                   'ts': clock.now().isoformat(timespec='seconds')}
            self.attempts.append(row)
        state = self.root / '.armada' / 'policy-notifications.json'
        with util.file_lock(state):
            data = util.read_json_state(state) if state.exists() else {}
            today = clock.today().isoformat()
            first = data.get(self.agent) != today
            if first:
                data[self.agent] = today
                util.write_json_atomic(state, data)
        if first:
            from . import notify
            notify.emit(self.root, 'policy_denied', 'Agent access refused',
                        f'{self.agent} attempted a denied tool or file write. See the run’s access audit.',
                        href=f'/agent/{self.agent}/skills')

    def report(self):
        with self.lock:
            return {'offered_tools': sorted(self.offered), 'denied_attempts': copy.deepcopy(self.attempts),
                    'warnings': ([f'{len(self.attempts)} tool or file access attempt(s) were refused by owner policy.']
                                 if self.attempts else [])}


class PolicyTools(ManagedTools):
    """File writes are checked on every call; no shell operation is provided."""
    def __init__(self, root, agent, audit, *, cancelled=None):
        super().__init__(root, agent, cancelled=cancelled)
        self.audit = audit
        self.server_name = 'armada_files_' + secrets.token_hex(8)

    def tools(self):
        from .capabilities import execution_policy
        grants = execution_policy(self.root, self.agent)
        if grants.native_filesystem_ids - grants.allowed_mcp_ids:
            return []  # A write scope never grants a withheld filesystem capability.
        return [_tool('write_file', 'Write UTF-8 text within your owner-approved write scope. Paths are relative to the realm. Read-only and control files are refused. Your own memory/*.md notes and valid jobs/_pending/*.json proposals are allowed only within that scope; proposals still need owner approval.',
                      {'path': _string('Realm-relative or absolute output path'), 'content': _string('UTF-8 file contents')},
                      ('path', 'content'), read_only=False),
                _tool('read_file', 'Read an existing file. Does not change it.',
                      {'path': _string('Absolute or realm-relative input path')}, ('path',)),
                _tool('list_directory', 'List files in a directory. Read only.',
                      {'path': _string('Absolute or realm-relative directory path')}, ('path',))]

    def call(self, name, arguments):
        from . import worker
        with self.lock:
            self._authorize()
            try:
                required = {'path', 'content'} if name == 'write_file' else {'path'}
                if (name not in {t['name'] for t in self.tools()} or not isinstance(arguments, dict)
                        or set(arguments) != required or any(not isinstance(v, str) for v in arguments.values())):
                    raise PermissionError('Unknown filesystem tool or invalid arguments.')
                if name == 'write_file':
                    policy = access_policy.load(self.root, self.agent)
                    path = access_policy.writable_path(self.root, policy, arguments['path'], agent_records=True)
                    if len(arguments['content'].encode('utf-8')) > MAX_BYTES:
                        raise ValueError('Files must be at most 1 MiB per write.')
                    content = self._validated_content(path, arguments['content'])
                    with worker.filesystem_identity():
                        path.parent.mkdir(parents=True, exist_ok=True)
                    with worker.filesystem_lock(path):
                        # Re-read authorization while holding the target lock.
                        policy = access_policy.load(self.root, self.agent)
                        if access_policy.writable_path(self.root, policy, arguments['path'], agent_records=True) != path:
                            raise PermissionError('Write target changed during authorization.')
                        with worker.filesystem_identity():
                            util.write_text_atomic(path, content, newline='\n')
                    with worker.filesystem_identity():
                        result = {'path': str(path), 'bytes': path.stat().st_size}
                    self.writes[str(path)] = {'kind': 'output', 'name': path.name, **result}
                    return result
                # Read permissions are unchanged; the write scope is never a read scope.
                path = Path(arguments['path'])
                if not path.is_absolute():
                    path = self.root / path
                if name == 'read_file':
                    return self._read(path)
                with worker.filesystem_identity():
                    return [{'name': p.name, 'kind': 'folder' if p.is_dir() else 'file'}
                            for p in sorted(path.iterdir())][:500]
            except (PermissionError, ValueError) as exc:
                self.audit.refuse(tool=name, path=arguments.get('path', '') if isinstance(arguments, dict) else '', reason=str(exc))
                raise

    def _validated_content(self, path, content):
        from . import control_files, jobs
        if control_files.kind(self.root, path, agent=self.agent) != 'proposal':
            return content
        try:
            proposal = json.loads(content)
        except ValueError as exc:
            raise ValueError('Job proposal must be valid JSON.') from exc
        ok, errors, proposal = jobs.validate(proposal)
        if not ok:
            raise ValueError('Invalid job proposal: ' + '; '.join(errors))
        if path.stem != proposal['id']:
            raise ValueError('Job proposal filename must match its job ID.')
        proposal.pop('approved_at', None)
        proposal.update(proposed_by=self.agent, enabled=False)
        return json.dumps(proposal, ensure_ascii=False, indent=2) + '\n'

    def __enter__(self):
        super().__enter__()
        util.write_json_atomic(self.config_path, {'mcpServers': {self.server_name: self.server_config}})
        self.audit.offer(f'mcp__{self.server_name}__{t["name"]}' for t in self.tools())
        return self

    def configure(self, engine):
        configured = copy.copy(engine)
        configured.policy_tools = self
        # Gemini uses these roots for read permissions too. Native writes are
        # removed by the adapters, so retain the owner's existing read/network reach.
        return configured


def codex_args(tools):
    from .connector_tools import codex_args as configure
    return configure(tools)


def claude_args(tools):
    return ['--mcp-config', str(tools.config_path), '--allowedTools', f'mcp__{tools.server_name}__*']
