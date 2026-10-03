"""Start the desktop app with Explorer's lifetime and unvirtualized user context.

Detaching a console alone does not escape an MSIX caller's job/device map. Use the
Windows parent-process attribute and the desktop user's environment instead.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def _windows():
    import ctypes as c
    from ctypes import wintypes as w
    k = c.WinDLL('kernel32', use_last_error=True)
    u = c.WinDLL('user32', use_last_error=True)
    u.GetShellWindow.restype = w.HWND
    u.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
    pid = w.DWORD()
    u.GetWindowThreadProcessId(u.GetShellWindow(), c.byref(pid))
    if not pid.value:
        raise OSError('The Windows desktop is not ready. Start Armada after signing in.')
    return c, w, k, pid.value


def desktop_parent():
    """True only for a process launched directly under the interactive desktop."""
    if os.name != 'nt':
        return True
    c, w, k, shell_pid = _windows()
    class Basic(c.Structure):
        _fields_ = [('reserved', c.c_void_p), ('peb', c.c_void_p),
                    ('reserved2', c.c_void_p * 2), ('pid', c.c_void_p), ('parent', c.c_void_p)]
    n = c.WinDLL('ntdll')
    n.NtQueryInformationProcess.argtypes = [w.HANDLE, w.ULONG, c.c_void_p, w.ULONG, c.c_void_p]
    data = Basic()
    if n.NtQueryInformationProcess(w.HANDLE(-1), 0, c.byref(data), c.sizeof(data), None):
        raise OSError('Could not verify Armada desktop ownership.')
    return data.parent == shell_pid


def spawn(argv, cwd=None):
    """Launch under Explorer, outside the caller's job and virtualized filesystem."""
    c, w, k, shell_pid = _windows()
    class Startup(c.Structure):
        _fields_ = [('cb', w.DWORD), ('reserved', w.LPWSTR), ('desktop', w.LPWSTR),
                    ('title', w.LPWSTR), ('x', w.DWORD), ('y', w.DWORD),
                    ('cx', w.DWORD), ('cy', w.DWORD), ('charsx', w.DWORD), ('charsy', w.DWORD),
                    ('fill', w.DWORD), ('flags', w.DWORD), ('show', w.WORD),
                    ('reserved_size', w.WORD), ('reserved_ptr', c.c_void_p),
                    ('stdin', w.HANDLE), ('stdout', w.HANDLE), ('stderr', w.HANDLE)]
    class Extended(c.Structure):
        _fields_ = [('startup', Startup), ('attributes', c.c_void_p)]
    class Process(c.Structure):
        _fields_ = [('process', w.HANDLE), ('thread', w.HANDLE), ('pid', w.DWORD), ('tid', w.DWORD)]
    k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    k.OpenProcess.restype = w.HANDLE
    k.CloseHandle.argtypes = [w.HANDLE]
    k.InitializeProcThreadAttributeList.argtypes = [c.c_void_p, w.DWORD, w.DWORD, c.POINTER(c.c_size_t)]
    k.UpdateProcThreadAttribute.argtypes = [c.c_void_p, w.DWORD, c.c_size_t, c.c_void_p, c.c_size_t, c.c_void_p, c.c_void_p]
    k.DeleteProcThreadAttributeList.argtypes = [c.c_void_p]
    k.CreateProcessW.argtypes = [w.LPCWSTR, w.LPWSTR, c.c_void_p, c.c_void_p, w.BOOL,
                                w.DWORD, c.c_void_p, w.LPCWSTR, c.c_void_p, c.c_void_p]
    parent = k.OpenProcess(0x1080, False, shell_pid)  # query + create process
    if not parent:
        raise c.WinError(c.get_last_error())
    token, env = w.HANDLE(), c.c_void_p()
    attributes = None
    attributes_ready = False
    userenv = c.WinDLL('userenv', use_last_error=True)
    userenv.CreateEnvironmentBlock.argtypes = [c.POINTER(c.c_void_p), w.HANDLE, w.BOOL]
    userenv.DestroyEnvironmentBlock.argtypes = [c.c_void_p]
    adv = c.WinDLL('advapi32', use_last_error=True)
    adv.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, c.POINTER(w.HANDLE)]
    try:
        if not adv.OpenProcessToken(parent, 8, c.byref(token)):
            raise c.WinError(c.get_last_error())
        if not userenv.CreateEnvironmentBlock(c.byref(env), token, False):
            raise c.WinError(c.get_last_error())
        size = c.c_size_t()
        k.InitializeProcThreadAttributeList(None, 1, 0, c.byref(size))
        attributes = c.create_string_buffer(size.value)
        if not k.InitializeProcThreadAttributeList(attributes, 1, 0, c.byref(size)):
            raise c.WinError(c.get_last_error())
        attributes_ready = True
        handle = w.HANDLE(parent)
        if not k.UpdateProcThreadAttribute(attributes, 0, 0x20000, c.byref(handle), c.sizeof(handle), None, None):
            raise c.WinError(c.get_last_error())
        si, pi = Extended(), Process()
        si.startup.cb = c.sizeof(si)
        si.attributes = c.cast(attributes, c.c_void_p)
        command = c.create_unicode_buffer(subprocess.list2cmdline([str(a) for a in argv]))
        # The specified parent supplies job membership, token and device map. Do not
        # inherit handles or caller environment; both can retain the caller's lifetime.
        if not k.CreateProcessW(str(argv[0]), command, None, None, False,
                                0x00080000 | 0x00000400 | 0x08000000,
                                env, str(cwd or Path.cwd()), c.byref(si), c.byref(pi)):
            raise c.WinError(c.get_last_error())
        k.CloseHandle(pi.thread)
        k.CloseHandle(pi.process)
        return pi.pid
    finally:
        if attributes_ready:
            k.DeleteProcThreadAttributeList(attributes)
        if env:
            userenv.DestroyEnvironmentBlock(env)
        if token:
            k.CloseHandle(token)
        k.CloseHandle(parent)


def relaunch_if_needed(args):
    if os.name != 'nt' or desktop_parent():
        return False
    host = Path(sys.executable).with_name('ARMADA.exe')
    if not host.is_file():
        host = Path(sys.executable)
    spawn([str(host), '-m', 'armada', *args])
    return True
