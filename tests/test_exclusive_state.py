"""Exercise OS locks with independent processes, not mocks of lock ownership."""
import errno
import json
import os
from pathlib import Path
import subprocess
import sys
import threading

import pytest

from armada import capabilities, realmformat, runner, scheduler, sysjobs, util

_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def _spawn(code, *args):
    return subprocess.Popen([sys.executable, "-c", code, *map(str, args)],
        cwd=Path(__file__).resolve().parents[1], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", creationflags=_NO_WINDOW)


def _stop(processes):
    for proc in processes:
        if proc.poll() is None:
            proc.kill()
        proc.communicate(timeout=10)


def test_independent_process_increments_preserve_every_update(tmp_path):
    target, start = tmp_path / "counter.json", tmp_path / "start"
    code = """
import sys, time
from pathlib import Path
from armada.util import mutate_json
target, start = map(Path, sys.argv[1:])
print('ready', flush=True)
while not start.exists(): time.sleep(.005)
for i in range(30):
    mutate_json(target, lambda d: d.update(count=d.get('count', 0)+1), default=dict, timeout=15)
"""
    processes = [_spawn(code, target, start) for _ in range(4)]
    try:
        for proc in processes:
            assert proc.stdout.readline().strip() == "ready"
        start.touch()
        for proc in processes:
            out, err = proc.communicate(timeout=30)
            assert proc.returncode == 0, err
        assert util.read_json_state(target) == {"count": 120}
    finally:
        _stop(processes)


def test_contention_times_out_and_crashed_owner_is_released(tmp_path):
    target = tmp_path / "state.json"
    code = """
import sys, time
from armada.util import file_lock
with file_lock(sys.argv[1]):
    print('locked', flush=True)
    time.sleep(60)
"""
    proc = _spawn(code, target)
    try:
        assert proc.stdout.readline().strip() == "locked"
        with pytest.raises(util.FileLockTimeout):
            with util.file_lock(target, timeout=.1, poll=.01):
                pytest.fail("contended writer entered critical section")
        proc.kill()
        proc.communicate(timeout=10)
        with util.file_lock(target, timeout=.5):
            target.write_text('{"recovered":true}', encoding="utf-8")
        assert util.read_json_state(target)["recovered"]
        assert target.with_name("." + target.name + ".lock").exists(), "stable lock inode must survive release"
    finally:
        _stop([proc])


def test_same_process_threads_are_exclusive(tmp_path):
    target, blocked = tmp_path / "state.json", []
    def contender():
        try:
            with util.file_lock(target, timeout=.05, poll=.005):
                blocked.append(False)
        except util.FileLockTimeout:
            blocked.append(True)
    with util.file_lock(target):
        worker = threading.Thread(target=contender)
        worker.start()
        worker.join(timeout=2)
        assert not worker.is_alive()
    assert blocked == [True]


@pytest.mark.parametrize("failure", [PermissionError(errno.EACCES, "denied"), OSError(errno.EIO, "disk failure")])
def test_open_error_never_enters_critical_section(tmp_path, monkeypatch, failure):
    def deny(*a, **kw):
        raise failure
    monkeypatch.setattr(util.os, "open", deny)
    with pytest.raises(OSError):
        with util.file_lock(tmp_path / "state.json", timeout=0):
            pytest.fail("failed lock entered critical section")


def test_legacy_or_interrupted_lock_is_never_stolen(tmp_path):
    target = tmp_path / "state.json"
    lock = Path(str(target) + ".lock")
    lock.write_bytes(b"")
    with pytest.raises(util.StateError, match="Legacy lock"):
        with util.file_lock(target, timeout=.01, poll=.001):
            pytest.fail("legacy lock was stolen")
    assert lock.read_bytes() == b""


def test_interrupted_lock_initialization_is_not_silently_replaced(tmp_path):
    target = tmp_path / "state.json"
    lock = target.with_name("." + target.name + ".lock")
    lock.write_bytes(b"")
    with pytest.raises(util.StateError, match="Unrecognized lock"):
        with util.file_lock(target, timeout=.01, poll=.001):
            pytest.fail("uninitialized lock was stolen")
    assert lock.read_bytes() == b""


def test_waiter_leaves_empty_lock_available_for_its_creator(tmp_path, monkeypatch):
    target = tmp_path / "fresh.json"
    lock = target.with_name("." + target.name + ".lock")
    fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    released, reacquired, published = threading.Event(), threading.Event(), threading.Event()
    original = util._os_lock
    outcomes = []
    def observed(other_fd, *, release=False):
        original(other_fd, release=release)
        if other_fd != fd:
            if release:
                released.set()
            elif released.is_set() and not published.is_set():
                reacquired.set()
    monkeypatch.setattr(util, "_os_lock", observed)
    def waiter():
        try:
            with util.file_lock(target, timeout=2, poll=.001):
                outcomes.append("entered")
        except Exception as exc:
            outcomes.append(exc)
    worker = threading.Thread(target=waiter)
    worker.start()
    try:
        assert released.wait(2)
        assert not reacquired.wait(.05), "waiters must not compete with initialization"
        original(fd)
        os.write(fd, util._LOCK_MAGIC)
        os.fsync(fd)
        published.set()
        original(fd, release=True)
        worker.join(2)
        assert outcomes == ["entered"]
    finally:
        os.close(fd)
        worker.join(3)


@pytest.mark.parametrize("raw", ['{', '[]', '{"x":1,"x":2}', '{"schema_version":99}',
    '{"schema_version":true}', '{"schema_version":"unknown"}'])
def test_bad_or_future_state_is_preserved_without_calling_mutator(tmp_path, raw):
    path = tmp_path / "agent.json"
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(util.StateError):
        util.mutate_json(path, lambda data: pytest.fail("invalid state reached mutation"), default=dict)
    assert path.read_text(encoding="utf-8") == raw


def test_atomic_shared_writer_cannot_overwrite_invalid_state(tmp_path):
    path = tmp_path / "realm.json"
    path.write_text('{"broken"', encoding="utf-8")
    with pytest.raises(util.StateError):
        util.write_json_atomic(path, {})
    assert path.read_text(encoding="utf-8") == '{"broken"'


def test_mutator_failure_preserves_original(tmp_path):
    path = tmp_path / "state.json"
    path.write_text('{"count":3}', encoding="utf-8")
    def fail(data):
        data["count"] = 4
        raise RuntimeError("interrupted")
    with pytest.raises(RuntimeError):
        util.mutate_json(path, fail)
    assert path.read_text(encoding="utf-8") == '{"count":3}'
    util.mutate_json(path, lambda data: data.update(count=5))
    assert util.read_json_state(path)["count"] == 5


def test_job_completion_preserves_a_switch_changed_during_execution(tmp_path, monkeypatch):
    root = tmp_path / "realm"
    root.mkdir()
    (root / "realm.json").write_text('{}', encoding="utf-8")
    jid = "prune-history"
    def run(realm):
        assert sysjobs.set_enabled(realm, jid, False)["ok"]
        return {"ok": True}
    monkeypatch.setitem(sysjobs._BY_ID[jid], "run", run)
    assert sysjobs.run_one(root, jid)["ok"]
    state = sysjobs.state(root)[jid]
    assert state["enabled"] is False and state["status"] == "ok" and len(state["runs"]) == 1


def test_corrupt_system_state_does_not_launch_job_or_get_rewritten(tmp_path, monkeypatch):
    (tmp_path / "realm.json").write_text('{}', encoding="utf-8")
    path = tmp_path / "system_jobs.json"
    path.write_text('{', encoding="utf-8")
    monkeypatch.setitem(sysjobs._BY_ID["prune-history"], "run", lambda *a: pytest.fail("bad state launched job"))
    assert not sysjobs.run_one(tmp_path, "prune-history")["ok"]
    assert not sysjobs.set_enabled(tmp_path, "prune-history", False)["ok"]
    assert path.read_text(encoding="utf-8") == '{'


def test_future_realm_cannot_launch_an_agent_or_scheduler(tmp_path, monkeypatch):
    (tmp_path / "realm.json").write_text('{"schema_version":99}', encoding="utf-8")
    monkeypatch.setattr(runner, "get_engine", lambda *a: pytest.fail("future realm launched engine"))
    with pytest.raises(util.UnsupportedSchemaError):
        runner.chat(tmp_path, "dev", "main", "test", allow_tools=True)
    result = scheduler.tick(tmp_path)
    assert result[0]["job"] == "schema-hold" and result[0]["status"] == "held"
    assert not (tmp_path / "agents").exists()


def test_future_realm_blocks_mutation_of_other_files(tmp_path):
    (tmp_path / "realm.json").write_text('{"schema_version":99}', encoding="utf-8")
    path = tmp_path / "agents" / "dev" / "agent.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"id":"dev"}', encoding="utf-8")
    with pytest.raises(util.UnsupportedSchemaError):
        util.mutate_json(path, lambda data: data.update(display="changed"))
    assert path.read_text(encoding="utf-8") == '{"id":"dev"}'


def test_invalid_schema_is_not_migrated_to_defaults(tmp_path):
    path = tmp_path / "realm.json"
    path.write_text('{"schema_version":"unknown"}', encoding="utf-8")
    assert not realmformat.migrate(tmp_path)["ok"]
    assert path.read_text(encoding="utf-8") == '{"schema_version":"unknown"}'


def test_future_realm_browses_but_http_changes_are_refused(tmp_path):
    import http.client
    from armada.request_context import RealmContext
    from tests.golden_support import build_fixture, ServedRealm
    root = Path(build_fixture(tmp_path / "realm"))
    config = util.read_json_state(root / "realm.json")
    config["schema_version"] = 99
    raw = json.dumps(config)
    (root / "realm.json").write_text(raw, encoding="utf-8")
    with ServedRealm(str(root)) as server:
        conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
        try:
            conn.request("GET", "/agent/captain/threads", headers=server.auth_headers())
            response = conn.getresponse()
            assert response.status == 200
            response.read()
            conn.request("POST", "/api/save-agent", json.dumps({"agent":"captain", "display":"changed"}),
                         {**server.auth_headers(), "Content-Type":"application/json", "X-Armada-Realm": RealmContext.capture(root).realm_id})
            response = conn.getresponse()
            assert response.status == 409
            assert "read-only" in json.loads(response.read())["error"]
        finally:
            conn.close()
    assert (root / "realm.json").read_text(encoding="utf-8") == raw
    assert util.read_json_state(root / "agents" / "captain" / "agent.json")["display"] != "changed"


def test_thread_metadata_actions_preserve_invalid_input(tmp_path):
    from armada.serve import Handler
    root = tmp_path / "realm"
    adir = root / "agents" / "dev" / "threads"
    adir.mkdir(parents=True)
    (root / "realm.json").write_text('{}', encoding="utf-8")
    path = adir / "meta.json"
    path.write_text('{"titles": []}', encoding="utf-8")
    handler = object.__new__(Handler)
    handler.realm = str(root)
    with pytest.raises(util.StateError):
        handler._thread_action({"agent":"dev", "action":"rename", "thread":"main", "title":"new"})
    assert path.read_text(encoding="utf-8") == '{"titles": []}'


def test_grant_writer_preserves_corrupt_agent_config(tmp_path):
    adir = tmp_path / "agents" / "dev"
    adir.mkdir(parents=True)
    (tmp_path / "realm.json").write_text('{"toolkit":{"extensions":[{"id":"fs"}]}}', encoding="utf-8")
    (adir / "agent.json").write_text('{', encoding="utf-8")
    with pytest.raises(util.StateError):
        capabilities.grant(tmp_path, "dev", "fs")
    assert (adir / "agent.json").read_text(encoding="utf-8") == '{'
