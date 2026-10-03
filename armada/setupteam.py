"""Edit a wizard's existing team without replacing its realm or agent histories."""
import json
import logging
from pathlib import Path
import tempfile

from . import setupflow, starter_profiles, util, covenant
from .templates import TEMPLATES

log = logging.getLogger(__name__)


def draft(root) -> dict:
    root = Path(root)
    cfg = json.loads((root / 'realm.json').read_text(encoding='utf-8-sig'))
    template = cfg.get('template', 'scratch')
    ids = {a['id'] for a in starter_profiles.roster(template)}
    keep, extra = [], []
    for path in sorted((root / 'agents').glob('*/agent.json')):
        a = json.loads(path.read_text(encoding='utf-8-sig'))
        if path.parent.name in ids:
            keep.append(path.parent.name)
            continue
        profile = {k: a.get(k, '') for k in ('display', 'role', 'leader')}
        profile['coordinator'] = bool(a.get('coordinator'))
        profile['saved_id'] = path.parent.name
        for key, filename in (('mandate', 'mandate.md'), ('voice', 'soul.md'), ('tenets', 'tenets.md')):
            f = path.parent / filename
            profile[key] = f.read_text(encoding='utf-8') if f.exists() else ''
        avatar = path.parent / 'avatar.png'
        if avatar.exists():
            profile['avatar_url'] = '/avatar/' + path.parent.name
        extra.append(profile)
    return {'name': cfg.get('name', root.name), 'owner': setupflow.owner_of(root),
            'template': template, 'keep': keep, 'extra': extra}


