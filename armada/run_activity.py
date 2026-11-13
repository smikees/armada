"""Shared liveness evidence for presentation and update draining."""
from . import util


def locked(path):
    """Probe stable kernel ownership without trusting a reusable process ID."""
    try:
        with util.file_lock(path, timeout=0, validate_state=False):
            return False
    except util.FileLockTimeout:
        return True


def marker_live(path, item):
    if not isinstance(item, dict):
        raise ValueError('Invalid run activity record')
    if item.get('status') == 'finished':
        return False
    if item.get('owned') is True:
        return locked(path.with_suffix('.owner'))
    if item.get('invocation_owned') is True:
        return locked(path.parent.parent / '.invocations' / path.name)
    # Older installed processes have no lifetime lease. Keep their live PID
    # conservative until they exit; do not kill work just because it is old.
    return bool(item.get('owner_pid') and util.pid_alive(item['owner_pid']))
