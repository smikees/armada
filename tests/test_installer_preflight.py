"""Real Windows file locks must stop Setup before it touches the old payload."""
import os
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Windows installer')
SCRIPT = Path(__file__).resolve().parents[1]/'installer/check-install-files.ps1'


def check(root, report):
    from armada.background import process_options
    return subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive',
        '-ExecutionPolicy', 'Bypass', '-File', str(SCRIPT), '-InstallRoot', str(root),
        '-Report', str(report)], capture_output=True, timeout=30, **process_options())


def test_unlocked_payload_and_new_install_pass(tmp_path):
    root=tmp_path/'install'; report=tmp_path/'report.txt'
    assert check(root,report).returncode == 0
    root.mkdir(); (root/'payload.dll').write_bytes(b'old payload')
    assert check(root,report).returncode == 0
    assert (root/'payload.dll').read_bytes() == b'old payload'


@pytest.mark.parametrize('contents', [b'expected payload', b'old skipped DLL', None])
def test_installed_payload_verification_rejects_skipped_or_missing_files(tmp_path, contents):
    from armada.background import process_options
    root=tmp_path/'install'; root.mkdir()
    if contents is not None: (root/'runtime.dll').write_bytes(contents)
    inventory=tmp_path/'expected.json'; report=tmp_path/'report.txt'
    inventory.write_text(json.dumps({'format':1,'files':[{'path':'runtime.dll',
        'sha256':hashlib.sha256(b'expected payload').hexdigest()}]}),encoding='utf-8')
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy',
        'Bypass','-File',str(SCRIPT.with_name('verify-install-files.ps1')),
        '-InstallRoot',str(root),'-Manifest',str(inventory),'-Report',str(report)],
        capture_output=True,timeout=30,**process_options())
    assert (result.returncode==0) == (contents==b'expected payload')
    if contents != b'expected payload': assert 'runtime.dll' in report.read_text(encoding='utf-8')


def test_locked_payload_refuses_and_preserves_all_files(tmp_path):
    import ctypes
    root=tmp_path/'install'; root.mkdir(); report=tmp_path/'report.txt'
    target=root/'vcruntime140.dll'; target.write_bytes(b'old runtime')
    marker=root/'installed.json'; marker.write_bytes(b'old marker')
    api=ctypes.WinDLL('kernel32',use_last_error=True)
    api.CreateFileW.argtypes=[ctypes.c_wchar_p,ctypes.c_uint,ctypes.c_uint,
        ctypes.c_void_p,ctypes.c_uint,ctypes.c_uint,ctypes.c_void_p]
    api.CreateFileW.restype=ctypes.c_void_p
    api.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=api.CreateFileW(str(target),0x80000000,1,None,3,0,None)
    assert handle != ctypes.c_void_p(-1).value
    try:
        result=check(root,report)
        assert result.returncode == 1
        assert 'vcruntime140.dll' in report.read_text(encoding='utf-8')
        assert target.read_bytes()==b'old runtime' and marker.read_bytes()==b'old marker'
    finally:
        api.CloseHandle(handle)
    assert check(root,report).returncode == 0
