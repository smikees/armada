"""Worker-side Windows pseudoconsole for provider/connector sign-in only.

Runs at worker privilege inside the invocation Job. Owner UI receives only the
CLI's terminal output; browser authorization URLs use the existing validated flow.
"""
import ctypes as C
from ctypes import wintypes as W
import os
import subprocess
import sys
import threading


class Coord(C.Structure):
    _fields_ = [('x', C.c_short), ('y', C.c_short)]


class Startup(C.Structure):
    _fields_ = [('cb',W.DWORD), ('reserved',W.LPWSTR), ('desktop',W.LPWSTR), ('title',W.LPWSTR),
                ('x',W.DWORD), ('y',W.DWORD), ('cx',W.DWORD), ('cy',W.DWORD),
                ('chars_x',W.DWORD), ('chars_y',W.DWORD), ('fill',W.DWORD), ('flags',W.DWORD),
                ('show',W.WORD), ('reserved_size',W.WORD), ('reserved_data',C.c_void_p),
                ('stdin',W.HANDLE), ('stdout',W.HANDLE), ('stderr',W.HANDLE)]


class Extended(C.Structure):
    _fields_ = [('startup',Startup), ('attributes',C.c_void_p)]


class Information(C.Structure):
    _fields_ = [('process',W.HANDLE), ('thread',W.HANDLE), ('pid',W.DWORD), ('tid',W.DWORD)]


def run(spec):
    api = C.WinDLL('kernel32', use_last_error=True)
    signatures = {
        'CreatePipe':([C.POINTER(W.HANDLE),C.POINTER(W.HANDLE),C.c_void_p,W.DWORD],W.BOOL),
        'CreatePseudoConsole':([Coord,W.HANDLE,W.HANDLE,W.DWORD,C.POINTER(W.HANDLE)],W.LONG),
        'ClosePseudoConsole':([W.HANDLE],None), 'CloseHandle':([W.HANDLE],W.BOOL),
        'InitializeProcThreadAttributeList':([C.c_void_p,W.DWORD,W.DWORD,C.POINTER(C.c_size_t)],W.BOOL),
        'UpdateProcThreadAttribute':([C.c_void_p,W.DWORD,C.c_size_t,C.c_void_p,C.c_size_t,C.c_void_p,C.c_void_p],W.BOOL),
        'DeleteProcThreadAttributeList':([C.c_void_p],None),
        'CreateProcessW':([W.LPCWSTR,W.LPWSTR,C.c_void_p,C.c_void_p,W.BOOL,W.DWORD,C.c_void_p,W.LPCWSTR,C.POINTER(Extended),C.POINTER(Information)],W.BOOL),
        'WaitForSingleObject':([W.HANDLE,W.DWORD],W.DWORD),
        'GetExitCodeProcess':([W.HANDLE,C.POINTER(W.DWORD)],W.BOOL),
        'ReadFile':([W.HANDLE,C.c_void_p,W.DWORD,C.POINTER(W.DWORD),C.c_void_p],W.BOOL),
        'WriteFile':([W.HANDLE,C.c_void_p,W.DWORD,C.POINTER(W.DWORD),C.c_void_p],W.BOOL),
    }
    for name,(args,result) in signatures.items():
        getattr(api,name).argtypes, getattr(api,name).restype = args,result
    input_read,input_write,output_read,output_write,console = [W.HANDLE() for _ in range(5)]
    info = Extended(); info.startup.cb = C.sizeof(info)
    process = Information()
    attributes = None
    try:
        if not api.CreatePipe(C.byref(input_read),C.byref(input_write),None,0) or not api.CreatePipe(C.byref(output_read),C.byref(output_write),None,0):
            raise C.WinError(C.get_last_error())
        hr = api.CreatePseudoConsole(Coord(4000,40),input_read,output_write,0,C.byref(console))
        if hr:
            raise OSError('Windows could not open the worker sign-in terminal.')
        size = C.c_size_t()
        api.InitializeProcThreadAttributeList(None,1,0,C.byref(size))
        attributes = C.create_string_buffer(size.value)
        if not api.InitializeProcThreadAttributeList(attributes,1,0,C.byref(size)):
            raise C.WinError(C.get_last_error())
        info.attributes = C.cast(attributes,C.c_void_p)
        if not api.UpdateProcThreadAttribute(attributes,0,0x20016,console,C.sizeof(console),None,None):
            raise C.WinError(C.get_last_error())
        from pathlib import Path
        launcher=[sys.executable,'-I',str(Path(__file__).with_name('worker_console.py')),spec['request_path']]
        command = C.create_unicode_buffer(subprocess.list2cmdline(launcher))
        env = C.create_unicode_buffer('\0'.join(k+'='+v for k,v in sorted(spec['env'].items()))+'\0')
        if not api.CreateProcessW(sys.executable,command,None,None,False,0x80400,env,spec['cwd'],C.byref(info),C.byref(process)):
            raise C.WinError(C.get_last_error())
        api.CloseHandle(input_read); input_read=W.HANDLE()
        api.CloseHandle(output_write); output_write=W.HANDLE()
        def read():
            buffer = C.create_string_buffer(8192); received=W.DWORD()
            while api.ReadFile(output_read,buffer,len(buffer),C.byref(received),None) and received.value:
                sys.stdout.buffer.write(buffer.raw[:received.value]); sys.stdout.buffer.flush()
        def write():
            written=W.DWORD()
            while True:
                value=os.read(sys.stdin.fileno(),8192)
                if not value or not api.WriteFile(input_write,value,len(value),C.byref(written),None):
                    return
        reader=threading.Thread(target=read,daemon=True); reader.start()
        threading.Thread(target=write,daemon=True).start()
        api.WaitForSingleObject(process.process,0xFFFFFFFF)
        code=W.DWORD()
        if not api.GetExitCodeProcess(process.process,C.byref(code)):
            raise C.WinError(C.get_last_error())
        api.ClosePseudoConsole(console);console=W.HANDLE()
        reader.join(3)
        return code.value
    finally:
        if console: api.ClosePseudoConsole(console)
        if attributes: api.DeleteProcThreadAttributeList(attributes)
        for handle in (input_read,input_write,output_read,output_write,process.process,process.thread):
            if handle: api.CloseHandle(handle)
