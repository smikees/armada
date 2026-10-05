"""Standalone update supervisor, copied outside the package before replacement.

Only standard-library code runs here; the supervisor holds no installation lease.
It verifies the successor's version, painted desktop and required scheduler.
"""
import ctypes
import json
import logging
import os
from pathlib import Path
import runpy
import sys
import time
import urllib.request

log = logging.getLogger('armada.restart')


def alive(pid):
    if os.name == 'nt':
        from ctypes import wintypes
        k = ctypes.WinDLL('kernel32', use_last_error=True)
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.OpenProcess.restype = wintypes.HANDLE
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        h = k.OpenProcess(0x1000, False, int(pid))
        if not h:
            return False
        try:
            code = wintypes.DWORD()
            return bool(k.GetExitCodeProcess(h, ctypes.byref(code)) and code.value == 259)
        finally:
            k.CloseHandle(h)
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False


def record(plan, phase, message, **extra):
    path = Path(plan['status'])
    data = {**plan, 'monitor_pid': os.getpid(), 'phase': phase, 'message': message, **extra}
    temp = path.with_name(path.name + '.' + plan['nonce'] + '.tmp')
    temp.write_text(json.dumps(data), encoding='utf-8')
    deadline = time.monotonic() + 3
    while True:
        try:
            temp.replace(path)
            break
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(.05)  # A concurrent status read or antivirus scan can briefly hold it open.


def reading(plan, route):
    auth = json.loads(Path(plan['auth']).read_text(encoding='utf-8'))
    request = urllib.request.Request(f"http://127.0.0.1:{plan['port']}/{route}",
                                    headers={'Authorization': 'Bearer ' + auth['token']})
    with urllib.request.urlopen(request, timeout=2) as response:
        return json.load(response)


def successor_endpoint(plan, owner=None):
    """Follow a live successor when it had to move away from a newly occupied port."""
    owner = owner or json.loads(Path(plan['instance']).read_text(encoding='utf-8'))
    if owner.get('pid') == plan['owner_pid'] or not alive(owner.get('pid', 0)):
        raise OSError('The replacement desktop has not acquired instance ownership.')
    port = owner.get('port')
    if port is None:
        return plan  # Older ownership records/test runtimes omit the endpoint.
    if type(port) is not int or not 0 < port < 65536:
        raise ValueError('The replacement desktop recorded an invalid server port.')
    auth = Path(plan['auth'])
    if owner.get('data_dir'):
        auth = Path(owner['data_dir'])/'local-auth'/f'{port}.json'
    elif port != plan.get('port'):
        auth = auth.with_name(str(port)+'.json')
    return {**plan, 'port':port, 'auth':str(auth)}


def readiness_error(plan):
    """Reject stale servers, error pages and a desktop whose scheduler never came back."""
    owner = json.loads(Path(plan['instance']).read_text(encoding='utf-8'))
    if owner.get('pid') == plan['owner_pid'] or not alive(owner.get('pid', 0)):
        return 'The replacement desktop has not acquired instance ownership.'
    endpoint = successor_endpoint(plan, owner)
    data = reading(endpoint, 'api/instance')
    if data.get('nonce') and data['nonce'] != owner.get('nonce'):
        return 'The readiness response belongs to another instance.'
    if data.get('version') != plan['version']:
        return f"Expected version {plan['version']}; the server reports {data.get('version', 'unknown')}."
    if not data.get('desktop_ready'):
        return 'The replacement desktop has not loaded its app page.'
    if plan['scheduler_required'] and not reading(endpoint, 'api/scheduler-status').get('running'):
        return 'The required scheduler has not started.'
    return ''


def verify(plan):
    return not readiness_error(plan)


def ready_if_reachable(plan):
    try:
        return verify(plan)
    except (OSError, ValueError, KeyError, TypeError):
        return False  # Missing owner/auth files are normal while startup is incomplete.


def launch_successor(plan, plan_path):
    argv = [plan['executable'], str(Path(__file__).resolve()), '--launch', str(plan_path)]
    if os.name == 'nt':
        # The embedded runtime's ._pth isolates sys.path, including script folders.
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from desktop_launch import spawn
        spawn(argv, plan['root'])
    else:
        import subprocess
        subprocess.Popen(argv, cwd=plan['root'], start_new_session=True, close_fds=True)


