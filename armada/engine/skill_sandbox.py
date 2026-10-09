"""Windows LPAC launcher for approved draft scripts; no network or child processes.

Only private staged trees receive a unique container SID. Production ACLs are never
modified. The existing process supervisor still owns deadlines, cancellation and pipes.
See Microsoft's implementing-an-appcontainer and UpdateProcThreadAttribute references.
"""
from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
import os
from pathlib import Path
import subprocess
import uuid


class Startup(C.Structure):
    _fields_ = [("cb", W.DWORD), ("reserved", W.LPWSTR), ("desktop", W.LPWSTR), ("title", W.LPWSTR),
        ("x", W.DWORD), ("y", W.DWORD), ("width", W.DWORD), ("height", W.DWORD),
        ("xc", W.DWORD), ("yc", W.DWORD), ("fill", W.DWORD), ("flags", W.DWORD),
        ("show", W.WORD), ("reserved2_size", W.WORD), ("reserved2", C.c_void_p),
        ("stdin", W.HANDLE), ("stdout", W.HANDLE), ("stderr", W.HANDLE)]


class StartupEx(C.Structure):
    _fields_ = [("startup", Startup), ("attributes", C.c_void_p)]


class ProcessInfo(C.Structure):
    _fields_ = [("process", W.HANDLE), ("thread", W.HANDLE), ("pid", W.DWORD), ("tid", W.DWORD)]


class SidAndAttributes(C.Structure):
    _fields_ = [("sid", C.c_void_p), ("attributes", W.DWORD)]


class Capabilities(C.Structure):
    _fields_ = [("sid", C.c_void_p), ("capabilities", C.POINTER(SidAndAttributes)),
               ("count", W.DWORD), ("reserved", W.DWORD)]


class Trustee(C.Structure):
    _fields_ = [("multiple", C.c_void_p), ("operation", C.c_int), ("form", C.c_int),
               ("type", C.c_int), ("name", C.c_void_p)]


class Access(C.Structure):
    _fields_ = [("permissions", W.DWORD), ("mode", C.c_int), ("inherit", W.DWORD), ("trustee", Trustee)]


def available():
    return os.name == "nt" and hasattr(C, "WinDLL")


