"""Exercise abrupt update recovery through the compiled Windows launcher and bundled Python."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def launcher_isolation(stage):
    """An actual external child must not inherit the packaged DLL directory."""
    from armada.background import process_options
    stage = Path(stage).resolve()
    csc = Path(os.environ['SystemRoot'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    with tempfile.TemporaryDirectory(prefix='armada-loader-probe-') as scratch:
        root = Path(scratch)
        source = root/'Child.cs'
        child = root/'Child.exe'
        report = root/'child.txt'
        source.write_text('''using System; using System.IO; using System.Text;
using System.Runtime.InteropServices;
class Child {
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode)] static extern uint GetDllDirectory(uint n,StringBuilder s);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode)] static extern IntPtr LoadLibrary(string s);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode)] static extern uint GetModuleFileName(IntPtr h,StringBuilder s,uint n);
 static void Main(string[] a) {
  var directory=new StringBuilder(32768); GetDllDirectory(32768,directory);
  var library=new StringBuilder(32768); var h=LoadLibrary("vcruntime140.dll");
  if(h!=IntPtr.Zero) GetModuleFileName(h,library,32768);
  File.WriteAllLines(a[0],new string[]{directory.ToString(),library.ToString()});
 }
}''', encoding='utf-8')
        subprocess.run([str(csc),'/nologo','/target:winexe','/platform:x64',
            '/out:'+str(child),str(source)],check=True,timeout=30,**process_options())
        host = stage/'python/ARMADA.exe'
        code = ('import ctypes,subprocess; b=ctypes.create_unicode_buffer(32768); '
                'ctypes.windll.kernel32.GetDllDirectoryW(32768,b); assert not b.value; '
                'import ssl,sqlite3,webview; '
                + 'subprocess.run('+repr([str(child),str(report)])+',check=True,timeout=20)')
        # Reproduce startup under a legacy parent as well as a clean parent.
        for inherited in (False, True):
            command = [str(host),'-c',code]
            if inherited:
                parent = ('import ctypes,subprocess; '
                    + 'ctypes.windll.kernel32.SetDllDirectoryW('+repr(str(stage/'python'))+'); '
                    + 'subprocess.run('+repr(command)+',check=True,timeout=30)')
                command = [str(stage/'python/python.exe'),'-c',parent]
            subprocess.run(command,cwd=root,check=True,timeout=45,**process_options())
            lines = report.read_text(encoding='utf-8-sig').splitlines()
            if lines[0] or (len(lines)>1 and lines[1].lower().startswith(str(stage).lower())):
                raise RuntimeError('External child inherited the private runtime DLL search path')
    print('Native launcher: external DLL isolation passed with clean and legacy parents',flush=True)


def recovery(stage):
    stage = Path(stage)
    if list(stage.rglob('support_key.txt')):
        raise RuntimeError('Installer contains a client mail credential')
    with tempfile.TemporaryDirectory(prefix='armada-native-recovery-') as scratch:
        root = Path(scratch)
        shutil.copytree(stage/'python',root/'python')
        shutil.copy2(stage/'armada_bootstrap.py',root/'armada_bootstrap.py')
        (root/'installed.json').write_text('{}')
        host = root/'python/ARMADA.exe'
        env = {**os.environ,'USERPROFILE':str(root/'home'),'HOME':str(root/'home'),
               'ARMADA_NO_EXTERNAL_NOTIFY':'1'}
        for point in ('prepared','live_moved','old_moved','stage_moved','new_live'):
            for name in ('armada','armada.staged','armada.previous'):
                folder=root/name
                if folder.resolve().parent != root.resolve(): raise RuntimeError('Probe cleanup escaped its temporary root')
                if folder.exists():shutil.rmtree(folder)
            # Fixture setup itself uses the bundled runtime, not a developer Python.
            prepare='''
from pathlib import Path
import armada_bootstrap as b
root=Path.cwd()
for name,v in [('armada','1.0.0'),('armada.staged','1.1.0')]:
 p=root/name;p.mkdir()
 (p/'__init__.py').write_text('__version__ = "'+v+'"\\n')
 (p/'__main__.py').write_text('from armada import __version__\\nfrom pathlib import Path\\nimport armada_bootstrap as b\\nb.confirm_health(Path.cwd(),__version__)\\nPath("proof.txt").write_text(__version__)\\n')
b.atomic_json(root/'armada.staged/.staged.json',{'version':'1.1.0','files':b.inventory(root/'armada.staged')})
'''
            subprocess.run([str(host),'-c',prepare],cwd=root,env=env,check=True,timeout=30)
            crash='''
from pathlib import Path
import os,sys
import armada_bootstrap as b
record,move=b.atomic_json,b.replace
point=sys.argv[1]
def write(path,data):
 record(path,data)
 if data.get('phase')==point:os._exit(77)
def rename(source,target):
 move(source,target)
 if (point=='live_moved' and source.name=='armada') or (point=='stage_moved' and source.name=='armada.staged'):os._exit(77)
b.atomic_json=write;b.replace=rename
b.apply(Path.cwd())
'''
            result=subprocess.run([str(host),'-c',crash,point],cwd=root,env=env,timeout=30)
            if result.returncode!=77:raise RuntimeError('Native crash injection failed at '+point)
            (root/'proof.txt').unlink(missing_ok=True)
            subprocess.run([str(host),'-m','armada','app'],cwd=root,env=env,check=True,timeout=30)
            if (root/'proof.txt').read_text()!='1.1.0':raise RuntimeError('Native recovery failed at '+point)
            if (root/'.armada-update.json').exists():raise RuntimeError('Recovery left an incomplete journal')
    print('Native launcher: recovery passed at all five interruption points',flush=True)
