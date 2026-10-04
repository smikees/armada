"""Windows CLI process-tree ownership using documented Job Object and thread APIs.

Start suspended so no tool child can escape before assignment. Failure to establish ownership
fails launch; process.py then kills the still-suspended child. No shell or taskkill is involved.
"""
import ctypes as C
from ctypes import wintypes as W
import time


class BasicLimits(C.Structure):
    _fields_ = [("PerProcessUserTimeLimit", C.c_longlong), ("PerJobUserTimeLimit", C.c_longlong),
                ("LimitFlags", W.DWORD), ("MinimumWorkingSetSize", C.c_size_t),
                ("MaximumWorkingSetSize", C.c_size_t), ("ActiveProcessLimit", W.DWORD),
                ("Affinity", C.c_size_t), ("PriorityClass", W.DWORD), ("SchedulingClass", W.DWORD)]


class ExtendedLimits(C.Structure):
    _fields_ = [("BasicLimitInformation", BasicLimits), ("IoInfo", C.c_ulonglong * 6),
                ("ProcessMemoryLimit", C.c_size_t), ("JobMemoryLimit", C.c_size_t),
                ("PeakProcessMemoryUsed", C.c_size_t), ("PeakJobMemoryUsed", C.c_size_t)]


class ThreadEntry(C.Structure):
    _fields_ = [("dwSize", W.DWORD), ("cntUsage", W.DWORD), ("th32ThreadID", W.DWORD),
                ("th32OwnerProcessID", W.DWORD), ("tpBasePri", W.LONG),
                ("tpDeltaPri", W.LONG), ("dwFlags", W.DWORD)]


class Accounting(C.Structure):
    _fields_ = [("TotalUserTime", C.c_longlong), ("TotalKernelTime", C.c_longlong),
                ("ThisPeriodTotalUserTime", C.c_longlong), ("ThisPeriodTotalKernelTime", C.c_longlong),
                ("TotalPageFaultCount", W.DWORD), ("TotalProcesses", W.DWORD),
                ("ActiveProcesses", W.DWORD), ("TotalTerminatedProcesses", W.DWORD)]


class WindowsJob:
    def __init__(self):
        self.api = C.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateJobObjectW": ([C.c_void_p, W.LPCWSTR], W.HANDLE),
            "SetInformationJobObject": ([W.HANDLE, C.c_int, C.c_void_p, W.DWORD], W.BOOL),
            "AssignProcessToJobObject": ([W.HANDLE, W.HANDLE], W.BOOL),
            "TerminateJobObject": ([W.HANDLE, W.UINT], W.BOOL),
            "QueryInformationJobObject": ([W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.c_void_p], W.BOOL),
            "OpenProcess": ([W.DWORD, W.BOOL, W.DWORD], W.HANDLE),
            "IsProcessInJob": ([W.HANDLE, W.HANDLE, C.POINTER(W.BOOL)], W.BOOL),
            "WaitForSingleObject": ([W.HANDLE, W.DWORD], W.DWORD),
            "CloseHandle": ([W.HANDLE], W.BOOL),
            "CreateToolhelp32Snapshot": ([W.DWORD, W.DWORD], W.HANDLE),
            "Thread32First": ([W.HANDLE, C.POINTER(ThreadEntry)], W.BOOL),
            "Thread32Next": ([W.HANDLE, C.POINTER(ThreadEntry)], W.BOOL),
            "OpenThread": ([W.DWORD, W.BOOL, W.DWORD], W.HANDLE),
            "ResumeThread": ([W.HANDLE], W.DWORD),
        }
        for name, (args, result) in signatures.items():
            fn = getattr(self.api, name)
            fn.argtypes, fn.restype = args, result
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise C.WinError(C.get_last_error())
        limits = ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.handle, 9, C.byref(limits), C.sizeof(limits)):
            error = C.WinError(C.get_last_error())
            self.close()
            raise error

    def attach_and_resume(self, process):
        if not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise C.WinError(C.get_last_error())
        snapshot = self.api.CreateToolhelp32Snapshot(4, 0)  # TH32CS_SNAPTHREAD
        if snapshot == C.c_void_p(-1).value:
            raise C.WinError(C.get_last_error())
        try:
            entry = ThreadEntry()
            entry.dwSize = C.sizeof(entry)
            more = self.api.Thread32First(snapshot, C.byref(entry))
            while more:
                if entry.th32OwnerProcessID == process.pid:
                    thread = self.api.OpenThread(2, False, entry.th32ThreadID)  # THREAD_SUSPEND_RESUME
                    if not thread:
                        raise C.WinError(C.get_last_error())
                    try:
                        if self.api.ResumeThread(thread) == 0xFFFFFFFF:
                            raise C.WinError(C.get_last_error())
                        return
                    finally:
                        self.api.CloseHandle(thread)
                more = self.api.Thread32Next(snapshot, C.byref(entry))
            raise OSError("Could not find the suspended CLI thread")
        finally:
            self.api.CloseHandle(snapshot)

    def _process_handles(self):
        """Hold identities across termination; querying numeric PIDs afterward can see reuse."""
        capacity = 64
        while capacity <= 65536:
            data = C.create_string_buffer(8 + C.sizeof(C.c_size_t) * capacity)
            ok = self.api.QueryInformationJobObject(self.handle, 3, data, C.sizeof(data), None)
            assigned, returned = (W.DWORD * 2).from_buffer(data)
            if not ok and C.get_last_error() != 234:  # ERROR_MORE_DATA
                raise C.WinError(C.get_last_error())
            if ok and returned >= assigned:
                break
            capacity = max(capacity * 2, assigned)
        else:
            raise OSError('Too many processes to verify job cleanup')
        handles = []
        for pid in (C.c_size_t * returned).from_buffer(data, 8):
            handle = self.api.OpenProcess(0x101000, False, pid)  # SYNCHRONIZE | QUERY_LIMITED_INFORMATION
            if not handle:  # exited before opening; no live handle remains
                if C.get_last_error() == 87:
                    continue
                for owned in handles: self.api.CloseHandle(owned)
                raise C.WinError(C.get_last_error())
            member = W.BOOL()
            if self.api.IsProcessInJob(handle, self.handle, C.byref(member)) and member.value:
                handles.append(handle)
            else:
                self.api.CloseHandle(handle)
        return handles

    def close(self):
        if self.handle:
            # KILL_ON_JOB_CLOSE alone requests asynchronous termination. Keep the handle long
            # enough to observe zero active processes before publishing a terminal run result.
            processes = self._process_handles()
            deadline = time.monotonic() + 3
            try:
                if not self.api.TerminateJobObject(self.handle, 1):
                    raise C.WinError(C.get_last_error())
                while True:
                    info = Accounting()
                    if not self.api.QueryInformationJobObject(self.handle, 1, C.byref(info), C.sizeof(info), None):
                        raise C.WinError(C.get_last_error())
                    if info.ActiveProcesses == 0:
                        break
                    if time.monotonic() >= deadline:
                        raise OSError('Windows process-tree termination did not finish within 3 seconds')
                    time.sleep(.01)
                for process in processes:
                    milliseconds = max(0, int((deadline-time.monotonic()) * 1000))
                    if self.api.WaitForSingleObject(process, milliseconds) != 0:
                        raise OSError('Windows descendant did not finish terminating within 3 seconds')
            finally:
                for process in processes:
                    self.api.CloseHandle(process)
                if not self.api.CloseHandle(self.handle):
                    raise C.WinError(C.get_last_error())
                self.handle = None
