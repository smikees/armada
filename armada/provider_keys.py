"""Owner-entered provider secrets outside realms, with no read/echo HTTP endpoint."""
import os
import base64
from . import util


def _crypt(value, *, decrypt=False):
    """Windows DPAPI keeps literal keys out of machine files as well as realm exports."""
    if os.name != 'nt':
        return value
    import ctypes as C
    from ctypes import wintypes as W
    class Blob(C.Structure):
        _fields_ = [('size', W.DWORD), ('data', C.POINTER(C.c_ubyte))]
    buffer = C.create_string_buffer(value)
    source = Blob(len(value), C.cast(buffer, C.POINTER(C.c_ubyte)))
    target = Blob()
    crypt = C.WinDLL('crypt32', use_last_error=True)
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [C.POINTER(Blob), C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p, W.DWORD, C.POINTER(Blob)]
    function.restype = W.BOOL
    if not function(C.byref(source), None, None, None, None, 1, C.byref(target)):
        raise OSError('The Windows credential store could not be accessed. The API lane is closed.')
    try:
        return C.string_at(target.data, target.size)
    finally:
        kernel = C.WinDLL('kernel32', use_last_error=True)
        kernel.LocalFree.argtypes = [C.c_void_p]
        kernel.LocalFree(C.cast(target.data, C.c_void_p))


def _path():
    return util.data_dir() / 'provider-secrets.json'


def _read():
    return util.read_json_state(_path(), default=dict)


def configured(provider):
    return bool(_read().get(provider))


def key(provider):
    value = _read().get(provider, '')
    if not isinstance(value, str):
        raise ValueError('Invalid provider key store.')
    if value.startswith('dpapi:'):
        return _crypt(base64.b64decode(value[6:]), decrypt=True).decode('utf-8')
    return value


def save(provider, value):
    if provider != 'claude':
        raise ValueError('Only Claude API fallback is enabled. Other providers remain on their existing authentication.')
    if not isinstance(value, str) or value and (not value.startswith('sk-ant-') or any(c.isspace() for c in value)):
        raise ValueError('Enter a valid Anthropic API key, or clear it.')
    if value:
        from . import worker
        worker.require()
    path = _path()
    if any((parent/'realm.json').is_file() for parent in path.resolve().parents):
        raise ValueError('Provider secrets must be stored outside every realm folder. Change the app data location first.')
    with util.file_lock(path):
        state = _read()
        if value:
            from .run_policy import initialise_ledger
            initialise_ledger(provider)
            state[provider] = 'dpapi:'+base64.b64encode(_crypt(value.encode('utf-8'))).decode('ascii') if os.name == 'nt' else value
        else:
            state.pop(provider, None)
        util.write_json_atomic(path, state)
        os.chmod(path, 0o600)
    from .run_policy import audit
    audit('set-provider-key', provider=provider, configured=bool(value))
