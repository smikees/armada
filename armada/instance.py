"""One desktop/server owner per OS account, independent of realm and install path."""
from contextlib import contextmanager
import json
import logging
import os
import threading
import uuid
import urllib.request
from pathlib import Path

from . import util

_owner = None


def _account_directory():
    """Resolve the Windows token's profile, independent of environment/profile overrides."""
    if os.name != 'nt': return Path.home() / '.armada'
    import ctypes as c
    from ctypes import wintypes as w
    kernel = c.WinDLL('kernel32', use_last_error=True)
    advapi = c.WinDLL('advapi32', use_last_error=True)
    userenv = c.WinDLL('userenv', use_last_error=True)
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.CloseHandle.argtypes = [w.HANDLE]
    advapi.OpenProcessToken.argtypes = [w.HANDLE,w.DWORD,c.POINTER(w.HANDLE)]
    userenv.GetUserProfileDirectoryW.argtypes = [w.HANDLE,w.LPWSTR,c.POINTER(w.DWORD)]
    token = w.HANDLE()
    if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 8, c.byref(token)):
        raise c.WinError(c.get_last_error())
    try:
        size = w.DWORD(32768)
        buffer = c.create_unicode_buffer(size.value)
        if not userenv.GetUserProfileDirectoryW(token, buffer, c.byref(size)):
            raise c.WinError(c.get_last_error())
        return Path(buffer.value) / '.armada'
    finally:
        kernel.CloseHandle(token)


def _path():
    return _account_directory() / 'desktop-instance.json'


def current():
    try:
        data = json.loads(_path().read_text(encoding='utf-8'))
        return data if isinstance(data, dict) and util.pid_alive(data.get('pid', 0)) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _legacy():
    """Recognize authenticated older servers which predate the account-wide lock."""
    from . import local_auth
    for path in (util.data_dir() / 'local-auth').glob('*.json'):
        try:
            port = int(path.stem)
            data = json.loads(path.read_text(encoding='utf-8'))
            pid = int(data.get('pid', 0))
            if pid == os.getpid() or not util.pid_alive(pid):
                continue
            request = urllib.request.Request(f'http://127.0.0.1:{port}/api/instance',
                                             headers=local_auth.headers(port))
            with urllib.request.urlopen(request, timeout=.3) as response:
                if json.load(response).get('app') == 'ARMADA':
                    return {'pid': pid, 'port': port, 'legacy': True}
        except (OSError, ValueError, TypeError, AttributeError):
            continue
    return {}


def _focus_pid(pid):
    if os.name != 'nt':
        return
    import ctypes as c
    from ctypes import wintypes as w
    user = c.WinDLL('user32', use_last_error=True)
    user.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
    user.GetWindowTextW.argtypes = [w.HWND, w.LPWSTR, c.c_int]
    user.ShowWindow.argtypes = [w.HWND, c.c_int]
    user.SetForegroundWindow.argtypes = [w.HWND]
    callback_type = c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    user.EnumWindows.argtypes = [callback_type, w.LPARAM]
    @callback_type
    def visit(hwnd, _):
        owner = w.DWORD()
        user.GetWindowThreadProcessId(hwnd, c.byref(owner))
        title = c.create_unicode_buffer(256)
        user.GetWindowTextW(hwnd, title, 256)
        if owner.value == pid and title.value.startswith('ARMADA'):
            user.ShowWindow(hwnd, 9)
            user.SetForegroundWindow(hwnd)
            return False
        return True
    user.EnumWindows(visit, 0)


def activate(info):
    if info.get('nonce'):
        util.write_json_atomic(_path().with_name('desktop-activate.json'),
                               {'nonce': info['nonce'], 'request': uuid.uuid4().hex})
    try:
        _focus_pid(info.get('pid', 0))
    except OSError:
        pass  # A foreground restriction must not allow a duplicate instance.


@contextmanager
def claim(role, port):
    """Kernel-held lifetime lock: simultaneous launches and crashes cannot steal ownership."""
    global _owner
    if _owner is not None:
        yield True
        return
    gate = util.file_lock(_path(), timeout=.3, validate_state=False)
    try:
        gate.__enter__()
    except util.FileLockTimeout:
        activate(current())
        yield False
        return
    try:
        legacy = _legacy()
        if legacy:
            activate(legacy)
            yield False
            return
        _owner = {'pid': os.getpid(), 'port': port, 'role': role, 'nonce': uuid.uuid4().hex,
                  'data_dir':str(util.data_dir())}
        util.write_json_atomic(_path(), _owner)
        yield True
    finally:
        if _owner is not None:
            _path().unlink(missing_ok=True)
            _owner = None
        gate.__exit__(None, None, None)


def publish_port(port):
    if _owner is not None:
        _owner['port'] = port
        util.write_json_atomic(_path(), _owner)


def desktop_ready():
    if _owner is not None:
        _owner['desktop_ready'] = True
        util.write_json_atomic(_path(), _owner)


def watch_activation(callback):
    """Bring a tray-hidden window back when a second launch requests activation."""
    stop = threading.Event()
    nonce = (_owner or {}).get('nonce')
    def watch():
        seen = None
        while not stop.wait(.25):
            try:
                data = json.loads(_path().with_name('desktop-activate.json').read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            if not isinstance(data, dict):
                continue
            try:
                if data.get('nonce') == nonce and data.get('request') != seen:
                    seen = data.get('request')
                    callback()
            except Exception:
                logging.getLogger(__name__).debug('Could not activate the desktop window', exc_info=True)
    threading.Thread(target=watch, daemon=True).start()
    return stop
