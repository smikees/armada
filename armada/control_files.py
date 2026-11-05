"""Shared classification of application state versus model-authored output.

Classification does not grant access. Callers must still validate canonical paths,
owner scopes and the operation's content. Owner APIs and the trusted builder do
not use the scoped model-write boundary.
"""
from pathlib import Path


CONTROL_NAMES = frozenset({
    'agent.json', 'realm.json', 'theme.json', 'dashboard.json', 'skills.json',
    'system_jobs.json', 'notifications.jsonl', 'notifications.state.json',
    'agent.md', 'agents.md', 'claude.md', 'mandate.md', 'soul.md', 'tenets.md',
    'objectives.md', 'core-context.md', 'final-answer.md',
})
CONTROL_DIRS = frozenset({
    'memory', 'memories', 'jobs', 'threads', 'runs', 'inbox', 'goals', 'addons',
    'capture-index', 'memory-audits', '.matcap',
})


def kind(root, target, *, agent=''):
    """Classify an already checked path as control, own memory, proposal or output."""
    root, target = Path(root).resolve(), Path(target)
    parts = tuple(p.casefold() for p in target.relative_to(root).parts)
    if not parts or any(p.startswith('.') for p in parts) or parts[-1] in CONTROL_NAMES:
        return 'control'
    # A broad data grant must not turn an embedded realm into writable output.
    for parent in target.parents:
        if parent == root:
            break
        if (parent / 'realm.json').is_file():
            return 'control'
    own = bool(agent) and len(parts) >= 3 and parts[:2] == ('agents', agent.casefold())
    if own and len(parts) == 5 and parts[2:4] == ('jobs', '_pending') and target.suffix.lower() == '.json':
        return 'proposal'
    if own and len(parts) == 4 and parts[2] == 'memory' and target.suffix.lower() == '.md':
        return 'memory'
    if parts[0] in CONTROL_DIRS or (len(parts) >= 3 and parts[0] == 'agents' and parts[2] in CONTROL_DIRS):
        return 'control'
    return 'output'
