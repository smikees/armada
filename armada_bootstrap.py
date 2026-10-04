"""Stable installed entry point: recover the package before importing it.

This file is replaced only by the installer. It uses the standard library and fixed paths
under its own installation. A kernel lock serializes startup and package replacement;
per-process leases prevent replacement while another process is using the package.
"""
from contextlib import contextmanager
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import sys
import time
import uuid

PROTOCOL = 1
JOURNAL = '.armada-update.json'
REQUEST = '.armada-update-request.json'
ERROR = '.armada-update-error.json'
_leases = {}


def _linked(path):
    return path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction())


def _lock(fd, release=False):
    if os.name == 'nt':
        import msvcrt
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK if release else msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_UN if release else fcntl.LOCK_EX | fcntl.LOCK_NB)


@contextmanager
def install_lock(root, timeout=10):
    root = Path(root).resolve()
    path = root / '.armada-update.lock'
    if _linked(path): raise OSError('Linked installation lock refused')
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    locked = False
    deadline = time.monotonic() + timeout
    try:
        while not locked:
            try:
                _lock(fd)
                locked = True
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK): raise
                if time.monotonic() >= deadline: raise OSError('Another ARMADA process owns the update lock') from exc
                time.sleep(.05)
        yield
    finally:
        if locked: _lock(fd, release=True)
        os.close(fd)


def _lease_directory(root):
    path = root / '.armada-processes'
    if _linked(path): raise OSError('Linked process lease directory refused')
    path.mkdir(exist_ok=True)
    return path


def active_others(root):
    """Caller holds install_lock. Stale files are harmless: only kernel ownership counts."""
    root = Path(root).resolve()
    own = _leases.get(root)
    for path in _lease_directory(root).glob('*.lease'):
        if own and path == own[0]: continue
        if _linked(path): raise OSError('Linked process lease refused')
        fd = os.open(path, os.O_RDWR)
        try:
            try: _lock(fd)
            except OSError as exc:
                if exc.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK): return True
                raise
            _lock(fd, release=True)
        finally: os.close(fd)
        path.unlink(missing_ok=True)
    return False


def acquire_lease(root):
    """Caller holds install_lock; the lease stays open through the entire application lifetime."""
    root = Path(root).resolve()
    path = _lease_directory(root) / f'{os.getpid()}-{uuid.uuid4().hex}.lease'
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
    try: _lock(fd)
    except BaseException:
        os.close(fd)
        raise
    _leases[root] = path, fd


def release_lease(root):
    own = _leases.pop(Path(root).resolve(), None)
    if own:
        path, fd = own
        with install_lock(root):
            os.close(fd)
            path.unlink(missing_ok=True)


