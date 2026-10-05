"""Prepare a monitored desktop handover before the old process releases its server."""
from pathlib import Path
import json
import os
import shutil
import sys
import time
import uuid

from . import desktop_launch, util


def cleanup(keep=5, days=30):
    """Bound retained helper folders, excluding the currently active monitor."""
    base = util.data_dir() / 'restart'
    active = state()
    folders = sorted((p for p in base.glob('*') if p.is_dir() and not p.is_symlink()
                      and not (hasattr(p, 'is_junction') and p.is_junction())),
                     key=lambda p:p.stat().st_mtime, reverse=True)
    for index, path in enumerate(folders):
        if path.name == active.get('nonce') and util.pid_alive(active.get('monitor_pid', 0)):
            continue
        if index >= keep or time.time()-path.stat().st_mtime > days*86400:
            shutil.rmtree(path, ignore_errors=True)


def lease_blockers(root, permitted):
    """Report kernel-held installation leases, excluding this app and its scheduler."""
    import armada_bootstrap as bootstrap
    blockers = []
    for path in (Path(root) / '.armada-processes').glob('*.lease'):
        if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
            raise OSError('Linked process lease refused')
        try:
            pid = int(path.name.split('-', 1)[0])
        except ValueError:
            raise OSError('Unrecognized installation lease') from None
        fd = os.open(path, os.O_RDWR)
        try:
            try:
                bootstrap._lock(fd)
            except OSError:
                if pid not in permitted:
                    blockers.append({'kind': 'instance', 'pid': pid,
                                     'label': f'Close the older ARMADA instance (PID {pid})'})
            else:
                bootstrap._lock(fd, release=True)
        finally:
            os.close(fd)
    return blockers


def state():
    try:
        data = json.loads((util.data_dir() / 'restart-status.json').read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def begin(root, realm, port, version, scheduler_required):
    """Start a lease-free supervisor and wait for its acknowledgement before shutdown."""
    cleanup()
    from . import app, instance
    app.save_window_state()
    folder = util.data_dir() / 'restart' / uuid.uuid4().hex
    folder.mkdir(parents=True)
    worker = folder / 'restart_worker.py'
    shutil.copy2(Path(__file__).with_name('restart_worker.py'), worker)
    shutil.copy2(Path(desktop_launch.__file__), folder / 'desktop_launch.py')
    plan = {'root': str(Path(root).resolve()), 'realm': str(realm or ''), 'port': port,
            'version': version, 'owner_pid': os.getpid(), 'scheduler_required': scheduler_required,
            'status': str(util.data_dir() / 'restart-status.json'),
            'auth': str(util.data_dir() / 'local-auth' / f'{port}.json'),
            'instance': str(instance._path()),
            'executable': sys.executable, 'log': str(folder / 'startup.log'),
            'nonce': folder.name, 'started': time.time()}
    plan_path = folder / 'plan.json'
    util.write_json_atomic(plan_path, plan)
    util.write_json_atomic(Path(plan['status']), {**plan, 'phase': 'starting_monitor'})
    argv = [sys.executable, str(worker), str(plan_path)]
    if os.name == 'nt':
        desktop_launch.spawn(argv, root)
    else:
        import subprocess
        subprocess.Popen(argv, cwd=root, start_new_session=True, close_fds=True)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        current = state()
        if current.get('nonce') == plan['nonce'] and current.get('phase') == 'waiting_exit':
            return plan
        if current.get('nonce') == plan['nonce'] and current.get('phase') == 'error':
            raise OSError(current.get('message', 'The restart monitor failed to start.'))
        time.sleep(.05)
    raise OSError('The restart monitor did not start. ARMADA has stayed open; try again.')
