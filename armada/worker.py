"""Owner-controlled Windows worker boundary for every provider and local tool child.

Only owner code can decrypt the launch password, change the worker policy, or read
the provider key held by the API gateway. The worker receives its own Windows identity,
profile, environment and desktop. Missing/broken setup never downgrades to the owner.
"""
from __future__ import annotations

import base64
import contextvars
import json
import logging
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager
from . import util

_lock = threading.RLock()
_desktops = {}
_temporary = {}
_owner_children = []
_owner_calls = 0
_pending = False
_checking=contextvars.ContextVar('armada_worker_checking',default=False)
log=logging.getLogger(__name__)


def _path():
    return util.data_dir() / 'worker-account.json'


def state():
    return util.read_json_state(_path(), default=dict)


def enabled():
    if state():
        return True
    # Losing worker configuration must never re-enable owner-identity tools while
    # an API credential still exists on this machine.
    from . import provider_keys
    return provider_keys.configured('claude')


def require():
    value = state()
    provisioned=all(value.get(k) for k in ('sid','home','python','python_root','bootstrap','launches','station'))
    if os.name != 'nt' or not value.get('ready') and not (_checking.get() and provisioned):
        raise OSError('Set up the isolated Windows worker in App Settings before using API fallback.')
    checked={**value,'app_root':str(Path(__file__).resolve().parent.parent), 'data_root':str(util.data_dir()),
             'python_root':sys.base_prefix,'python_env_root':sys.prefix}
    if deletion_guard_paths(checked):
        raise OSError('Worker activation requires owner-protected application and settings folders. Use the normal per-user installation; a worker-writable development checkout cannot protect owner credentials.')
    return value


def password(value):
    from .provider_keys import _crypt
    return _crypt(base64.b64decode(value['password']), decrypt=True).decode('utf-8')


def home():
    value = state()
    return Path(value['home']) if value.get('ready') else Path.home()