def recover_failure(plan, plan_path, reason, timeout=30):
    """Rollback only an unacknowledged package after all of its leases have closed."""
    root = Path(plan['root'])
    if not (root/'.armada-update-health.json').exists(): return False
    record(plan, 'recovering', 'Startup failed; restoring the previous verified version.', error=reason)
    # Ask only this successor to exit. Never kill a desktop or a running job.
    try:
        endpoint = successor_endpoint(plan)
        auth = json.loads(Path(endpoint['auth']).read_text(encoding='utf-8'))
        request = urllib.request.Request(f"http://127.0.0.1:{endpoint['port']}/api/startup-abort",
            data=json.dumps({'version':plan['version']}).encode(),
            headers={'Authorization':'Bearer '+auth['token'], 'Content-Type':'application/json'})
        with urllib.request.urlopen(request, timeout=2): pass
    except (OSError, ValueError):
        pass  # It may have already crashed before opening its server.
    api = runpy.run_path(str(root/'armada_bootstrap.py'))
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        if not (root/'.armada-update-health.json').exists(): return False
        with api['install_lock'](root):
            if not api['active_others'](root):
                restored = api['rollback_locked'](root, reason)
                break
        time.sleep(.2)
    else:
        raise OSError('Failed startup is still using the installation; rollback postponed. '+reason)
    if not restored: return False
    recovered = {**plan, 'version':restored, 'owner_pid':0}
    Path(plan_path).write_text(json.dumps(recovered), encoding='utf-8')
    launch_successor(recovered, plan_path)
    deadline = time.monotonic()+timeout
    while time.monotonic() < deadline:
        try:
            if not readiness_error(recovered):
                record(recovered, 'rolled_back', 'The previous version was restored after startup failed.', error=reason)
                return True
        except (OSError, ValueError, KeyError): pass
        time.sleep(.5)
    raise OSError('Previous code was restored, but its desktop did not become ready. '+reason)


def supervise(plan, plan_path, timeout=150):
    record(plan, 'waiting_exit', 'Restart monitor ready; waiting for the old app to close.')
    deadline = time.monotonic() + timeout
    while alive(plan['owner_pid']):
        try:
            state = json.loads(Path(plan['status']).read_text(encoding='utf-8'))
            if state.get('nonce') != plan['nonce'] or state.get('phase') == 'error':
                return
        except FileNotFoundError:
            return  # The owner postponed the handover before shutdown.
        if time.monotonic() >= deadline:
            raise OSError('The old ARMADA process did not close. Finish current work and quit from the tray.')
        time.sleep(.1)
    record(plan, 'launching', 'Starting the updated ARMADA desktop.')
    launch_successor(plan, plan_path)
    last_error = 'The desktop has not become ready.'
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            state = json.loads(Path(plan['status']).read_text(encoding='utf-8'))
            if state.get('phase') == 'error':
                raise RuntimeError(state.get('message', 'Successor startup failed'))
            failure = Path(plan['root']) / '.armada-update-error.json'
            if failure.exists():
                raise RuntimeError('Update was not applied: ' + str(json.loads(failure.read_text())['error']))
            last_error = readiness_error(plan)
            if not last_error:
                record(plan, 'complete', 'Update verified: desktop and scheduled jobs are ready.')
                return
        except (OSError, ValueError, KeyError) as exc:
            last_error = str(exc)
        time.sleep(.5)
    raise OSError('ARMADA did not become ready after restart: ' + last_error)


def main():
    launch = sys.argv[1] == '--launch'
    plan_path = Path(sys.argv[2] if launch else sys.argv[1])
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    with Path(plan['log']).open('a', encoding='utf-8') as stream:
        sys.stdout = sys.stderr = stream
        logging.basicConfig(stream=stream, level=logging.INFO)
        try:
            if launch:
                entry = str(Path(plan['root']) / 'armada_bootstrap.py')
                sys.argv = [entry, 'app', plan['realm'], '--port', str(plan['port'])]
                runpy.run_path(entry, run_name='__main__')
            else:
                supervise(plan, plan_path)
        except Exception as exc:
            log.exception('Desktop restart failed')
            if not launch:
                try:
                    if ready_if_reachable(plan):
                        record(plan, 'complete', 'Update verified after delayed local startup.')
                        return
                    if recover_failure(plan, plan_path, str(exc)):
                        return
                    if ready_if_reachable(plan):
                        record(plan, 'complete', 'Update verified after delayed local startup.')
                        return
                except Exception as recovery:
                    log.exception('Startup rollback failed; preserving both operational errors')
                    exc = OSError(f'{exc}; recovery: {recovery}')
            try:
                record(plan, 'error', str(exc), startup_log=plan['log'])
            except OSError:
                log.exception('Could not persist restart failure; the startup log retains it')
            if not launch:
                if os.name == 'nt':
                    ctypes.windll.user32.MessageBoxW(None,
                        f"{exc}\n\nDetails: {plan['log']}\nOpen ARMADA again from its shortcut.",
                        'ARMADA restart needs attention', 0x10)


if __name__ == '__main__':
    main()
