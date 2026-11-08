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


def test_duplicate_waits_for_locked_owner_to_publish(tmp_path, monkeypatch):
    # Hold the primary between acquiring the lock and writing its owner record.
    original_code = CODE
    primary_code = original_code.replace('with instance.claim', """
def delayed_legacy():
    print('locked',flush=True)
    sys.stdin.readline()
    return {}
instance._legacy=delayed_legacy
with instance.claim""")
    monkeypatch.setattr(sys.modules[__name__], 'CODE', primary_code)
    owner = launch(tmp_path)
    other = None
    try:
        assert owner.stdout.readline().strip() == 'locked'
        duplicate_code = primary_code[:primary_code.index('def delayed_legacy')] + """
original_current=instance.current
def observed_current():
    result=original_current()
    if not result: print('owner-not-published',flush=True)
    return result
instance.current=observed_current
""" + original_code[original_code.index('with instance.claim'):]
        monkeypatch.setattr(sys.modules[__name__], 'CODE', duplicate_code)
        other = launch(tmp_path)
        assert other.stdout.readline().strip() == 'owner-not-published'
        owner.stdin.write('\n'); owner.stdin.flush()
        assert owner.stdout.readline().strip() == 'primary'
        out, err = other.communicate(timeout=15)
        assert other.returncode == 0, err
        assert out.splitlines()[-1] == 'existing'
    finally:
        if other is not None and other.poll() is None:
            other.kill(); other.communicate(timeout=10)
        owner.communicate('\n\n', timeout=10)


def test_unpublished_owner_wait_is_bounded(monkeypatch):
    monkeypatch.setattr(instance, 'current', lambda: {})
    clock = iter([0.0, 11.0])
    monkeypatch.setattr(instance.time, 'monotonic', lambda: next(clock))
    with pytest.raises(instance.ActivationError, match='details are not ready'):
        instance._wait_for_owner()


def test_duplicate_with_different_data_directory_and_port_restores_owner(tmp_path):
    """A separate launch folder/profile cannot select a different account lock."""
    code = '''
import sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from armada import instance,util
instance._account_directory=lambda:Path(sys.argv[2])
util.data_dir=lambda:Path(sys.argv[3])
with instance.claim('app',int(sys.argv[4])) as primary:
    print('primary' if primary else 'existing',flush=True)
    if primary: sys.stdin.readline()
'''
    account = tmp_path/'account'
    profiles = [tmp_path/'installation-a', tmp_path/'installation-b']
    for profile in profiles:
        profile.mkdir()
    def start(profile, port):
        return subprocess.Popen([getattr(sys, '_base_executable', sys.executable), '-c', code,
            str(ROOT), str(account), str(profile), str(port)], cwd=profile,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, **process_options())
    owner = start(profiles[0], 8756)
    try:
        assert owner.stdout.readline().strip() == 'primary'
        before = json.loads((account/'desktop-instance.json').read_text())
        other = start(profiles[1], 8890)
        try:
            out, err = other.communicate(timeout=10)
            assert other.returncode == 0, err
            assert out.strip() == 'existing'
            assert json.loads((account/'desktop-instance.json').read_text()) == before
            activation = json.loads((account/'desktop-activate.json').read_text())
            assert activation['nonce'] == before['nonce'] and activation['role'] == 'app'
            assert not (profiles[1]/'desktop-instance.json').exists()
        finally:
            if other.poll() is None:
                other.kill()
                other.communicate(timeout=5)
    finally:
        owner.communicate('\n', timeout=10)


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