def _within(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def _acl(path, sid, rights):
    """Grant a registered runtime through its held handle, never an untrusted path."""
    with _lock:
        folder=_temporary.get(os.path.normcase(str(Path(path).absolute())))
        if folder is None or rights != 'M':
            raise OSError('Refusing a grant outside a held worker runtime folder.')
        folder.grant(sid)


def deletion_guard_paths(value):
    """Read-only access check: list only trusted ancestors this worker can replace.

    Open-existing directory handles request delete/control rights, then immediately
    close. No file, directory, ACL or token is modified by this check.
    """
    import ctypes as C
    from ctypes import wintypes as W
    adv=C.WinDLL('advapi32',use_last_error=True)
    kernel=C.WinDLL('kernel32',use_last_error=True)
    adv.LogonUserW.argtypes=[W.LPCWSTR,W.LPCWSTR,W.LPCWSTR,W.DWORD,W.DWORD,C.POINTER(W.HANDLE)]
    adv.ImpersonateLoggedOnUser.argtypes=[W.HANDLE]
    kernel.CreateFileW.argtypes, kernel.CreateFileW.restype=[W.LPCWSTR,W.DWORD,W.DWORD,C.c_void_p,W.DWORD,W.DWORD,W.HANDLE],W.HANDLE
    kernel.CloseHandle.argtypes=[W.HANDLE]
    candidates=set()
    for item in [value['app_root'],value['root'],value['python_root'],value.get('python_env_root',value['python_root']),value.get('data_root',str(util.data_dir()))]:
        for parent in Path(item).resolve().parents:
            if parent.parent != parent:
                candidates.add(str(parent))
    token=W.HANDLE()
    if not adv.LogonUserW(value['username'],'.',password(value),2,0,C.byref(token)):
        raise OSError('Could not inspect worker permissions.')
    result=[]
    try:
        if not adv.ImpersonateLoggedOnUser(token):
            raise OSError('Could not inspect worker directory access.')
        try:
            for path in sorted(candidates):
                for rights in (0x10000,0x40,0x40000,0x80000):
                    handle=kernel.CreateFileW(path,rights,7,None,3,0x02000000,None)
                    if handle != C.c_void_p(-1).value:
                        kernel.CloseHandle(handle)
                        result.append(path)
                        break
        finally:
            adv.RevertToSelf()
    finally:
        kernel.CloseHandle(token)
    return result


def _safe_temporary(path):
    path = Path(path).absolute()
    value = state()
    if not value.get('home'):
        return None
    base=Path(value['home'])/'AppData/Local/Temp'
    try:
        relative=path.relative_to(base)
    except ValueError:
        return None
    if not relative.parts or not relative.parts[0].startswith('armada-'):
        return None
    root = base/relative.parts[0]
    if root.is_symlink() or (hasattr(root, 'is_junction') and root.is_junction()) or root.resolve() != root:
        raise OSError('Refusing redirected worker runtime files.')
    return root


def _access(path, value, *, temporary=False):
    if any(_within(path, p) for p in value['protected_roots']):
        raise OSError('The isolated worker cannot access an owner credential or application-control folder.')
    candidate=_safe_temporary(path)
    if candidate and os.path.normcase(str(candidate)) in _temporary:
        _acl(candidate,value['sid'],'M')
    if any(_within(path, p) for p in value['allowed_roots']) or _within(path, value['home']):
        return str(path)
    raise OSError('This folder is not shared with the isolated worker. Add it in App Settings > Worker folders.')


_ENV = frozenset(('SYSTEMROOT', 'WINDIR', 'COMSPEC', 'SYSTEMDRIVE', 'OS', 'PROCESSOR_ARCHITECTURE',
                  'NUMBER_OF_PROCESSORS', 'PATHEXT', 'LANG', 'LC_ALL', 'TERM', 'COLORTERM',
                  'PYTHONIOENCODING', 'PYTHONUTF8', 'GIT_TERMINAL_PROMPT', 'NO_COLOR'))
_RUN_ENV = frozenset(('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_BASE_URL',
                      'CLAUDE_CODE_SUBPROCESS_ENV_SCRUB', 'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC',
                      'DISABLE_TELEMETRY', 'DISABLE_ERROR_REPORTING', 'NO_PROXY', 'no_proxy',
                      'ARMADA_RAW_DIR', 'CLAUDE_CONFIG_DIR', 'CODEX_HOME', 'ARMADA_DRY_RUN',
                      'ARMADA_DRY_RUN_DIR','ARMADA_INPUT_DIR','ARMADA_INPUT_MANIFEST'))


def environment(value, supplied=None):
    """Allowlist the worker environment. Only explicit invocation credentials cross it."""
    env = {k:v for k,v in os.environ.items() if k.upper() in _ENV}
    profile = Path(value['home'])
    env.update(USERPROFILE=str(profile), HOME=str(profile), HOMEDRIVE=profile.drive,
               HOMEPATH=str(profile)[len(profile.drive):], APPDATA=str(profile/'AppData/Roaming'),
               LOCALAPPDATA=str(profile/'AppData/Local'), TEMP=str(profile/'AppData/Local/Temp'),
               TMP=str(profile/'AppData/Local/Temp'), USERNAME=value['username'],
               PYTHONUTF8='1', PYTHONIOENCODING='utf-8',
               CLAUDE_CODE_USE_POWERSHELL_TOOL='1',
               PATH=os.pathsep.join(value['path']), CODEX_HOME=str(profile/'.codex'),
               CLAUDE_CONFIG_DIR=str(profile/'.claude'))
    # Callers often pass a merge of os.environ and invocation overrides. Never mistake
    # an inherited owner secret/configuration for an explicit run setting.
    for key, item in (supplied or {}).items():
        if key in _RUN_ENV and item != os.environ.get(key):
            if key in ('CLAUDE_CONFIG_DIR', 'CODEX_HOME', 'ARMADA_RAW_DIR'):
                _access(item, value, temporary=True)
            env[key] = item
    return env


def popen(args, **kwargs):
    with _lock:
        return _popen(args,**kwargs)


def _popen(args, **kwargs):
    terminal = kwargs.pop('worker_terminal', False)
    if not enabled():
        process=subprocess.Popen(args, **kwargs)
        _owner_children[:]=[child for child in _owner_children if child.poll() is None]
        if hasattr(process,'poll'):_owner_children.append(process)
        return process
    value = require()
    if not isinstance(args, (list, tuple)) or kwargs.get('shell'):
        raise OSError('An isolated worker launch requires an argument array without a shell.')
    if kwargs.get('executable'):
        raise OSError('Alternate worker executables must be passed in the argument array.')
    args = [os.fspath(item) for item in args]
    folder = _access(kwargs.pop('cwd', None) or value['home'], value, temporary=True)
    # Runtime-only prompt/config files live in host-created temporary folders. No
    # arbitrary owner file is granted merely because it appeared in an argument.
    for index, item in enumerate(args):
        if index and args[index-1] in ('--system-prompt-file', '--mcp-config') and Path(item).exists():
            _access(item, value, temporary=True)
    run = Path(value['launches'])/secrets.token_hex(16)
    run.mkdir()
    spec = run/'request.json'
    env = environment(value, kwargs.pop('env', None))
    spec.write_text(json.dumps({'args':args, 'cwd':folder, 'env':env,
                               'owner_sid':value['owner_sid'], 'sid':value['sid'], 'terminal':terminal,
                               'station':value['station']}), encoding='utf-8')
    from .worker_process import WorkerPopen
    # Handles are always private pipes, including unattended login output. No owner
    # console, desktop, token or arbitrary inheritable handle is passed to the worker.
    kwargs.setdefault('stdin', subprocess.DEVNULL)
    kwargs.setdefault('stdout', subprocess.DEVNULL)
    kwargs.setdefault('stderr', subprocess.DEVNULL)
    try:
        return WorkerPopen(args, identity=value, spec=spec, cwd=value['home'], **kwargs)
    except BaseException:
        spec.unlink(missing_ok=True)
        run.rmdir()
        raise


def run(args, *, input=None, capture_output=False, timeout=None, check=False, **kwargs):
    global _owner_calls
    with _lock:
        owner=not enabled()
        if owner:_owner_calls+=1
    if owner:
        try:
            return subprocess.run(args, input=input, capture_output=capture_output, timeout=timeout, check=check, **kwargs)
        finally:
            with _lock:_owner_calls-=1
    if input is not None:
        kwargs['stdin'] = subprocess.PIPE
    if capture_output:
        kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    with popen(args, **kwargs) as proc:
        try:
            stdout, stderr = proc.communicate(input, timeout=timeout)
        except BaseException:
            proc.kill()
            proc.communicate()
            raise
        result = subprocess.CompletedProcess(args, proc.returncode, stdout, stderr)
        if check:
            result.check_returncode()
        return result


def read_text(path, *, encoding='utf-8', errors='strict'):
    """Read a CLI-owned worker file without widening its private credential ACL."""
    try:
        return Path(path).read_text(encoding=encoding, errors=errors)
    except PermissionError:
        if not enabled():
            raise
        value = require()
        _access(path, value, temporary=True)
        script = 'import pathlib,sys; sys.stdout.buffer.write(pathlib.Path(sys.argv[1]).read_text(encoding=sys.argv[2],errors=sys.argv[3]).encode("utf-8"))'
        result = run([value['python'],'-I','-c',script,str(path),encoding,errors],
                     capture_output=True,text=True,encoding='utf-8',timeout=20,check=True)
        return result.stdout


def clean_temporary(path):
    """CLI-private ACLs must be cleaned by the worker which created those files."""
    if not enabled():
        return
    root = _safe_temporary(path)
    if root is None or Path(path).resolve() != root.resolve():
        raise OSError('Refusing to remove a path outside an Armada runtime temporary folder.')
    if not root.exists():
        return
    with _lock:
        folder=_temporary.pop(os.path.normcase(str(root)),None)
        if folder:
            # Finish staging before releasing the no-delete handles. Removal itself
            # runs as the worker, so a redirected path cannot touch owner controls.
            if not folder.ready:folder.grant(folder.sid)
            folder.release()
    value = require()
    run([value['python'],'-I','-c','import shutil,sys; shutil.rmtree(sys.argv[1])',str(root)],
        capture_output=True,timeout=30,check=True)


@contextmanager
def temporary_directory(**kwargs):
    folder = temporary_folder(**kwargs)
    try:
        yield folder.name
    finally:
        if enabled():
            clean_temporary(folder.name)
        folder.cleanup()


def temporary_folder(**kwargs):
    """Owner-private inputs become shared only when the worker invocation starts."""
    if not enabled():return tempfile.TemporaryDirectory(**kwargs)
    from .worker_files import RuntimeFolder
    folder=RuntimeFolder(require(),**kwargs)
    with _lock:
        _temporary[os.path.normcase(folder.name)]=folder
    return folder


def temp_root():
    """Worker CLIs must be able to inspect every parent of runtime input paths."""
    if not enabled():
        return None
    return str(Path(require()['home'])/'AppData/Local/Temp')


def desktop(value):
    """Open only the unique Armada station created by the fixed setup task."""
    import ctypes as C
    from ctypes import wintypes as W
    with _lock:
        name = value['station']
        if name in _desktops:
            return name+'\\Agent'
        user = C.WinDLL('user32', use_last_error=True)
        user.OpenWindowStationW.argtypes, user.OpenWindowStationW.restype = [W.LPCWSTR, W.BOOL, W.DWORD], W.HANDLE
        handle = user.OpenWindowStationW(name, False, 0x20000)
        if not handle:
            subprocess.run([str(Path(os.environ['SystemRoot'])/'System32/schtasks.exe'),
                            '/Run','/TN',value['station_task']], capture_output=True,
                            creationflags=0x08000000, timeout=20)
            import time
            deadline = time.monotonic()+15
            while not handle and time.monotonic()<deadline:
                time.sleep(.05)
                handle = user.OpenWindowStationW(name, False, 0x20000)
        if not handle:
            raise OSError('The private worker desktop is unavailable. Repair worker setup in App Settings.')
        _desktops[name] = handle
        return name+'\\Agent'


def draft_desktop():
    """LPAC scripts use the private station too, with no inherited owner clipboard."""
    value=require()
    desktop(value)
    return value['station']+'\\Draft'


def status():
    value = state()
    return {'enabled': bool(value), 'ready': bool(value.get('ready')), 'pending': _pending,
            'username':value.get('username',''), 'folders':value.get('allowed_roots', []),
            'error': value.get('error','')}


def setup(roots):
    """Prepare an owner-only request, then request Windows elevation for account setup."""
    global _pending
    if os.name != 'nt':
        raise OSError('The isolated account requires Windows.')
    if any((parent/'realm.json').is_file() for parent in _path().resolve().parents):
        raise ValueError('Worker controls must be stored outside every realm folder. Change the app data location first.')
    with _lock:
        if _pending:
            return status()
        _owner_children[:]=[child for child in _owner_children if child.poll() is None]
        if _owner_calls or _owner_children:
            raise ValueError('Finish or Stop existing agent runs, provider sign-ins and connector checks before setting up the isolated worker.')
        existing = state()
        from .provider_keys import _crypt
        import getpass
        sid = subprocess.run(['whoami','/user','/fo','csv','/nh'], capture_output=True, text=True,
                             creationflags=0x08000000, check=True).stdout.strip().split(',')[-1].strip('"')
        token = secrets.token_hex(4)
        account = existing.get('username') or 'ArmadaW_'+token
        root = Path(os.environ['ProgramData'])/'ARMADA'/'Workers'/sid/account
        # These are explicit owner choices captured once, never reread from agent-editable realm.json.
        protected = list(dict.fromkeys([util.data_dir().resolve(), Path.home()/'.armada',
                                       Path.home()/'.claude', Path.home()/'.codex', Path.home()/'.gemini']))
        app_root = Path(__file__).resolve().parent.parent
        private = app_root.with_name(app_root.name+'-private')
        if private.is_dir():
            protected.append(private)
        allowed = []
        for item in roots:
            candidate = Path(item).resolve()
            if (not candidate.is_dir() or any(_within(p, candidate) or _within(candidate, p) for p in protected)
                    or _within(candidate, app_root) or _within(app_root, candidate)):
                raise ValueError('Worker folders must exist and must exclude owner settings and credentials.')
            allowed.append(str(candidate))
        value = {'username':account, 'owner_sid':sid, 'owner_name':getpass.getuser(),
                 'password':existing.get('password') or base64.b64encode(_crypt(secrets.token_urlsafe(48).encode())).decode(),
                 'ready':False, 'root':str(root), 'allowed_roots':allowed,
                 'station':'ArmadaWorker_'+secrets.token_hex(12),
                 'station_task':existing.get('station_task') or 'ARMADA worker desktop '+account,
                 'protected_roots':[str(p) for p in protected],
                 'python':sys._base_executable, 'python_root':sys.base_prefix,
                 'bootstrap_source':str(Path(__file__).with_name('worker_bootstrap.py')),
                 'app_root':str(app_root)}
        if existing.get('allowed_roots'):
            value['previous_roots'] = existing['allowed_roots']
        if existing.get('sid'):
            value['sid'] = existing['sid']
        from .engine import get_engine
        runtimes = {sys.base_prefix}
        for provider in ('claude','codex','gemini'):
            for item in get_engine(provider)._launcher() or []:
                if Path(item).is_file():
                    directory = Path(item).parent
                    if Path(item).suffix in ('.js','.cjs','.mjs') and (directory.parent/'package.json').is_file():
                        directory = directory.parent
                    runtimes.add(str(directory))
        value['runtime_roots'] = sorted(runtimes)
        value['path'] = list(dict.fromkeys([str(Path(p)) for p in runtimes] +
                            [str(Path(os.environ['SystemRoot'])/'System32'), os.environ['SystemRoot'],
                             str(Path(os.environ.get('ProgramFiles', 'C:/Program Files'))/'Git/bin')]))
        from . import execution_admission
        # Admission cannot promote a queued owner-identity turn between this check
        # and the pending manifest. New launches then fail closed until verification.
        with execution_admission._transaction() as execution:
            if any(row.get('state')=='running' for row in execution['tickets'].values()):
                raise ValueError('Finish or Stop existing agent runs before setting up the isolated worker. This protects newly stored keys from older owner-identity processes.')
            util.write_json_atomic(_path(), value)
        script = Path(__file__).with_name('worker_setup.ps1')
        _pending = True
        def provision():
            global _pending
            try:
                # ShellExecute's runas verb supplies the normal Windows UAC consent prompt.
                # No passwords or API keys occur in this command line.
                expression = ('$p=Start-Process -FilePath "$env:SystemRoot\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" '
                              '-Verb RunAs -WindowStyle Hidden -Wait -PassThru -ArgumentList @('+
                              ','.join("'"+a.replace("'", "''")+"'" for a in ['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File', '"'+str(script)+'"','-Request', '"'+str(_path())+'"'])+
                              '); exit $p.ExitCode')
                result = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',expression],
                                        creationflags=0x08000000, timeout=600, capture_output=True)
                current = state()
                if result.returncode or not current.get('sid'):
                    raise OSError('Windows account setup did not finish. '+current.get('setup_error', 'Check the UAC prompt and retry setup.'))
                current['ready'] = False
                util.write_json_atomic(_path(), current)
                verify()
                current=state()
                current.update(ready=True,error='')
                util.write_json_atomic(_path(),current)
                from .run_policy import audit
                audit('configure-worker', username=account, folders=allowed)
            except Exception as exc:
                log.warning('Worker setup failed (%s)',type(exc).__name__)
                current = state()
                current.update(ready=False, error=str(exc) if isinstance(exc, OSError) else 'Worker setup or verification failed. Agent launches are blocked; repair the account before continuing.')
                util.write_json_atomic(_path(), current)
            finally:
                _pending = False
        threading.Thread(target=provision, name='armada-worker-setup', daemon=True).start()
        return status()


