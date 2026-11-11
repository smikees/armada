"""Real Windows account/access and descendant-cleanup proof. No provider calls or real keys.

Requires --setup to create the dedicated synthetic account through the normal UAC flow.
The fixture is reusable; its launch credential stays DPAPI-protected outside the realm.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixture', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--setup', action='store_true')
    parser.add_argument('--controller', help='Owner-protected copy of the public Armada package')
    parser.add_argument('--data', help='Owner-protected synthetic control folder')
    parser.add_argument('--lpac',action='store_true',help='Also verify approved draft scripts on the private desktop')
    args = parser.parse_args()
    fixture = Path(args.fixture).resolve()
    fixture.mkdir(parents=True, exist_ok=True)
    if args.controller:
        sys.path.insert(0,str(Path(args.controller).resolve()))
    data, workspace = Path(args.data).resolve() if args.data else fixture/'owner', fixture/'workspace'
    workspace.mkdir(exist_ok=True)
    os.environ['ARMADA_DATA_DIR'] = str(data)
    from armada import worker, util
    if args.setup:
        worker.setup([str(workspace)])
        for attempt in range(300):
            state = worker.status()
            if not state['pending']:
                break
            time.sleep(1)
        if not state['ready']:
            print(json.dumps(state))
            return 1
    proof = worker.verify()
    value = worker.require()
    # A redirected temporary-folder grant must be rejected before it reaches a
    # fixed task/helper. No trusted file content or permission is changed.
    try:
        worker._acl(value['root'],value['sid'],'M')
        proof['redirected_grant_denied']=False
    except OSError:
        proof['redirected_grant_denied']=True
    proof['passed']=proof['passed'] and proof['redirected_grant_denied']
    with worker.temporary_directory(prefix='armada-staging-proof-') as directory:
        staged=Path(directory)/'input.txt'
        staged.write_text('synthetic staging input',encoding='utf-8')
        script='''import os,pathlib,json,sys
p=pathlib.Path(sys.argv[1]);read=False;renamed=False;parent_renamed=False
try:p.read_text();read=True
except OSError:pass
for source,label in ((p.parent,'root'),(p.parent.parent,'parent')):
 try:
  target=str(source)+'-rename-proof';os.rename(source,target);os.rename(target,source)
  if label=='root':renamed=True
  else:parent_renamed=True
 except OSError:pass
print(json.dumps(dict(read=read,renamed=renamed,parent_renamed=parent_renamed)))'''
        before=worker.run([value['python'],'-I','-c',script,str(staged)],cwd=str(workspace),capture_output=True,text=True,timeout=20,check=True)
        before=json.loads(before.stdout)
        worker._access(staged,value,temporary=True)
        after=worker.run([value['python'],'-I','-c',script,str(staged)],cwd=str(workspace),capture_output=True,text=True,timeout=20,check=True)
        after=json.loads(after.stdout)
        proof['staging_before']=before
        proof['staging_after']=after
        proof['staging_private_before_launch']=not before['read']
        proof['staging_readable_after_launch']=after['read']
        proof['staging_replacement_denied']=not any(row[k] for row in (before,after) for k in ('renamed','parent_renamed'))
        proof['passed']=proof['passed'] and all(proof[k] for k in ('staging_private_before_launch','staging_readable_after_launch','staging_replacement_denied'))
    from armada.engine.process import supervise_command
    marker = 'synthetic-owner-environment-secret'
    os.environ['ARMADA_TEST_OWNER_SECRET'] = marker
    result = supervise_command([value['python'], '-I', '-c',
        'import os,json,subprocess; print(json.dumps(dict(secret=os.environ.get("ARMADA_TEST_OWNER_SECRET"),'
        'home=os.environ.get("USERPROFILE"), child=subprocess.check_output(["whoami","/user","/fo","csv","/nh"],text=True).strip())))'],
        timeout=30, cwd=str(workspace))
    observed = json.loads(result.stdout)
    proof.update(owner_environment_absent=observed['secret'] is None,
                 child_is_worker=value['sid'] in observed['child'],
                 worker_profile=observed['home'] == value['home'],
                 supervised_success=result.returncode == 0 and not result.error)
    child = workspace/'child.pid'
    child.unlink(missing_ok=True)
    running = 'import subprocess,time,pathlib; p=subprocess.Popen([%r,"-I","-c","import time; time.sleep(120)"]); pathlib.Path(%r).write_text(str(p.pid)); time.sleep(120)' % (value['python'], str(child))
    proc = worker.popen([value['python'], '-I', '-c', running], cwd=str(workspace))
    try:
        deadline = time.monotonic()+20
        while not child.exists() and time.monotonic()<deadline:
            time.sleep(.05)
        if not child.exists():
            raise OSError('The worker child did not start.')
        pid = int(child.read_text())
        # Keep an OS process handle while stopping to avoid PID-reuse ambiguity.
        import ctypes as C
        from ctypes import wintypes as W
        api = C.WinDLL('kernel32',use_last_error=True)
        api.OpenProcess.argtypes, api.OpenProcess.restype = [W.DWORD,W.BOOL,W.DWORD], W.HANDLE
        api.WaitForSingleObject.argtypes = [W.HANDLE,W.DWORD]
        api.CloseHandle.argtypes = [W.HANDLE]
        handle=api.OpenProcess(0x100000,False,pid)
        if not handle:
            raise C.WinError(C.get_last_error())
        try:
            proc.kill()
            proc.wait(timeout=5)
            proof['descendant_stopped'] = api.WaitForSingleObject(handle,3000)==0
        finally:
            api.CloseHandle(handle)
    finally:
        if proc.poll() is None:
            proc.kill(); proc.wait(timeout=5)
    proof['passed'] = proof['passed'] and all(proof[k] for k in ('owner_environment_absent','child_is_worker','worker_profile','supervised_success','descendant_stopped'))
    if args.lpac:
        draft=lpac_proof(workspace,data,value)
        proof['lpac']=draft
        proof['passed']=proof['passed'] and draft['passed']
    util.write_json_atomic(Path(args.output), proof)
    print(json.dumps(proof, indent=2))
    return 0 if proof['passed'] else 1


def lpac_proof(workspace,data,value):
    import base64
    from armada import provider_keys,draft_skills
    from armada.engine.skill_sandbox import SkillSandbox
    from armada.engine.process import supervise_command
    root=workspace/'draft-boundary';root.mkdir(exist_ok=True)
    runtime=root/'runtime';runtime.mkdir(exist_ok=True)
    exe=runtime/'python/python.exe'
    if not exe.exists():exe=draft_skills._runtime('python',runtime)
    output=root/'output';output.mkdir(exist_ok=True)
    protected=data/'synthetic-owner-secret'
    protected.write_text('synthetic owner credential proof',encoding='utf-8')
    cipher=base64.b64encode(provider_keys._crypt(b'synthetic-owner-secret')).decode()
    script='''import ctypes as C,json,pathlib,base64,os
from ctypes import wintypes as W
class B(C.Structure):
 _fields_=[('n',W.DWORD),('p',C.c_void_p)]
raw=base64.b64decode(%r);buf=C.create_string_buffer(raw);a=B(len(raw),C.cast(buf,C.c_void_p));b=B()
decrypt=bool(C.windll.crypt32.CryptUnprotectData(C.byref(a),None,None,None,None,1,C.byref(b)))
read=False
try:pathlib.Path(%r).read_bytes();read=True
except OSError:pass
u=C.WinDLL('user32');u.GetProcessWindowStation.restype=W.HANDLE;u.GetUserObjectInformationW.argtypes=[W.HANDLE,C.c_int,C.c_void_p,W.DWORD,C.c_void_p]
name=C.create_unicode_buffer(512);u.GetUserObjectInformationW(u.GetProcessWindowStation(),2,name,C.sizeof(name),None)
u.OpenWindowStationW.argtypes=[W.LPCWSTR,W.BOOL,W.DWORD];u.OpenWindowStationW.restype=W.HANDLE;h=u.OpenWindowStationW('WinSta0',False,4)
owner_station=bool(h)
if h:u.CloseWindowStation.argtypes=[W.HANDLE];u.CloseWindowStation(h)
k=C.WinDLL('kernel32');k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE;h=k.OpenProcess(0x10,False,%d);memory=bool(h)
if h:k.CloseHandle.argtypes=[W.HANDLE];k.CloseHandle(h)
print(json.dumps(dict(decrypt=decrypt,read=read,private_station=name.value==%r,owner_clipboard_station=owner_station,owner_memory=memory,api_key_in_env=bool(os.environ.get('ANTHROPIC_API_KEY')))))
''' % (cipher,str(protected),os.getpid(),value['station'])
    env={k:os.environ[k] for k in ('SystemRoot','WINDIR','USERPROFILE','LOCALAPPDATA','APPDATA') if k in os.environ}
    env.update(TEMP=str(output),TMP=str(output),PYTHONUTF8='1',PYTHONIOENCODING='utf-8')
    try:
        with SkillSandbox(readonly=[runtime],writable=output) as launch:
            result=supervise_command([str(exe),'-I','-c',script],cwd=str(output),env=env,timeout=30,launch=launch)
        proof=json.loads(result.stdout) if result.stdout else {}
        proof['passed']=not result.error and result.returncode==0 and proof.get('private_station') and not any(proof.get(k,True) for k in ('decrypt','read','owner_clipboard_station','owner_memory','api_key_in_env'))
        proof['error']=result.error
        return proof
    finally:
        protected.unlink(missing_ok=True)


if __name__ == '__main__':
    raise SystemExit(main())