def update(root, body: dict, agents: list) -> dict:
    """Stage additions, archive removals, and roll back file changes on write failures.

    Existing profile settings and work survive. Only unchanged generated owner text is
    personalised again. A shared admission lock prevents editing during an in-process turn.
    """
    from . import execution, setup, memory
    from .request_context import RealmContext
    root = Path(root).resolve()
    name = ' '.join(str(body.get('name') or '').split())[:60]
    owner = ' '.join(str(body.get('owner') or '').split())[:60]
    template = str(body.get('template') or '')
    if not name or not owner or not agents or template not in TEMPLATES:
        return {'ok': False, 'error': 'Enter both names and choose at least one agent.'}
    identity = RealmContext.capture(root).realm_id
    try:
        with execution.RUNS_LOCK, util.file_lock(root / 'realm.json'):
            if any(run.context.realm.realm_id == identity for run in execution.ACTIVE_RUNS.values()):
                return {'ok': False, 'error': 'Wait for the current task to finish before changing your team.'}
            cfg = json.loads((root / 'realm.json').read_text(encoding='utf-8-sig'))
            if not cfg.get('setup') or cfg['setup'].get('done'):
                return {'ok': False, 'error': 'Setup is complete. Edit your team from Agents.'}
            live = {p.name: p for p in (root / 'agents').iterdir() if p.is_dir()}
            retired = {p.name: p for p in (root / 'retired').iterdir() if p.is_dir()} if (root / 'retired').exists() else {}
            known = {**retired, **live}
            # Custom indices change when a preceding draft is removed. Preserve saved identities.
            customs = [a for a in agents if a['id'].startswith('custom-')]
            for a, submitted in zip(customs, body.get('extra') or []):
                saved = submitted.get('saved_id')
                if saved:
                    if saved not in known:
                        return {'ok': False, 'error': 'That saved agent is no longer available. Reload setup.'}
                    a['id'] = saved
                else:
                    base, n = a['id'], 2
                    while a['id'] in known:
                        existing = json.loads((known[a['id']] / 'agent.json').read_text(encoding='utf-8-sig'))
                        if all(existing.get(k, '') == a.get(k, '') for k in ('display', 'role', 'leader')):
                            break
                        a['id'], n = f'{base}-{n}', n + 1
            wanted = {a['id'] for a in agents}
            if len(wanted) != len(agents):
                return {'ok': False, 'error': 'Choose each agent only once.'}
            for aid in wanted:
                util.safe_seg(aid, 'agent')
            if any(aid in retired for aid in live.keys() - wanted):
                return {'ok': False, 'error': 'A retired profile already has this ID. Resolve it in Agents first.'}
            previous_owner = (cfg.get('user') or {}).get('name') or 'the owner'
            profile_owners = cfg['setup'].setdefault('profile_owners', {})
            for aid in known:
                profile_owners.setdefault(aid, previous_owner)
            theme = {**TEMPLATES[template]['theme'], 'template': template}
            writes, moves = {}, []
            with tempfile.TemporaryDirectory(prefix='.setup-edit-', dir=root) as temporary:
                stage = Path(temporary)
                for a in agents:
                    if a['id'] not in known:
                        setup.write_agent(stage, a, theme)
                try:
                    def write(path, data):
                        writes.setdefault(path, path.read_bytes() if path.exists() else None)
                        util.write_text_atomic(path, data.decode('utf-8'))

                    def put_json(path, value):
                        write(path, json.dumps(value, ensure_ascii=False, indent=2).encode('utf-8'))

                    def move(src, dst):
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        src.rename(dst)
                        moves.append((src, dst))

                    for a in agents:
                        aid = a['id']
                        dest = root / 'agents' / aid
                        if aid not in live:
                            move(known.get(aid, stage / 'agents' / aid), dest)
                        agent_cfg = json.loads((dest / 'agent.json').read_text(encoding='utf-8-sig'))
                        agent_cfg['coordinator'] = bool(a.get('coordinator'))
                        if agent_cfg.pop('retired', None):
                            agent_cfg['reinstated'] = setupflow._now()
                        put_json(dest / 'agent.json', agent_cfg)
                        old_owner = profile_owners.get(aid, previous_owner)
                        old = next((p for p in starter_profiles.roster(template, old_owner) if p['id'] == aid), None)
                        if old and old_owner != owner:
                            for key, filename in (('mandate', 'mandate.md'), ('voice', 'soul.md'), ('tenets', 'tenets.md')):
                                p = dest / filename
                                if p.exists() and covenant.adapt(p.read_text(encoding='utf-8'), template).strip() == old.get(key, '').strip():
                                    write(p, (a.get(key, '') + '\n').encode('utf-8'))
                        profile_owners[aid] = owner
                    for aid in live.keys() - wanted:
                        path = live[aid] / 'agent.json'
                        agent_cfg = json.loads(path.read_text(encoding='utf-8-sig'))
                        agent_cfg.update(coordinator=False, retired=setupflow._now())
                        put_json(path, agent_cfg)
                        move(live[aid], root / 'retired' / aid)
                    if cfg.get('template') != template:
                        terms = root / 'tenets.md'
                        if terms.exists():
                            write(terms, covenant.adapt(terms.read_text(encoding='utf-8'), template).encode('utf-8'))
                    cfg.update(name=name, template=template)
                    cfg['user'] = {**(cfg.get('user') or {}), 'name': owner}
                    cfg['setup']['step'] = 'capabilities'
                    put_json(root / 'theme.json', theme)
                    put_json(root / 'realm.json', cfg)
                except Exception:
                    # Restore files at their current locations, then undo directory moves.
                    for path, data in reversed(list(writes.items())):
                        actual = path
                        for src, dst in moves:
                            if path.is_relative_to(src):
                                actual = dst / path.relative_to(src)
                        if data is None:
                            actual.unlink(missing_ok=True)
                        else:
                            util.write_text_atomic(actual, data.decode('utf-8'), newline='')
                    for src, dst in reversed(moves):
                        dst.rename(src)
                    raise
        try:
            memory.refresh_system_memory(root, trigger='setup-team-edited')
        except Exception:
            log.exception('Team saved; system memory will refresh on next use')
        return {'ok': True}
    except (OSError, ValueError) as exc:
        log.exception('Could not update setup team')
        return {'ok': False, 'error': f'Could not save your team: {exc}'[:200]}
