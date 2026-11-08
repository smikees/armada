"""Strict, provider-neutral connector tool and filesystem write policy.

The owner edits policy; models cannot grant permissions. Missing fields preserve
legacy behavior, whereas an explicit empty allowlist grants nothing.
"""
from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from functools import cache
from pathlib import Path, PureWindowsPath
import re

from . import util


def error(message):
    from .capabilities import CapabilityPolicyError
    return CapabilityPolicyError('Capability policy: ' + message)


def patterns(value, label, *, paths=False):
    if not isinstance(value, list) or len(value) > 500:
        raise error(f'{label} must be a list of at most 500 glob patterns.')
    out = []
    for value in value:
        if not isinstance(value, str) or not value or value != value.strip() or len(value) > 500:
            raise error(f'{label} contains an invalid glob pattern.')
        if any(ord(c) < 32 for c in value) or any(c in value for c in '{}'):
            raise error(f'{label} contains an invalid glob pattern.')
        # fnmatch silently treats broken character classes as literals. Reject typos.
        remainder = re.sub(r'\[!?[^\[\]]+\]', '', value)
        if '[' in remainder or ']' in remainder:
            raise error(f'{label} contains a malformed character class.')
        if paths:
            value = value.replace('\\', '/')
            if (PureWindowsPath(value).drive or value.startswith('/') or ':' in value
                    or any(p in ('', '.', '..') or p.endswith((' ', '.')) for p in value.split('/'))):
                raise error(f'{label} paths must be relative to the realm, without traversal or drive names.')
        elif not re.fullmatch(r'[A-Za-z0-9_.?*\[\]!\-]+', value):
            raise error(f'{label} must match tool names, not qualified server names or commands.')
        out.append(value)
    return tuple(out)


@dataclass(frozen=True)
class ToolRule:
    allow: tuple[str, ...] | None = None
    deny: tuple[str, ...] = ()
    default_deny: tuple[str, ...] = ()

    def permits(self, tool):
        if any(fnmatchcase(tool, p) for p in self.deny):
            return False
        explicit = self.allow is not None and any(fnmatchcase(tool, p) for p in self.allow)
        if self.allow is not None and not explicit:
            return False
        return explicit or not any(fnmatchcase(tool, p) for p in self.default_deny)


@dataclass(frozen=True)
class AccessPolicy:
    tools: tuple[tuple[str, ToolRule], ...] = ()
    write_scope: tuple[str, ...] | None = None
    read_only: tuple[str, ...] = ()
    builder: bool = False
    agent: str = ''

    @property
    def scoped(self):
        return not self.builder and (self.write_scope is not None or bool(self.read_only))

    def rule(self, connector):
        return dict(self.tools).get(connector, ToolRule())


