"""Private runtime staging with held Windows handles, never path-based ACL grants.

The worker controls its profile and can redirect paths. Create inputs with an
owner-only descriptor, verify the opened object, and hold it against replacement
until inputs are complete and execution grants the worker access.
"""
import ctypes as C
from ctypes import wintypes as W
import os
from pathlib import Path
import secrets


def _api():
    kernel=C.WinDLL('kernel32',use_last_error=True)
    adv=C.WinDLL('advapi32',use_last_error=True)
    kernel.CreateDirectoryW.argtypes=[W.LPCWSTR,C.c_void_p]
    kernel.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,C.c_void_p,W.DWORD,W.DWORD,W.HANDLE]
    kernel.CreateFileW.restype=W.HANDLE
    kernel.GetFinalPathNameByHandleW.argtypes=[W.HANDLE,W.LPWSTR,W.DWORD,W.DWORD]
    kernel.GetFileInformationByHandleEx.argtypes=[W.HANDLE,C.c_int,C.c_void_p,W.DWORD]
    kernel.CloseHandle.argtypes=[W.HANDLE]
    kernel.LocalFree.argtypes=[C.c_void_p]
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes=[W.LPCWSTR,W.DWORD,C.POINTER(C.c_void_p),C.c_void_p]
    adv.ConvertStringSidToSidW.argtypes=[W.LPCWSTR,C.POINTER(C.c_void_p)]
    adv.GetSecurityInfo.argtypes=[W.HANDLE,C.c_int,W.DWORD,C.POINTER(C.c_void_p),C.c_void_p,C.POINTER(C.c_void_p),C.c_void_p,C.POINTER(C.c_void_p)]
    adv.GetSecurityInfo.restype=W.DWORD
    adv.GetSecurityDescriptorControl.argtypes=[C.c_void_p,C.POINTER(W.WORD),C.POINTER(W.DWORD)]
    adv.EqualSid.argtypes=[C.c_void_p,C.c_void_p]
    adv.GetAce.argtypes=[C.c_void_p,W.DWORD,C.POINTER(C.c_void_p)]
    adv.SetEntriesInAclW.argtypes=[W.ULONG,C.c_void_p,C.c_void_p,C.POINTER(C.c_void_p)]
    adv.SetEntriesInAclW.restype=W.DWORD
    adv.SetSecurityInfo.argtypes=[W.HANDLE,C.c_int,W.DWORD,C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p]
    adv.SetSecurityInfo.restype=W.DWORD
    return kernel,adv


def _same_path(left,right):
    return os.path.normcase(str(left).removeprefix('\\\\?\\')) == os.path.normcase(str(right).removeprefix('\\\\?\\'))


