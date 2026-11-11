"""Credential-free usage readings shared by header, scheduler and agent preambles."""
import datetime as dt
import time
from pathlib import Path
import os
from . import util


def root_path(root):
    return Path(root if isinstance(root, (str, os.PathLike)) else root.root)


def remember(root, provider, data, *, at=None):
    if not root or not data.get('available') or data.get('stale'):
        return
    path = root_path(root) / 'usage-last.json'
    # Explicit allowlist: never mirror an account response or credentials to a realm.
    clean = {k: data[k] for k in ('available', 'plan', 'session', 'weekly', 'model_weekly', 'groups') if k in data}
    if provider == 'codex':
        group = next((g for g in clean.get('groups', []) if g.get('id') == 'codex'), {})
        clean['session'] = next((w for w in group.get('windows', []) if 0 < (w.get('window_minutes') or 0) < 1440), None)
        clean['weekly'] = next((w for w in group.get('windows', []) if w.get('window_minutes') == 10080), None)
    stamp = time.time() if at is None else at
    with util.file_lock(path):
        state = util.read_json_state(path, default=dict)
        entries = state.setdefault('engines', {})
        if stamp >= entries.get(provider, {}).get('at', 0):
            entries[provider] = {'at': stamp, 'read_at': dt.datetime.fromtimestamp(stamp, dt.timezone.utc).isoformat(), **clean}
        if provider == 'claude':
            state.update(at=stamp, data=clean)  # Preserve the existing Claude cache contract.
        util.write_json_atomic(path, state)


def read(root):
    path = root_path(root) / 'usage-last.json'
    with util.file_lock(path):
        state = util.read_json_state(path, default=dict)
    entries = dict(state.get('engines', {}))
    if 'claude' not in entries and state.get('data'):
        entries['claude'] = {'at': state.get('at', 0), **state['data']}
    return entries


def preamble(root):
    try:
        entries = read(root)
    except OSError:
        entries = {}
    lines = ['Usage readings in usage-last.json (percent used; times include timezone):']
    for provider in ('claude', 'codex'):
        row = entries.get(provider, {})
        if not row.get('available'):
            lines.append(f'{provider.title()}: usage unavailable; do not assume there is room.')
            continue
        windows = []
        for label in ('session', 'weekly'):
            value = row.get(label)
            if isinstance(value, dict):
                windows.append(f'{label} {value.get("pct", "?")}% used, resets {value.get("resets_at") or "unknown"}')
        for group in row.get('groups', []):
            windows.extend(f'{group.get("name", "model")} {w.get("label", "window")} {w.get("pct", "?")}% used, resets {w.get("resets_at") or "unknown"}' for w in group.get('windows', []))
        for model, value in row.get('model_weekly', {}).items():
            windows.append(f'{model} weekly {value.get("pct", "?")}% used, resets {value.get("resets_at") or "unknown"}')
        at = row.get('at', 0)
        age = max(0, time.time()-at)
        stamp = dt.datetime.fromtimestamp(at, dt.timezone.utc).isoformat()
        lines.append(f'{provider.title()}: '+ '; '.join(windows)+f' (read {stamp}; {int(age/60)} minutes old'+('; STALE: older than 30 minutes' if age > 1800 else '')+').')
    try:
        from . import run_policy, billing
        credit = run_policy.credit()
        billing.publish_credit(root_path(root), 'claude', credit)
        lines.append(f'Claude API credit: ${credit["spent_usd"]:.2f} of ${credit["cap_usd"]:.2f} spent, ${credit["reserved_usd"]:.2f} reserved; resets {credit["resets_at"]}; '
                     + ('open' if credit['open'] else 'closed: '+credit['reason'])+'.')
    except (OSError, ValueError):
        lines.append('Claude API credit: closed; accounting unavailable.')
    return '\n\n' + '\n'.join(lines)


def refresh(root):
    from . import provider_limits, providers
    for provider in providers.connected():
        provider_limits.read(provider, root, force=True)


def refresh_due(root):
    """Scheduler upkeep also runs while ordinary jobs are held by preflight."""
    from . import provider_limits, providers
    from .sysjobs import is_enabled
    if not is_enabled(root,'usage-readings'):
        return
    entries = read(root)
    for provider in providers.connected():
        if time.time()-entries.get(provider,{}).get('at',0) >= 1500:
            provider_limits.read(provider,root)
