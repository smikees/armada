"""Windows alternate-account launch, retaining Python's pipe and communicate ownership.

No shell, credential arguments, owner environment inheritance or interactive desktop.
The regular supervisor assigns the suspended process to its kill-on-close Job Object.
"""
import ctypes as C
from ctypes import wintypes as W
import os
import subprocess


class Startup(C.Structure):
    _fields_ = [('cb', W.DWORD), ('reserved', W.LPWSTR), ('desktop', W.LPWSTR),
                ('title', W.LPWSTR), ('x', W.DWORD), ('y', W.DWORD), ('cx', W.DWORD),
                ('cy', W.DWORD), ('chars_x', W.DWORD), ('chars_y', W.DWORD),
                ('fill', W.DWORD), ('flags', W.DWORD), ('show', W.WORD),
                ('reserved_size', W.WORD), ('reserved_data', C.c_void_p),
                ('stdin', W.HANDLE), ('stdout', W.HANDLE), ('stderr', W.HANDLE)]


class Information(C.Structure):
    _fields_ = [('process', W.HANDLE), ('thread', W.HANDLE), ('pid', W.DWORD), ('tid', W.DWORD)]


class WorkerPopen(subprocess.Popen):
    def __init__(self, args, *, identity, spec, **kwargs):
        self._identity, self._spec = identity, spec
        self._worker_tree = None
        supervised = bool(kwargs.get('creationflags', 0) & 4)
        kwargs['creationflags'] = kwargs.get('creationflags', 0) | 4
        super().__init__(args, **kwargs)
        if not supervised:
            from .engine.windows_job import WindowsJob
            try:
                self._worker_tree = WindowsJob()
                self._worker_tree.attach_and_resume(self)
            except BaseException:
                self.kill()
                raise

    def _cleanup_worker(self):
        if self._worker_tree:
            self._worker_tree.close()
            self._worker_tree = None
        self._spec.unlink(missing_ok=True)
        try:
            self._spec.parent.rmdir()
        except FileNotFoundError:
            pass

    def kill(self):
        try:
            if self._worker_tree:
                self._worker_tree.close()
        finally:
            self._worker_tree = None
            super().kill()

    terminate = kill

    def wait(self, timeout=None):
        result = super().wait(timeout=timeout)
        self._cleanup_worker()
        return result

    def _execute_child(self, args, executable, preexec_fn, close_fds, pass_fds, cwd, env,
                       startupinfo, creationflags, shell, p2cread, p2cwrite, c2pread,
                       c2pwrite, errread, errwrite, *unused):
        from . import worker
        import _winapi
        if shell or pass_fds or preexec_fn:
            raise ValueError('Worker launches require an argument array without shell or extra handles.')
        info = Startup()
        info.cb = C.sizeof(info)
        info.desktop = worker.desktop(self._identity)
        info.flags = 0x101  # USESHOWWINDOW | USESTDHANDLES
        info.show = 0
        info.stdin, info.stdout, info.stderr = p2cread, c2pwrite, errwrite
        result = Information()
        api = C.WinDLL('advapi32', use_last_error=True).CreateProcessWithLogonW
        api.argtypes = [W.LPCWSTR, W.LPCWSTR, W.LPCWSTR, W.DWORD, W.LPCWSTR, W.LPWSTR,
                        W.DWORD, C.c_void_p, W.LPCWSTR, C.POINTER(Startup), C.POINTER(Information)]
        api.restype = W.BOOL
        command = C.create_unicode_buffer(subprocess.list2cmdline([
            self._identity['python'], '-I', self._identity['bootstrap'], str(self._spec)]))
        # NULL environment builds the worker's own profile environment, never the owner's.
        try:
            if not api(self._identity['username'], '.', worker.password(self._identity), 1,
                       self._identity['python'], command, 0x08000404,
                       None, self._identity['home'], C.byref(info), C.byref(result)):
                code = C.get_last_error()
                raise OSError(code, 'Windows could not start the isolated worker. Repair worker setup in App Settings.')
        finally:
            self._close_pipe_fds(p2cread, p2cwrite, c2pread, c2pwrite, errread, errwrite)
        self._child_created = True
        self._handle = subprocess.Handle(result.process)
        self.pid = result.pid
        # Reopening a worker-owned thread by ID is denied to the owner account.
        # Keep the creation handle until the supervisor has assigned its Job Object.
        self._worker_thread = subprocess.Handle(result.thread)