def atomic_json(path, data):
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temp.open('x', encoding='utf-8') as stream:
            json.dump(data, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        replace(temp, path)
    finally: temp.unlink(missing_ok=True)


def replace(source, target):
    for attempt in range(12):
        try:
            os.replace(source, target)
            if os.name != 'nt':
                fd = os.open(str(Path(target).parent), os.O_RDONLY)
                try: os.fsync(fd)
                finally: os.close(fd)
            return
        except PermissionError:
            if attempt == 11: raise
            time.sleep(.05)


def inventory(folder):
    if _linked(folder) or not folder.is_dir(): raise OSError('Incomplete or linked package')
    result = {}
    for path in folder.rglob('*'):
        if _linked(path): raise OSError('Linked package member refused')
        if '__pycache__' in path.parts or path.name == '.staged.json': continue
        if path.is_file():
            result[path.relative_to(folder).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    if '__init__.py' not in result: raise OSError('Package has no version entry point')
    return result


def version(folder):
    try:
        found = re.search(r'__version__\s*=\s*"([0-9.]+)"', (folder/'__init__.py').read_text(encoding='utf-8'))
        return found[1] if found else ''
    except OSError: return ''


def _matches(folder, files):
    try: return inventory(folder) == files
    except OSError: return False


def _finish(root):
    (root/'armada'/'.staged.json').unlink(missing_ok=True)
    (root/JOURNAL).unlink(missing_ok=True)
    (root/REQUEST).unlink(missing_ok=True)
    (root/ERROR).unlink(missing_ok=True)


def recover_locked(root):
    """Resolve a durable journal using complete-file inventories, never just a directory name."""
    root = Path(root)
    journal = root/JOURNAL
    if not journal.exists(): return ''
    if active_others(root): raise OSError('Recovery is waiting for another ARMADA process to exit')
    state = json.loads(journal.read_text(encoding='utf-8'))
    if (not isinstance(state, dict) or state.get('format') != PROTOCOL
            or not isinstance(state.get('new_files'),dict) or not isinstance(state.get('old_files'),dict)):
        raise OSError('Invalid update journal; preserved for recovery')
    live, staged, previous = [root/name for name in ('armada','armada.staged','armada.previous')]
    if _matches(live,state['new_files']):
        _finish(root)
        return state['version']
    if _matches(live,state['old_files']):
        # Interrupted before the live rename, or ordinary failure rolled it back.
        journal.unlink()
        return state['old_version']
    if live.exists(): raise OSError('Live package differs from both journal snapshots; preserved for recovery')
    if _matches(staged,state['new_files']):
        replace(staged,live)
        _finish(root)
        return state['version']
    if _matches(previous,state['old_files']):
        replace(previous,live)
        journal.unlink()
        (root/REQUEST).unlink(missing_ok=True)
        return state['old_version']
    raise OSError('No complete package matches the update journal; preserved for recovery')


def apply_locked(root):
    root = Path(root)
    if active_others(root): raise OSError('Another ARMADA process is still using this installation')
    recover_locked(root)
    live, staged, previous = [root/name for name in ('armada','armada.staged','armada.previous')]
    if not staged.exists(): return ''
    info = json.loads((staged/'.staged.json').read_text(encoding='utf-8'))
    new_files = inventory(staged)
    if info.get('files') != new_files or info.get('version') != version(staged):
        raise OSError('The staged package changed after verification')
    if tuple(map(int, version(staged).split('.'))) <= tuple(map(int, version(live).split('.'))):
        raise OSError('The staged version must be newer than the installed version')
    state = {'format':PROTOCOL, 'phase':'prepared', 'version':version(staged),
             'old_version':version(live), 'new_files':new_files, 'old_files':inventory(live)}
    if _linked(previous): raise OSError('Linked previous package refused')
    atomic_json(root/JOURNAL,state)
    if previous.exists(): shutil.rmtree(previous)
    replace(live,previous)
    try:
        state['phase']='old_moved'
        atomic_json(root/JOURNAL,state)
        replace(staged,live)
    except BaseException:
        replace(previous,live)
        (root/JOURNAL).unlink(missing_ok=True)
        raise
    state['phase']='new_live'
    atomic_json(root/JOURNAL,state)
    _finish(root)
    return state['version']


def apply(root):
    with install_lock(root): return apply_locked(root)


def main():
    root = Path(__file__).resolve().parent
    sys.modules['armada_bootstrap'] = sys.modules[__name__]
    installed = (root/'installed.json').is_file() and not (root/'.git').exists()
    if installed:
        deadline = time.monotonic()+120
        while True:
            with install_lock(root):
                others = active_others(root)
                pending = (root/REQUEST).exists() or (root/JOURNAL).exists()
                if not (others and pending):
                    recover_locked(root)
                    if not others and (root/'armada.staged').exists() and not (root/ERROR).exists():
                        try: apply_locked(root)
                        except (OSError, ValueError) as exc:
                            # A rejected stage must not hide an intact current installation.
                            recover_locked(root)
                            if not version(root/'armada'): raise
                            atomic_json(root/ERROR, {'error':str(exc)[:500]})
                            (root/REQUEST).unlink(missing_ok=True)
                    acquire_lease(root)
                    break
            if time.monotonic() >= deadline:
                raise OSError('Update is waiting for ARMADA to close. Finish current work, close all ARMADA windows, then reopen.')
            time.sleep(.1)
    try:
        sys.path.insert(0,str(root))
        runpy.run_module('armada',run_name='__main__')
    finally:
        if installed: release_lease(root)


if __name__ == '__main__': main()