def validate(realm, agent):
    """Validate even unused policies; a malformed policy never becomes unrestricted."""
    from .capabilities import _policy_toolkit
    _policy_toolkit(realm, 'realm')
    _policy_toolkit(agent, 'agent', grants_only=True)
    catalogue = {c.get('id') for k in ('connectors', 'extensions', 'plugins')
                 for c in (realm.get('toolkit') or {}).get(k, []) if isinstance(c, dict)}
    defaults = realm.get('tool_policy', {})
    overrides = agent.get('tool_policy', {})
    rules = {}
    for label, entries, is_default in (('realm.tool_policy', defaults, True),
                                        ('agent.tool_policy', overrides, False)):
        if not isinstance(entries, dict):
            raise error(f'{label} must be an object keyed by connector ID.')
        for connector, entry in entries.items():
            if connector not in catalogue:
                raise error(f'{label} references unknown connector {connector!r}.')
            fields = {'deny'} if is_default else {'allow', 'deny'}
            if not isinstance(entry, dict) or set(entry) - fields:
                raise error(f'{label}.{connector} accepts only ' + ', '.join(sorted(fields)) + '.')
            if not is_default and 'allow' not in entry:
                raise error(f'{label}.{connector}.allow is required (use [] to deny all tools).')
            previous = rules.get(connector, ToolRule())
            deny = patterns(entry.get('deny', []), f'{label}.{connector}.deny')
            rules[connector] = (ToolRule(default_deny=deny) if is_default else
                ToolRule(patterns(entry['allow'], f'{label}.{connector}.allow'), deny, previous.default_deny))
    scope = patterns(agent['write_scope'], 'agent.write_scope', paths=True) if 'write_scope' in agent else None
    readonly = patterns(realm.get('read_only', []), 'realm.read_only', paths=True)
    builder = realm.get('policy_builder', 'builder')
    if not isinstance(builder, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', builder):
        raise error('realm.policy_builder must be an agent ID.')
    return AccessPolicy(tuple(sorted(rules.items())), scope, readonly, agent.get('id') == builder,
                        str(agent.get('id') or ''))


def load(root, agent):
    from .capabilities import _policy_json
    root = Path(root)
    a = agent if isinstance(agent, dict) else {
        **_policy_json(root / 'agents' / util.safe_seg(agent, 'agent') / 'agent.json'), 'id': agent}
    return validate(_policy_json(root / 'realm.json'), a)


def path_matches(path, pattern):
    """Case-insensitive path globs: * stays in a segment; ** spans folders."""
    parts, pats = path.casefold().split('/'), pattern.casefold().split('/')
    @cache
    def match(i, j):
        if j == len(pats):
            return i == len(parts)
        if pats[j] == '**':
            return match(i, j + 1) or (i < len(parts) and match(i + 1, j))
        return i < len(parts) and fnmatchcase(parts[i], pats[j]) and match(i + 1, j + 1)
    return match(0, 0)


def writable_path(root, policy, value, *, agent_records=False):
    """Validate the canonical target and every ancestor before any write occurs."""
    from .inspection import checked_path
    root = Path(root).resolve()
    raw = Path(value)
    target = checked_path(raw if raw.is_absolute() else root / raw, [root])
    relative = target.relative_to(root).as_posix()
    if not policy.scoped:
        return target
    from .control_files import kind
    record = kind(root, target, agent=policy.agent)
    # Only PolicyTools opts into the agent's own notes and validated pending proposals.
    # Generic output/draft writers never inherit that exception.
    if record == 'control' or (record in ('memory', 'proposal') and not agent_records):
        raise PermissionError('Write refused: ARMADA control files are owner-managed.')
    if any(path_matches(relative, p) for p in policy.read_only):
        raise PermissionError('Write refused: this path is read-only for agents.')
    if policy.write_scope is not None and not any(path_matches(relative, p) for p in policy.write_scope):
        raise PermissionError('Write refused: this path is outside the agent write scope.')
    return target


def _updated(before, changes, agent):
    fields = {'tool_policy', 'write_scope'} if agent else {'tool_policy', 'read_only', 'policy_builder'}
    if not isinstance(changes, dict) or set(changes) - fields:
        raise error('unknown access-policy field.')
    updated = dict(before)
    for key, value in changes.items():
        if key == 'write_scope' and value is None:
            updated.pop(key, None)
        else:
            updated[key] = value
    return updated, fields


def preview(root, agent, changes, provider, *, realm_defaults=False):
    """Evaluate an unsaved owner edit with the execution validator, without writes or discovery."""
    from . import capabilities, tool_admission
    if provider not in ('claude', 'codex', 'gemini'):
        raise error('Unknown provider.')
    root = Path(root)
    agent = util.safe_seg(agent, 'agent')
    realm = capabilities._policy_json(root / 'realm.json')
    data = capabilities._policy_json(root / 'agents' / agent / 'agent.json')
    before = validate(realm, dict(data, id=agent))
    if realm_defaults:
        realm, _ = _updated(realm, changes, None)
        validate(realm, {})
        for path in (root / 'agents').glob('*/agent.json'):
            validate(realm, capabilities._policy_json(path))
    else:
        data, _ = _updated(data, changes, agent)
    after = validate(realm, dict(data, id=agent))
    grants = capabilities.execution_policy(root, agent)
    previous = {row['id']: row for row in tool_admission.describe_access(root, provider, before, grants)}
    rows = tool_admission.describe_access(root, provider, after, grants)
    for row in rows:
        old = set(previous[row['id']]['can_call'])
        row['newly_allowed'] = [n for n in row['can_call'] if n not in old]
        row['newly_denied'] = sorted(old - set(row['can_call']))
    return {'ok': True, 'agent': agent, 'connectors': rows, 'builder': after.builder,
            'write_scope': after.write_scope, 'read_only': after.read_only, 'scoped': after.scoped,
            'notice': 'Preview only; nothing saved. Uses recorded tool names and current connector grants. '
                      'Provider availability and permissions are checked again when a run starts.'}


def save(root, agent, changes):
    """Owner API mutation; policy and its change log are one locked atomic write."""
    from . import clock
    from .capabilities import _policy_json
    root = Path(root)
    path = root / 'agents' / util.safe_seg(agent, 'agent') / 'agent.json' if agent else root / 'realm.json'
    with util.file_lock(path):
        before = _policy_json(path)
        updated, fields = _updated(before, changes, agent)
        if agent:
            validate(_policy_json(root / 'realm.json'), updated)
        else:
            validate(updated, {})
            for ap in (root / 'agents').glob('*/agent.json'):
                validate(updated, _policy_json(ap))
        updated['_policy_changes'] = list(before.get('_policy_changes', [])) + [{
            'ts': clock.now().isoformat(timespec='seconds'), 'actor': 'owner',
            'before': {k: before[k] for k in fields if k in before},
            'after': {k: updated[k] for k in fields if k in updated}}]
        util.write_json_atomic(path, updated)
    return {'ok': True}
