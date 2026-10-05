"""Exercise abrupt update recovery through the compiled Windows launcher and bundled Python."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


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
