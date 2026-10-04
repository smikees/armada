"""Run the same pinned, isolated test gate locally and on Windows CI before releasing."""
import importlib.metadata
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def verify_dependencies():
    for line in (ROOT/'requirements-dev.txt').read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'): continue
        name, expected = line.strip().split('==',1)
        try: actual = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: actual = 'missing'
        if actual != expected:
            raise SystemExit(f'{name} must be {expected}, got {actual}. Install requirements-dev.txt first.')


def run():
    verify_dependencies()
    with tempfile.TemporaryDirectory(prefix='armada-release-tests-') as directory:
        home = Path(directory)
        env = dict(os.environ)
        for name in ('HOME','USERPROFILE'): env[name] = str(home)
        env['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
        env['ARMADA_NO_EXTERNAL_NOTIFY'] = '1'
        env.pop('ARMADA_TEST_REALM',None)
        subprocess.run([sys.executable,'-m','pytest','-o','addopts=','-q',
                        '-W','error::pytest.PytestUnhandledThreadExceptionWarning',
                        '--basetemp',str(home/'tests')],cwd=ROOT,env=env,check=True)


if __name__ == '__main__': run()
