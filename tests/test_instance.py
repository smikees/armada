import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from armada import instance, local_auth, serve, util
from armada.background import process_options

ROOT = Path(__file__).resolve().parents[1]
CODE = '''
import sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from armada import instance,util
util.data_dir=lambda:Path(sys.argv[2])
instance._path=lambda:Path(sys.argv[2])/'desktop-instance.json'
with instance.claim(sys.argv[3],int(sys.argv[4])) as primary:
    print('primary' if primary else 'existing',flush=True)
    if primary: sys.stdin.readline()
'''


def launch(home, role='app', port=8756):
    return subprocess.Popen([getattr(sys, '_base_executable', sys.executable), '-c', CODE,
                             str(ROOT), str(home), role, str(port)], cwd=ROOT,
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, **process_options())


def test_second_launch_reuses_owner_across_ports_and_modes(tmp_path):
    owner = launch(tmp_path)
    try:
        assert owner.stdout.readline().strip() == 'primary'
        before = json.loads((tmp_path/'desktop-instance.json').read_text())
        other = launch(tmp_path, 'serve', 8890)
        out, err = other.communicate(timeout=10)
        assert other.returncode == 0, err
        assert out.strip() == 'existing'
        assert json.loads((tmp_path/'desktop-instance.json').read_text()) == before
        assert not (tmp_path/'desktop-activate.json').exists()
    finally:
        owner.communicate('\n', timeout=10)


def test_crash_releases_account_lock(tmp_path):
    owner = launch(tmp_path)
    try:
        assert owner.stdout.readline().strip() == 'primary'
        owner.kill()
        owner.wait(timeout=10)
        replacement = launch(tmp_path)
        try:
            assert replacement.stdout.readline().strip() == 'primary'
        finally:
            replacement.communicate('\n', timeout=10)
    finally:
        if owner.poll() is None:
            owner.kill()
        owner.communicate(timeout=10)


def test_simultaneous_launches_have_one_owner(tmp_path):
    processes = [launch(tmp_path, port=8756+i*2) for i in range(3)]
    try:
        results = [p.stdout.readline().strip() for p in processes]
        assert sorted(results) == ['existing', 'existing', 'primary']
    finally:
        for p in processes:
            p.communicate('\n' if p.poll() is None else None, timeout=10)


def test_duplicate_socket_does_not_replace_live_authentication():
    first = serve._Server(('127.0.0.1', 0), serve.Handler)
    try:
        before = local_auth.headers(first.server_port)
        with pytest.raises(OSError):
            serve._Server(first.server_address, serve.Handler)
        assert local_auth.headers(first.server_port) == before
    finally:
        first.server_close()


def test_closed_server_can_rebind_without_delay():
    first = serve._Server(('127.0.0.1', 0), serve.Handler)
    address = first.server_address
    first.server_close()
    second = serve._Server(address, serve.Handler)
    second.server_close()
