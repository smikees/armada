"""Concurrent discovery changes preserve every writer and refuse damaged input."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import threading

import pytest

from armada import realm_registry as registry, util


@pytest.fixture
def path(tmp_path, monkeypatch):
    target = tmp_path / 'registry.json'
    monkeypatch.setattr(registry, 'path', lambda: target)
    return target


@pytest.mark.parametrize('raw', [b'{broken', b'{}', b'null', b'[null]',
    b'[{"path":"relative"}]', b'[{"path":1}]', b'\xff'])
def test_corrupt_registry_is_never_replaced(path, raw):
    path.write_bytes(raw)
    with pytest.raises(util.StateError):
        registry.ensure(path.parent / 'New', 'New')
    assert path.read_bytes() == raw


def test_duplicate_identity_is_preserved_for_repair(path):
    row = {'path':str(path.parent / 'Same'), 'name':'Same'}
    path.write_text(json.dumps([row,row]))
    before = path.read_bytes()
    with pytest.raises(util.StateError): registry.rename(row['path'],'Changed')
    assert path.read_bytes() == before


def test_failed_mutation_preserves_original(path):
    registry.ensure(path.parent / 'Old','Old')
    before = path.read_bytes()
    with pytest.raises(OSError):
        with registry.edit() as records:
            records.clear()
            raise OSError('disk unavailable during dependent operation')
    assert path.read_bytes() == before


def test_concurrent_add_rename_and_remove_preserve_unrelated_entries(path):
    old, removed = path.parent / 'Old', path.parent / 'Removed'
    registry.ensure(old, 'Old'); registry.ensure(removed, 'Removed')
    start = threading.Barrier(10)
    def mutate(index):
        start.wait(timeout=5)
        if index == 0:
            registry.rename(old, 'Renamed')
        elif index == 1:
            with registry.edit() as records:
                records[:] = [r for r in records if registry.identity(r['path']) != removed]
        else:
            registry.ensure(path.parent / str(index), str(index))
    with ThreadPoolExecutor(10) as pool: list(pool.map(mutate, range(10)))
    assert {r['name'] for r in registry.load()} == {'Renamed', *map(str,range(2,10))}


def test_independent_process_adds_preserve_every_registration(path):
    gate = path.parent / 'start'
    code = '''
import sys,time
from pathlib import Path
from armada import realm_registry as r
target,gate,number=map(Path,sys.argv[1:])
r.path=lambda:target
print('ready',flush=True)
while not gate.exists():time.sleep(.005)
for i in range(15):r.ensure(target.parent / (str(number)+'-'+str(i)),str(number)+'-'+str(i))
'''
    children = [subprocess.Popen([sys.executable,'-c',code,str(path),str(gate),str(i)],
        cwd=Path(__file__).resolve().parents[1],stdout=subprocess.PIPE,stderr=subprocess.PIPE,
        text=True,creationflags=0x08000000 if os.name == 'nt' else 0) for i in range(3)]
    try:
        for child in children: assert child.stdout.readline().strip() == 'ready'
        gate.touch()
        for child in children:
            _, error = child.communicate(timeout=25)
            assert child.returncode == 0,error
        assert len(registry.load()) == 45
    finally:
        for child in children:
            if child.poll() is None: child.kill()
            child.communicate(timeout=10)


def test_failed_folder_move_does_not_restore_a_stale_registry(path, monkeypatch):
    from armada import setupfolder, appconfig, approot, activerealm
    root, dest, added = [path.parent / name for name in ('Original','Destination','Concurrent')]
    root.mkdir()
    (root / 'realm.json').write_text(json.dumps({'name':'Original',
        'setup':{'step':'folder','complete':False}}))
    (root / 'keep.txt').write_text('preserve this')
    registry.ensure(root,root.name)
    monkeypatch.setattr(setupfolder.setupflow,'needs_setup',lambda _:True)
    monkeypatch.setattr(approot,'root',lambda:str(path.parent))
    save = appconfig.save
    calls = []
    def fail_once(changes):
        calls.append(changes)
        if len(calls) == 1: raise OSError('injected config failure')
        return save(changes)
    monkeypatch.setattr(appconfig,'save',fail_once)
    rename = Path.rename
    def restore_and_register(source,target):
        result = rename(source,target)
        if source.name.startswith('.armada-moved-'):
            registry.ensure(added,'Concurrent')
        return result
    monkeypatch.setattr(Path,'rename',restore_and_register)
    result = setupfolder.relocate(root,str(dest))
    assert not result['ok']
    assert (root/'keep.txt').read_text() == 'preserve this' and not dest.exists()
    assert {r['name'] for r in registry.load()} == {'Original','Concurrent'}