class RuntimeFolder:
    """Owner-private staging, then worker Modify access through the same held object."""
    def __init__(self,value,*,prefix='armada-',suffix='',dir=None):
        base=Path(value['home'])/'AppData/Local/Temp'
        if dir is not None and not _same_path(dir,base) or not prefix.startswith('armada-'):
            raise OSError('Worker runtime folders must stay in the dedicated temporary directory.')
        self.name=str(base/(prefix+secrets.token_hex(16)+suffix))
        self.sid=value['sid']
        self.handle=None
        self.parents=[]
        self.ready=False
        kernel,adv=_api()
        try:
            for parent in (Path(value['home']),Path(value['home'])/'AppData',base.parent,base):
                self.parents.append(self._open_guard(parent,0x20081))
        except BaseException:
            self.release()
            raise
        descriptor=C.c_void_p()
        sddl=f'O:{value["owner_sid"]}D:P(A;OICI;FA;;;{value["owner_sid"]})(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)'
        if not adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl,1,C.byref(descriptor),None):
            self.release()
            raise C.WinError(C.get_last_error())
        class SecurityAttributes(C.Structure):
            _fields_=[('size',W.DWORD),('descriptor',C.c_void_p),('inherit',W.BOOL)]
        attributes=SecurityAttributes(C.sizeof(SecurityAttributes),descriptor,False)
        try:
            if not kernel.CreateDirectoryW(self.name,C.byref(attributes)):
                raise C.WinError(C.get_last_error())
        except BaseException:
            self.release()
            raise
        finally:
            kernel.LocalFree(descriptor)
        # No FILE_SHARE_DELETE: neither this object nor its live input tree may be
        # replaced while the host stages data. OPEN_REPARSE_POINT opens a link itself.
        try:
            self.handle=self._open_guard(self.name,0x60081)
            self._verify_private(value['owner_sid'])
        except BaseException:
            self.release()
            raise

    def _open_guard(self,path,access):
        kernel,_=_api()
        handle=kernel.CreateFileW(str(path),access,3,None,3,0x02200000,None)
        if handle == C.c_void_p(-1).value:raise C.WinError(C.get_last_error())
        actual=C.create_unicode_buffer(32768)
        info=(W.DWORD*2)()
        if (not kernel.GetFinalPathNameByHandleW(handle,actual,len(actual),0) or not _same_path(actual.value,path)
                or not kernel.GetFileInformationByHandleEx(handle,9,C.byref(info),C.sizeof(info)) or info[0]&0x400):
            kernel.CloseHandle(handle)
            raise OSError('Refusing a redirected worker runtime folder.')
        return handle

    def _verify_private(self,owner_sid):
        kernel,adv=_api()
        actual=C.create_unicode_buffer(32768)
        if not kernel.GetFinalPathNameByHandleW(self.handle,actual,len(actual),0) or not _same_path(actual.value,self.name):
            raise OSError('Refusing a redirected worker runtime folder.')
        descriptor,owner,acl=C.c_void_p(),C.c_void_p(),C.c_void_p()
        error=adv.GetSecurityInfo(self.handle,1,5,C.byref(owner),None,C.byref(acl),None,C.byref(descriptor))
        if error:raise C.WinError(error)
        identifiers=[]
        try:
            for sid in (owner_sid,'S-1-5-18','S-1-5-32-544'):
                ptr=C.c_void_p()
                if not adv.ConvertStringSidToSidW(sid,C.byref(ptr)):raise C.WinError(C.get_last_error())
                identifiers.append(ptr)
            control,revision=W.WORD(),W.DWORD()
            if not adv.GetSecurityDescriptorControl(descriptor,C.byref(control),C.byref(revision)) or not control.value&0x1000 or not adv.EqualSid(owner,identifiers[0]):
                raise OSError('Worker staging ownership changed before it could be secured.')
            class ACL(C.Structure):
                _fields_=[('revision',C.c_ubyte),('unused',C.c_ubyte),('size',W.WORD),('count',W.WORD),('unused2',W.WORD)]
            if not acl.value or C.cast(acl,C.POINTER(ACL)).contents.count != 3:
                raise OSError('Worker staging permissions are not private.')
            seen=set()
            for index in range(3):
                ace=C.c_void_p()
                if not adv.GetAce(acl,index,C.byref(ace)):raise C.WinError(C.get_last_error())
                header=C.string_at(ace,4)
                mask=C.c_ulong.from_address(ace.value+4).value
                trustee=next((i for i,sid in enumerate(identifiers) if adv.EqualSid(ace.value+8,sid)),None)
                if header[0] != 0 or header[1] != 3 or mask != 0x1F01FF or trustee is None or trustee in seen:
                    raise OSError('Worker staging permissions changed before inputs were written.')
                seen.add(trustee)
            if any(Path(self.name).iterdir()):
                raise OSError('Worker staging must be empty before inputs are written.')
        finally:
            for ptr in identifiers:kernel.LocalFree(ptr)
            kernel.LocalFree(descriptor)

    def grant(self,sid):
        if sid != self.sid or self.handle is None:
            raise OSError('Invalid worker runtime grant.')
        if self.ready:return
        kernel,adv=_api()
        descriptor,old_acl,new_acl,identifier=C.c_void_p(),C.c_void_p(),C.c_void_p(),C.c_void_p()
        class Trustee(C.Structure):
            _fields_=[('multiple',C.c_void_p),('operation',C.c_int),('form',C.c_int),('type',C.c_int),('name',C.c_void_p)]
        class Access(C.Structure):
            _fields_=[('permissions',W.DWORD),('mode',C.c_int),('inheritance',W.DWORD),('trustee',Trustee)]
        try:
            error=adv.GetSecurityInfo(self.handle,1,4,None,None,C.byref(old_acl),None,C.byref(descriptor))
            if error:raise C.WinError(error)
            if not adv.ConvertStringSidToSidW(sid,C.byref(identifier)):raise C.WinError(C.get_last_error())
            access=Access(0x1301BF,1,3,Trustee(None,0,0,1,identifier))
            error=adv.SetEntriesInAclW(1,C.byref(access),old_acl,C.byref(new_acl))
            if error:raise C.WinError(error)
            error=adv.SetSecurityInfo(self.handle,1,0x80000004,None,None,new_acl,None)
            if error:raise C.WinError(error)
            self.ready=True
        finally:
            for ptr in (identifier,new_acl,descriptor):
                if ptr:kernel.LocalFree(ptr)

    def release(self):
        if self.handle is not None:
            _api()[0].CloseHandle(self.handle)
            self.handle=None
        for handle in reversed(self.parents):
            _api()[0].CloseHandle(handle)
        self.parents=[]

    def cleanup(self):
        from . import worker
        worker.clean_temporary(self.name)