class SkillSandbox:
    """A launch factory accepted only by the owned command supervisor."""
    def __init__(self, *, readonly, writable):
        if not available():
            raise ValueError("Isolated skill scripts currently require Windows. No unrestricted fallback is used.")
        self.kernel = C.WinDLL("kernel32", use_last_error=True)
        self.security = C.WinDLL("advapi32", use_last_error=True)
        self.userenv = C.WinDLL("userenv", use_last_error=True)
        self.base = C.WinDLL("kernelbase", use_last_error=True)
        self.sid = C.c_void_p()
        self.cap_sid = None
        self.profile = "armada.draft." + uuid.uuid4().hex
        self.profile_created = False
        self._setup()
        result = self.userenv.CreateAppContainerProfile(self.profile, self.profile, "ARMADA isolated draft script", None, 0, C.byref(self.sid))
        if result:
            raise OSError(f"Could not create isolated script identity: {result:#x}")
        self.profile_created = True
        try:
            self.cap_sid = []
            for name in ("lpacFileRead", "registryRead"):
                groups, caps = C.POINTER(C.c_void_p)(), C.POINTER(C.c_void_p)()
                ng, nc = W.DWORD(), W.DWORD()
                self._ok(self.base.DeriveCapabilitySidsFromName(name, C.byref(groups), C.byref(ng), C.byref(caps), C.byref(nc)))
                if nc.value != 1:
                    raise OSError("Windows did not return the required LPAC system read capability.")
                self.cap_sid.append(caps[0])
                for index in range(ng.value):
                    self.kernel.LocalFree(groups[index])
                self.kernel.LocalFree(groups)
                self.kernel.LocalFree(caps)
            self.caps = (SidAndAttributes * len(self.cap_sid))(*[SidAndAttributes(s, 4) for s in self.cap_sid])
            # Windows creates a private package profile outside the run. Deny its file
            # writes explicitly: the script's only writable files must be in output/.
            sid_text, profile_path = W.LPWSTR(), W.LPWSTR()
            try:
                self._ok(self.security.ConvertSidToStringSidW(self.sid, C.byref(sid_text)))
                error = self.userenv.GetAppContainerFolderPath(sid_text, C.byref(profile_path))
                if error:
                    raise OSError(f"Could not locate isolated script profile: {error:#x}")
                self._grant(Path(profile_path.value).parent, 0xD0156, mode=3)
            finally:
                self.kernel.LocalFree(sid_text)
                C.OleDLL("ole32").CoTaskMemFree(C.cast(profile_path, C.c_void_p))
            for folder in readonly:
                self._grant(Path(folder), 0x1200A9)  # FILE_GENERIC_READ | EXECUTE
            self._grant(Path(writable), 0x1301BF)  # modify, not ACL/ownership changes
        except BaseException:
            self.close()
            raise

    def _setup(self):
        signatures = {
            (self.userenv, "DeriveAppContainerSidFromAppContainerName"): ([W.LPCWSTR, C.POINTER(C.c_void_p)], W.LONG),
            (self.userenv, "CreateAppContainerProfile"): ([W.LPCWSTR, W.LPCWSTR, W.LPCWSTR, C.c_void_p, W.DWORD, C.POINTER(C.c_void_p)], W.LONG),
            (self.userenv, "DeleteAppContainerProfile"): ([W.LPCWSTR], W.LONG),
            (self.userenv, "GetAppContainerFolderPath"): ([W.LPCWSTR, C.POINTER(W.LPWSTR)], W.LONG),
            (self.security, "ConvertSidToStringSidW"): ([C.c_void_p, C.POINTER(W.LPWSTR)], W.BOOL),
            (self.base, "DeriveCapabilitySidsFromName"): ([W.LPCWSTR, C.POINTER(C.POINTER(C.c_void_p)), C.POINTER(W.DWORD), C.POINTER(C.POINTER(C.c_void_p)), C.POINTER(W.DWORD)], W.BOOL),
            (self.kernel, "LocalFree"): ([C.c_void_p], C.c_void_p),
            (self.security, "FreeSid"): ([C.c_void_p], C.c_void_p),
            (self.security, "GetNamedSecurityInfoW"): ([W.LPWSTR, C.c_int, W.DWORD, C.c_void_p, C.c_void_p, C.POINTER(C.c_void_p), C.c_void_p, C.POINTER(C.c_void_p)], W.DWORD),
            (self.security, "SetEntriesInAclW"): ([W.DWORD, C.POINTER(Access), C.c_void_p, C.POINTER(C.c_void_p)], W.DWORD),
            (self.security, "SetNamedSecurityInfoW"): ([W.LPWSTR, C.c_int, W.DWORD, C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p], W.DWORD),
            (self.kernel, "InitializeProcThreadAttributeList"): ([C.c_void_p, W.DWORD, W.DWORD, C.POINTER(C.c_size_t)], W.BOOL),
            (self.kernel, "UpdateProcThreadAttribute"): ([C.c_void_p, W.DWORD, C.c_size_t, C.c_void_p, C.c_size_t, C.c_void_p, C.c_void_p], W.BOOL),
            (self.kernel, "DeleteProcThreadAttributeList"): ([C.c_void_p], None),
            (self.kernel, "CreateProcessW"): ([W.LPCWSTR, W.LPWSTR, C.c_void_p, C.c_void_p, W.BOOL, W.DWORD, C.c_void_p, W.LPCWSTR, C.POINTER(StartupEx), C.POINTER(ProcessInfo)], W.BOOL),
            (self.kernel, "CloseHandle"): ([W.HANDLE], W.BOOL),
            (self.kernel, "GetExitCodeProcess"): ([W.HANDLE, C.POINTER(W.DWORD)], W.BOOL),
            (self.kernel, "WaitForSingleObject"): ([W.HANDLE, W.DWORD], W.DWORD),
            (self.kernel, "TerminateProcess"): ([W.HANDLE, W.UINT], W.BOOL),
        }
        for (library, name), (args, result) in signatures.items():
            fn = getattr(library, name)
            fn.argtypes, fn.restype = args, result

    @staticmethod
    def _ok(value):
        if not value:
            raise C.WinError(C.get_last_error())

    def _grant(self, path, access, *, mode=1):
        # Callers supply only host-created staged copies, never an input's original folder.
        dacl, descriptor, updated = C.c_void_p(), C.c_void_p(), C.c_void_p()
        error = self.security.GetNamedSecurityInfoW(str(path), 1, 4, None, None, C.byref(dacl), None, C.byref(descriptor))
        if error:
            raise C.WinError(error)
        try:
            entry = Access(access, mode, 3, Trustee(None, 0, 0, 1, self.sid))
            error = self.security.SetEntriesInAclW(1, C.byref(entry), dacl, C.byref(updated))
            if not error:
                error = self.security.SetNamedSecurityInfoW(str(path), 1, 4, None, None, updated, None)
            if error:
                raise C.WinError(error)
        finally:
            self.kernel.LocalFree(updated)
            self.kernel.LocalFree(descriptor)

    def __call__(self, args, *, cwd, env, **kwargs):
        import msvcrt
        pairs = [os.pipe() for _ in range(3)]
        child_fds = [pairs[0][0], pairs[1][1], pairs[2][1]]
        parent_fds = [pairs[0][1], pairs[1][0], pairs[2][0]]
        attributes = None
        attributes_ready = False
        info = ProcessInfo()
        process = None
        try:
            for fd in child_fds:
                os.set_inheritable(fd, True)
            handles = (W.HANDLE * 3)(*[msvcrt.get_osfhandle(fd) for fd in child_fds])
            size = C.c_size_t()
            self.kernel.InitializeProcThreadAttributeList(None, 4, 0, C.byref(size))
            attributes = C.create_string_buffer(size.value)
            self._ok(self.kernel.InitializeProcThreadAttributeList(attributes, 4, 0, C.byref(size)))
            attributes_ready = True
            caps = Capabilities(self.sid, self.caps, len(self.caps), 0)
            opt_out, child_policy = W.DWORD(1), W.DWORD(1)
            for key, value in ((0x20009, caps), (0x2000F, opt_out), (0x2000E, child_policy), (0x20002, handles)):
                self._ok(self.kernel.UpdateProcThreadAttribute(attributes, 0, key, C.byref(value), C.sizeof(value), None, None))
            startup = StartupEx()
            startup.startup.cb = C.sizeof(startup)
            startup.startup.flags = 0x100  # STARTF_USESTDHANDLES
            startup.startup.stdin, startup.startup.stdout, startup.startup.stderr = handles
            startup.attributes = C.cast(attributes, C.c_void_p)
            block = C.create_unicode_buffer("\0".join(k + "=" + v for k, v in sorted(env.items(), key=lambda p: p[0].upper())) + "\0\0")
            self._ok(self.kernel.CreateProcessW(str(args[0]), C.create_unicode_buffer(subprocess.list2cmdline(args)),
                # DETACHED_PROCESS avoids starting conhost (a forbidden child). Pipes
                # supply stdio; no visible console or inherited interactive console.
                None, None, True, 0x0008040C, block, str(cwd), C.byref(startup), C.byref(info)))
            # The supervisor assigns this still-suspended child to its kill-on-close Job Object.
            process = NativeProcess(self.kernel, info.process, info.pid, parent_fds, args)
            return process
        finally:
            if info.thread:
                self.kernel.CloseHandle(info.thread)
            if attributes_ready:
                self.kernel.DeleteProcThreadAttributeList(attributes)
            for fd in child_fds:
                os.close(fd)
            if process is None:
                if info.process:
                    self.kernel.TerminateProcess(info.process, 1)
                    self.kernel.CloseHandle(info.process)
                for fd in parent_fds:
                    os.close(fd)

    def close(self):
        error = None
        if self.profile_created:
            result = self.userenv.DeleteAppContainerProfile(self.profile)
            self.profile_created = False
            if result:
                error = OSError(f"Could not remove isolated script profile: {result:#x}")
        if self.cap_sid:
            for sid in self.cap_sid:
                self.kernel.LocalFree(sid)
            self.cap_sid = None
        if self.sid:
            self.security.FreeSid(self.sid)
            self.sid = C.c_void_p()
        if error:
            raise error

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class NativeProcess:
    def __init__(self, api, handle, pid, fds, args):
        class Handle(int):
            closed = False
            def Close(self):
                if not self.closed:
                    api.CloseHandle(self)
                    self.closed = True
        self.api, self._handle, self.pid, self.args = api, Handle(handle), pid, args
        self.stdin = os.fdopen(fds[0], "w", encoding="utf-8")
        self.stdout = os.fdopen(fds[1], "r", encoding="utf-8")
        self.stderr = os.fdopen(fds[2], "r", encoding="utf-8")
        self.returncode = None

    def poll(self):
        if self.returncode is not None:
            return self.returncode
        # ExitProcess can publish its code before the process object is signaled.
        # Treating that interval as completion lets job cleanup terminate a script
        # that is still exiting and replace its successful code with 1.
        value = self.api.WaitForSingleObject(self._handle, 0)
        if value == 258:
            return None
        if value:
            raise C.WinError(C.get_last_error())
        code = W.DWORD()
        if not self.api.GetExitCodeProcess(self._handle, C.byref(code)):
            raise C.WinError(C.get_last_error())
        self.returncode = code.value
        return self.returncode

    def wait(self, timeout=None):
        value = self.api.WaitForSingleObject(self._handle, 0xFFFFFFFF if timeout is None else max(0, int(timeout * 1000)))
        if value == 258:
            raise subprocess.TimeoutExpired(self.args, timeout)
        if value:
            raise C.WinError(C.get_last_error())
        return self.poll()

    def kill(self):
        if not self.api.TerminateProcess(self._handle, 1):
            raise C.WinError(C.get_last_error())
