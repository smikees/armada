"""Relocate an unfinished realm, preserving its files and machine registration."""
import hashlib
import json
import logging
from pathlib import Path
import shutil
import uuid

from . import appconfig, approot, activerealm, setupflow, util
from . import realm_registry

log = logging.getLogger(__name__)


def _manifest(root):
    result = {}
    for path in root.rglob('*'):
        if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
            raise ValueError('This realm contains linked folders. Move it outside setup instead.')
        if path.is_file():
            with path.open('rb') as stream:
                result[str(path.relative_to(root))] = hashlib.file_digest(stream, 'sha256').hexdigest()
    return result


def relocate(root, target: str) -> dict:
    """The caller holds run admission and selection locks until it selects the new path.

    Copy/verify first (also works across drives), then rename the original as a rollback
    copy. Publish the destination only after verification. Never replace a nonempty target.
    """
    from . import scheduler
    source = Path(root).resolve()
    target = str(target or '').strip()
    if not target or not Path(target).is_absolute():
        return {'ok': False, 'error': 'Choose an absolute folder path.'}
    destination = Path(target).resolve()
    if not setupflow.needs_setup(source):
        return {'ok': False, 'error': 'Setup is complete. Folder moves are available only during setup.'}
    if source == destination:
        result = setupflow.set_step(source, 'naming')
        return {**result, 'path': str(source)}
    if source in destination.parents or destination in source.parents:
        return {'ok': False, 'error': 'Choose a separate folder, outside the current realm.'}
    if not destination.parent.is_dir():
        return {'ok': False, 'error': 'The destination’s parent folder must already exist.'}
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        return {'ok': False, 'error': 'Choose a new or empty folder. Existing files will not be overwritten.'}
    if scheduler.lock_holder(source):
        return {'ok': False, 'error': 'The scheduler is using this realm. Stop it before moving the folder.'}
    # Keep all previously registered realms inside the machine's existing containment boundary.
    new_app_root = Path(approot.root()).resolve() if approot.root() else destination.parent
    if destination != new_app_root and new_app_root not in destination.parents:
        new_app_root = destination.parent
    token = uuid.uuid4().hex
    stage = destination.parent / ('.armada-moving-' + token)
    backup = source.parent / ('.armada-moved-' + token)
    old_config = appconfig.load()
    moved = published = False
    target_was_empty = destination.exists()
    try:
        with util.file_lock(source.parent / ('.setup-move-' + source.name), validate_state=False), realm_registry.edit() as records:
            if any(Path(r['path']).resolve() != source and activerealm.is_realm(r['path'])
                   and Path(r['path']).resolve() != new_app_root and new_app_root not in Path(r['path']).resolve().parents
                   for r in records):
                raise ValueError('Other realms use Armada’s current folder. Choose a destination inside it so they remain accessible.')
            before = _manifest(source)
            shutil.copytree(source, stage)
            if _manifest(stage) != before or _manifest(source) != before:
                raise ValueError('Files changed during the move. Wait for the task to finish and try again.')
            if target_was_empty:
                destination.rmdir()  # fails safely if another process wrote into it
            source.rename(backup)
            moved = True
            stage.rename(destination)
            published = True
            cfg_path = destination / 'realm.json'
            with util.file_lock(cfg_path):
                cfg = json.loads(cfg_path.read_text(encoding='utf-8-sig'))
                workspace = str(cfg.get('workspace') or '')
                if workspace and (Path(workspace).resolve() == source or source in Path(workspace).resolve().parents):
                    cfg['workspace'] = str(destination / Path(workspace).resolve().relative_to(source))
                cfg['setup']['step'] = 'naming'
                util.write_json_atomic(cfg_path, cfg)
            records[:] = [{**r, 'path': str(destination)} if Path(r.get('path', '')).resolve() == source else r for r in records]
            if not any(r.get('path') == str(destination) for r in records):
                records.append({'path': str(destination), 'name': cfg.get('name', destination.name)})
            appconfig.save({approot.KEY: str(new_app_root), activerealm.KEY: str(destination)})
    except (OSError, ValueError) as exc:
        log.exception('Setup folder move failed')
        if published:
            shutil.rmtree(destination)
        if moved:
            backup.rename(source)
            appconfig.save({approot.KEY: old_config.get(approot.KEY, ''), activerealm.KEY: old_config.get(activerealm.KEY, '')})
        if stage.exists():
            shutil.rmtree(stage)
        if target_was_empty and not destination.exists():
            destination.mkdir()
        return {'ok': False, 'error': 'Could not move the realm: ' + str(exc)[:160]}
    # The verified destination is now canonical; a cleanup failure leaves a recoverable backup.
    try:
        shutil.rmtree(backup)
    except OSError:
        log.warning('Realm moved; old backup remains at %s', backup)
    try:
        from . import memory
        memory.refresh_system_memory(destination, trigger='setup-folder-moved')
    except Exception:
        log.exception('Realm moved; system memory will refresh on next use')
    return {'ok': True, 'path': str(destination)}