def verify():
    """Real identity/access probe, using a synthetic DPAPI secret and owned process tree."""
    token=_checking.set(True)
    try:
        return _verify()
    except (OSError,ValueError):
        current=state()
        if current:
            current.update(ready=False,error='Worker isolation verification failed. Repair worker setup before running agents.')
            util.write_json_atomic(_path(),current)
        raise
    finally:
        _checking.reset(token)


def _verify():
    from .provider_keys import _crypt
    value = require()
    cipher = base64.b64encode(_crypt(b'armada-worker-boundary-proof')).decode()
    trusted = [value['bootstrap'], str(Path(value['root'])/'worker_station.ps1'), value['python'], __file__]
    # Supplying the encrypted bytes proves separation even if a blob were copied out
    # of the credential folder. Do not pass any real provider credential to this probe.
    script = ("import json,ctypes,base64,os,pathlib,subprocess; from ctypes import wintypes as W; "
              "exec("+repr('class B(ctypes.Structure):\n _fields_=[("n",W.DWORD),("p",ctypes.c_void_p)]\n'
                            'raw=base64.b64decode('+repr(cipher)+')\n'
                            'buf=ctypes.create_string_buffer(raw)\n'
                            'a=B(len(raw),ctypes.cast(buf,ctypes.c_void_p)); b=B()\n'
                            'decrypt=bool(ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(a),None,None,None,None,1,ctypes.byref(b)))\n'
                            'read=False; write=False\n'
                            'try:\n pathlib.Path('+repr(str(_path()))+').read_bytes(); read=True\nexcept OSError: pass\n'
                            'try:\n f=open('+repr(str(util.data_dir()/'worker-denial-probe'))+',"w"); f.close(); write=True\nexcept OSError: pass\n'
                            'trusted_write=False\n'
                            'for path in '+repr(trusted)+':\n'
                            ' try:\n  f=open(path,"r+b"); f.close(); trusted_write=True\n except OSError: pass\n'
                            'identity=subprocess.check_output(["whoami","/user","/fo","csv","/nh"],text=True).strip()\n'
                            'print(json.dumps(dict(identity=identity,decrypt=decrypt,read=read,write=write,trusted_write=trusted_write)))')+")")
    result = run([value['python'], '-I', '-c', script], capture_output=True, text=True, timeout=30,
                 creationflags=0x08000000)
    if result.returncode:
        raise OSError('The isolated Windows worker could not complete its boundary probe.')
    proof = json.loads(result.stdout.strip())
    proof['passed'] = value['sid'] in proof['identity'] and not any(proof[k] for k in ('decrypt','read','write','trusted_write'))
    util.write_json_atomic(util.data_dir()/'worker-proof.json', proof)
    if not proof['passed']:
        raise OSError('Windows worker credential isolation failed; agent execution is blocked.')
    return proof
