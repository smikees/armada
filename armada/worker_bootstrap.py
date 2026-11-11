"""Standalone, unprivileged process trampoline. Never imports the Armada application.

The owner writes the launch description in a worker-readable, owner-writable directory.
Only this short command crosses CreateProcessWithLogonW's command-line limit. The whole
trampoline and its descendants enter the invocation Job Object before execution resumes.
"""
import json
import os
import subprocess
import sys


def observation_rights(spec):
    """Retain owner administration of worker children/files; no reverse access."""
    import ctypes as C
    from ctypes import wintypes as W
    adv = C.WinDLL('advapi32', use_last_error=True)
    kernel = C.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = W.HANDLE
    kernel.CloseHandle.argtypes = [W.HANDLE]
    kernel.LocalFree.argtypes = [C.c_void_p]
    adv.OpenProcessToken.argtypes = [W.HANDLE, W.DWORD, C.POINTER(W.HANDLE)]
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [W.LPCWSTR, W.DWORD, C.POINTER(C.c_void_p), C.c_void_p]
    adv.GetSecurityDescriptorDacl.argtypes = [C.c_void_p, C.POINTER(W.BOOL), C.POINTER(C.c_void_p), C.POINTER(W.BOOL)]
    adv.SetTokenInformation.argtypes = [W.HANDLE, C.c_int, C.c_void_p, W.DWORD]
    descriptor, token = C.c_void_p(), W.HANDLE()
    try:
        if not adv.OpenProcessToken(kernel.GetCurrentProcess(), 0x88, C.byref(token)):
            raise C.WinError(C.get_last_error())
        sddl = f'D:(A;;GA;;;SY)(A;;GA;;;BA)(A;;GA;;;{spec["sid"]})(A;;GA;;;{spec["owner_sid"]})'
        if not adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, C.byref(descriptor), None):
            raise C.WinError(C.get_last_error())
        acl, present, defaulted = C.c_void_p(), W.BOOL(), W.BOOL()
        if not adv.GetSecurityDescriptorDacl(descriptor, C.byref(present), C.byref(acl), C.byref(defaulted)):
            raise C.WinError(C.get_last_error())
        if not adv.SetTokenInformation(token, 6, C.byref(acl), C.sizeof(acl)):
            raise C.WinError(C.get_last_error())
    finally:
        if token:
            kernel.CloseHandle(token)
        if descriptor:
            kernel.LocalFree(descriptor)


def main():
    with open(sys.argv[1], encoding='utf-8') as stream:
        spec = json.load(stream)
    observation_rights(spec)
    if spec.get('terminal'):
        import runpy
        from pathlib import Path
        spec['request_path'] = sys.argv[1]
        return runpy.run_path(str(Path(__file__).with_name('worker_terminal.py')))['run'](spec)
    process = subprocess.Popen(spec['args'], cwd=spec['cwd'], env=spec['env'],
                               stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr,
                               creationflags=0x08000000)
    return process.wait()


if __name__ == '__main__':
    raise SystemExit(main())
