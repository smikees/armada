"""Exercise the native restart boundary, not just the argv passed to a mock."""
import json
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from armada import desktop_launch
from armada.background import process_options

ROOT = Path(__file__).resolve().parents[1]


def run_restart(code, arguments, marker):
    result = subprocess.run([sys.executable, '-c', code, *map(str, arguments)],
                            cwd=ROOT, capture_output=True, text=True, timeout=20,
                            **process_options())
    assert result.returncode == 0, result.stderr
    # Windows _execv overlays by launching a successor; the original process can
    # finish before that successor writes its receipt.
    deadline = time.monotonic() + 15
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(.05)
    assert marker.exists(), result.stderr
    return json.loads(marker.read_text(encoding='utf-8'))


@pytest.fixture
def install(tmp_path):
    root = tmp_path / "Owner's ARMADA install"
    root.mkdir()
    marker = root / 'restart receipt.json'
    bootstrap = root / 'armada_bootstrap.py'
    bootstrap.write_text(
        'import json, sys\nfrom pathlib import Path\n'
        f'Path({str(marker)!r}).write_text(json.dumps(sys.argv[1:]), encoding="utf-8")\n',
        encoding='utf-8')
    return root, marker, bootstrap


@pytest.mark.parametrize('mode', ['app', 'scheduler'])
def test_real_restart_preserves_install_and_realm_paths(install, mode):
    root, marker, bootstrap = install
    realm = root / "Realms / Laura's projects / Călătorii"
    args = [mode, str(realm), '--port', '8876'] if mode == 'app' else [mode, str(realm)]
    code = '''
import sys
from pathlib import Path
from types import SimpleNamespace
from armada import serve, updater
updater.ROOT = Path(sys.argv[1])
updater.installed = lambda: True
args = sys.argv[2:]
sys.argv = ['armada', *args]
if args[0] == 'app':
    serve._content_httpd = None
    handler = SimpleNamespace(realm=args[1], server=SimpleNamespace(
        socket=SimpleNamespace(close=lambda: None), server_address=('127.0.0.1', 8876)))
    serve.Handler._restart(handler)
else:
    updater.reexec()
'''
    assert run_restart(code, [root, *args], marker) == args


def test_native_replacement_preserves_empty_quotes_unicode_and_backslashes(install):
    _, marker, bootstrap = install
    args = ['', 'two words', '"quoted value"', "owner's realm", '日本語 călătorii',
            'C:\\a b\\', 'backslash\\"quote', 'plain']
    code = '''
import sys
from armada.desktop_launch import replace_process
replace_process(sys.executable, [sys.executable, *sys.argv[1:]])
'''
    assert run_restart(code, [bootstrap, *args], marker) == args


def test_posix_replacement_leaves_raw_arguments(monkeypatch):
    execv = Mock()
    monkeypatch.setattr(desktop_launch, 'os', SimpleNamespace(name='posix', execv=execv))
    argv = ['/a b/python', '/a b/bootstrap.py', '', '"quoted"']
    desktop_launch.replace_process(argv[0], argv)
    execv.assert_called_once_with(argv[0], argv)
