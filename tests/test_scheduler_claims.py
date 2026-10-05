"""Real synchronized processes plus fault injection at the durable dispatch boundaries (2.14)."""
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import threading

import pytest

from armada import preflight, runner, scheduler, scheduler_state as state, sysjobs, util

AT = dt.datetime(2026, 9, 27, 9, 0)
DAY = AT.date().isoformat()


@pytest.fixture
def realm(tmp_path, monkeypatch):
    (tmp_path / "realm.json").write_text('{"schema_version":2}', encoding="utf-8")
    jobs = tmp_path / "agents" / "a" / "jobs"
    jobs.mkdir(parents=True)
    (jobs / "daily.json").write_text(json.dumps({"id": "daily", "schedule": "daily 09:00"}), encoding="utf-8")
    monkeypatch.setattr(preflight, "hold_reason", lambda *a: "")
    monkeypatch.setattr(sysjobs, "run_due", lambda *a: [])
    monkeypatch.setattr(runner, "run_job", lambda *a, **kw: {"status": "ok"})
    return tmp_path


def _spawn(code, *args):
    return subprocess.Popen([sys.executable, "-c", code, *map(str, args)],
        cwd=Path(__file__).resolve().parents[1], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", creationflags=0x08000000 if os.name == "nt" else 0)


def _stop(processes):
    for proc in processes:
        if proc.poll() is None:
            proc.kill()
        proc.communicate(timeout=10)


_CHILD_SETUP = """
import datetime as dt, json, sys, time
from pathlib import Path
from armada import preflight, runner, scheduler, scheduler_state as state, sysjobs
root = Path(sys.argv[1])
preflight.hold_reason = lambda *a: ''
sysjobs.run_due = lambda *a: []
at = dt.datetime(2026, 9, 27, 9, 0)
"""


def test_two_synchronized_processes_have_one_owner_and_one_dispatch(realm):
    code = _CHILD_SETUP + """
def run(*args, **kw):
    with (root / 'effects').open('a') as f: f.write('effect\\n')
    print('dispatch', flush=True)
    while not (root / 'finish').exists(): time.sleep(.005)
    return {'status': 'ok'}
runner.run_job = run
print('ready', flush=True)
while not (root / 'start').exists(): time.sleep(.005)
result = scheduler.tick(root, at=at)
print(json.dumps(result), flush=True)
"""
    procs = [_spawn(code, realm) for _ in range(2)]
    try:
        for proc in procs:
            assert proc.stdout.readline().strip() == "ready"
        (realm / "start").touch()
        first = [proc.stdout.readline().strip() for proc in procs]
        assert first.count("dispatch") == 1
        loser = json.loads(next(line for line in first if line != "dispatch"))
        assert loser[0]["job"] == "scheduler-lock" and loser[0]["status"] == "skipped"
        assert scheduler.lock_holder(realm)["owner_token"]
        (realm / "finish").touch()
        for proc in procs:
            out, err = proc.communicate(timeout=15)
            assert proc.returncode == 0, err
        assert (realm / "effects").read_text().splitlines() == ["effect"]
        entries = state._attempts(state._attempt_path(realm, DAY))["attempts"]
        assert len(entries) == 1 and next(iter(entries.values()))["state"] == "finished"
        # Runner stub deliberately wrote no completion ledger: admission alone prevents replay.
        assert scheduler.tick(realm, at=AT) == []
    finally:
        _stop(procs)


@pytest.mark.parametrize("after_effect", [False, True])
def test_killed_owner_releases_lease_but_never_replays_uncertain_attempt(realm, monkeypatch, after_effect):
    code = _CHILD_SETUP + """
def pause():
    print('claimed', flush=True)
    time.sleep(60)
if sys.argv[2] == 'True':
    def run(*a, **kw):
        (root / 'effect').write_text('done')
        pause()
    runner.run_job = run
else:
    original = state.claim
    def claim(*a):
        result = original(*a)
        pause()
        return result
    state.claim = claim
scheduler.tick(root, at=at)
"""
    proc = _spawn(code, realm, after_effect)
    try:
        assert proc.stdout.readline().strip() == "claimed"
        previous = scheduler.lock_holder(realm)
        assert previous and state.acquire(realm) is None
        proc.kill()
        proc.communicate(timeout=10)
        assert scheduler.lock_holder(realm) is None
        monkeypatch.setattr(runner, "run_job", lambda *a, **kw: pytest.fail("uncertain attempt replayed"))
        result = scheduler.tick(realm, at=AT)
        assert result[0]["status"] == "held" and "Previous attempt" in result[0]["detail"]
        assert (realm / "effect").exists() is after_effect
        lease = state.acquire(realm)
        try:
            assert lease.token != previous["owner_token"]
        finally:
            lease.close()
    finally:
        _stop([proc])


def test_overlapping_daemon_and_standalone_calls_in_one_process(realm, monkeypatch):
    entered, finish = threading.Event(), threading.Event()
    results = []
    def run(*a, **kw):
        entered.set()
        assert finish.wait(5)
        return {"status": "ok"}
    monkeypatch.setattr(runner, "run_job", run)
    lease = state.acquire(realm)
    worker = threading.Thread(target=lambda: results.append(scheduler.tick(realm, at=AT, _lease=lease)))
    try:
        worker.start()
        assert entered.wait(5)
        for kwargs in ({"_lease": lease}, {}):
            result = scheduler.tick(realm, at=AT, **kwargs)
            assert result[0]["job"] == "scheduler-lock" and result[0]["status"] == "skipped"
    finally:
        finish.set()
        worker.join(timeout=5)
        lease.close()
    assert not worker.is_alive() and len(results[0]) == 1
    assert scheduler.tick(realm, at=AT) == []


@pytest.mark.parametrize("schedule", ["30 22 * * *", "daily 22:30"])
def test_midnight_catchup_cannot_replay_last_nights_attempt(realm, schedule):
    job = realm / "agents/a/jobs/daily.json"
    job.write_text(json.dumps({"id": "daily", "schedule": schedule}), encoding="utf-8")
    evening = dt.datetime(2026, 9, 30, 22, 30)
    assert len(scheduler.tick(realm, at=evening)) == 1
    assert scheduler.tick(realm, at=dt.datetime(2026, 10, 1, 0, 5)) == []
    assert state.inspect_attempt(realm, "a", "daily", "2026-10-01") is None
    assert len(scheduler.tick(realm, at=dt.datetime(2026, 10, 1, 22, 30))) == 1


def test_first_run_after_midnight_claims_previous_scheduled_day(realm):
    job = realm / "agents/a/jobs/daily.json"
    job.write_text('{"id":"daily","schedule":"30 22 * * *"}', encoding="utf-8")
    assert len(scheduler.tick(realm, at=dt.datetime(2026, 10, 1, 0, 5))) == 1
    assert state.inspect_attempt(realm, "a", "daily", "2026-09-30")["state"] == "finished"
    assert state.inspect_attempt(realm, "a", "daily", "2026-10-01") is None


def test_early_legacy_report_does_not_block_todays_later_fire(realm):
    job = realm / "agents/a/jobs/daily.json"
    job.write_text('{"id":"daily","schedule":"30 22 * * *"}', encoding="utf-8")
    reports = realm / "agents/a/runs"
    reports.mkdir()
    (reports / "a.jsonl").write_text(json.dumps({"ts":"2026-10-01T00:14:52",
                                                "task":"daily","status":"error"}) + '\n')
    assert len(scheduler.tick(realm, at=dt.datetime(2026, 10, 1, 22, 30))) == 1


def test_multiple_daily_cron_fires_still_dispatch_only_once_per_day(realm):
    job = realm / "agents/a/jobs/daily.json"
    job.write_text('{"id":"daily","schedule":"0 9,16 * * *"}', encoding="utf-8")
    assert len(scheduler.tick(realm, at=dt.datetime(2026, 10, 1, 9))) == 1
    assert scheduler.tick(realm, at=dt.datetime(2026, 10, 1, 16)) == []


def test_pid_liveness_cannot_steal_a_kernel_lease(realm, monkeypatch):
    lease = state.acquire(realm)
    try:
        monkeypatch.setattr(util, "pid_alive", lambda *a: False)
        assert state.acquire(realm) is None
        assert state.holder(realm)["owner_token"] == lease.token
    finally:
        lease.close()


def test_stale_metadata_with_reused_pid_does_not_block_recovery(realm):
    (realm / "scheduler.lock.json").write_text(json.dumps({"pid": os.getpid(), "owner_token": "old"}))
    lease = state.acquire(realm)
    try:
        assert lease.token != "old"
    finally:
        lease.close()


@pytest.mark.parametrize("boundary", ["owner", "claim"])
def test_write_failure_blocks_dispatch_and_releases_owner(realm, monkeypatch, boundary):
    original = util.write_json_atomic
    def write(path, obj, **kw):
        if (Path(path).name == "scheduler.lock.json") == (boundary == "owner"):
            raise OSError("disk full")
        return original(path, obj, **kw)
    monkeypatch.setattr(util, "write_json_atomic", write)
    monkeypatch.setattr(runner, "run_job", lambda *a, **kw: pytest.fail("unclaimed dispatch"))
    result = scheduler.tick(realm, at=AT)
    assert result[0]["status"] == "held" and "disk full" in result[0]["detail"]
    assert state.holder(realm) is None
    monkeypatch.setattr(util, "write_json_atomic", original)
    lease = state.acquire(realm)
    lease.close()


def test_failed_completion_remains_uncertain_without_retry(realm, monkeypatch):
    original = util.write_json_atomic
    calls = []
    def write(path, obj, **kw):
        if "attempts" in obj and any(a["state"] == "finished" for a in obj["attempts"].values()):
            raise OSError("disk full after dispatch")
        return original(path, obj, **kw)
    monkeypatch.setattr(util, "write_json_atomic", write)
    monkeypatch.setattr(runner, "run_job", lambda *a, **kw: calls.append(1) or {"status": "ok"})
    assert scheduler.tick(realm, at=AT)[0]["status"] == "error"
    assert scheduler.tick(realm, at=AT)[0]["status"] == "held"
    assert calls == [1]


def test_waiting_retry_is_resumed_after_restart_outside_grace(realm, monkeypatch):
    from armada import job_retries
    lease=state.acquire(realm)
    attempt,fresh=state.claim(lease,'a','daily',DAY)
    lease.close()
    report={'run_id':'first','status':'error','result':{'execution':'failed','delivery':[], 'evidence':{}}}
    util.write_json_atomic(job_retries.state_path(realm,'a','daily'),{
        'schema_version':1,'max_retries':3,
        'state':'waiting','started_at':AT.timestamp(),'next_at':AT.timestamp()+30,
        'attempts':[{'run_id':'first'}],'last_report':report})
    calls=[]
    def resume(*a,**kw):
        calls.append(1)
        util.write_json_atomic(job_retries.state_path(realm,'a','daily'),{'state':'finished'})
        return {'status':'ok'}
    monkeypatch.setattr(runner,'run_job',resume)
    assert scheduler.tick(realm,at=AT+dt.timedelta(hours=4),grace_min=1)[0]['status']=='ok'
    assert calls==[1]
    assert state.inspect_attempt(realm,'a','daily',DAY)['state']=='finished'


@pytest.mark.parametrize("raw", ["{", "[]", '{"schema_version":99}', '{"attempts":[]}', '{"attempts":{"bad":{}}}'])
def test_corrupt_or_future_attempts_are_preserved_and_block_dispatch(realm, monkeypatch, raw):
    path = state._attempt_path(realm, DAY)
    path.parent.mkdir(parents=True)
    path.write_text(raw)
    monkeypatch.setattr(runner, "run_job", lambda *a, **kw: pytest.fail("invalid admission state dispatched"))
    assert scheduler.tick(realm, at=AT)[0]["status"] == "held"
    assert path.read_text() == raw


def test_wrong_realm_or_released_lease_never_dispatches(realm, tmp_path, monkeypatch):
    other = tmp_path / "other"
    other.mkdir()
    lease = state.acquire(other)
    monkeypatch.setattr(runner, "run_job", lambda *a, **kw: pytest.fail("invalid lease dispatched"))
    assert scheduler.tick(realm, at=AT, _lease=lease)[0]["status"] == "held"
    lease.close()
    assert scheduler.tick(other, at=AT, _lease=lease)[0]["status"] == "held"


def test_failure_consumes_today_only_and_preserves_other_jobs(realm, monkeypatch):
    jobs = realm / "agents" / "a" / "jobs"
    (jobs / "second.json").write_text('{"id":"second","schedule":"daily 09:00"}')
    calls = []
    def run(root, agent, job, **kw):
        calls.append(job)
        if job == "daily":
            raise RuntimeError("provider failed")
        return {"status": "ok"}
    monkeypatch.setattr(runner, "run_job", run)
    assert [r["status"] for r in scheduler.tick(realm, at=AT)] == ["error", "ok"]
    assert scheduler.tick(realm, at=AT) == []
    scheduler.tick(realm, at=AT + dt.timedelta(days=1))
    assert calls == ["daily", "second", "daily", "second"]


def test_daemon_startup_failure_closes_all_leases(realm, monkeypatch):
    monkeypatch.setattr(scheduler, "_note_running", lambda on: (_ for _ in ()).throw(RuntimeError("startup")) if on else None)
    from armada import telegram
    monkeypatch.setattr(telegram, "start_listener", lambda *a: False)
    with pytest.raises(RuntimeError, match="startup"):
        scheduler.run_daemon(realm)
    lease = state.acquire(realm)
    lease.close()


def test_two_system_job_processes_and_boot_nudges_dispatch_once(realm):
    code = """
import sys, time, json
from pathlib import Path
from armada import sysjobs
root = Path(sys.argv[1])
def run(*args):
    print('dispatch', flush=True)
    while not (root / 'finish').exists(): time.sleep(.005)
    return {'ok': True}
sysjobs._BY_ID['prune-history']['run'] = run
print('ready', flush=True)
while not (root / 'start').exists(): time.sleep(.005)
print(json.dumps(sysjobs.run_one(root, 'prune-history')), flush=True)
"""
    procs = [_spawn(code, realm) for _ in range(2)]
    try:
        for proc in procs:
            assert proc.stdout.readline().strip() == "ready"
        (realm / "start").touch()
        first = [proc.stdout.readline().strip() for proc in procs]
        assert first.count("dispatch") == 1
        result = json.loads(next(r for r in first if r != "dispatch"))
        assert result["status"] == "skipped", result.get("error") or result
        (realm / "finish").touch()
        for proc in procs:
            _, err = proc.communicate(timeout=15)
            assert proc.returncode == 0, err
        assert sysjobs.run_one(realm, "prune-history")["status"] == "skipped"
        assert len(sysjobs.state(realm)["prune-history"]["runs"]) == 1
    finally:
        _stop(procs)


def test_crashed_system_job_requires_explicit_manual_retry(realm, monkeypatch):
    code = """
import sys, time
from armada import sysjobs
def run(*a):
    print('running', flush=True)
    time.sleep(60)
sysjobs._BY_ID['prune-history']['run'] = run
sysjobs.run_one(sys.argv[1], 'prune-history')
"""
    proc = _spawn(code, realm)
    try:
        assert proc.stdout.readline().strip() == "running"
        assert sysjobs.run_one(realm, "prune-history", manual=True)["status"] == "skipped"
        proc.kill()
        proc.communicate(timeout=10)
        calls = []
        monkeypatch.setitem(sysjobs._BY_ID["prune-history"], "run", lambda *a: calls.append(1) or {"ok": True})
        assert not sysjobs.due(realm, "prune-history")
        assert sysjobs.run_one(realm, "prune-history")["status"] == "held"
        assert next(j for j in sysjobs.status(realm) if j["id"] == "prune-history")["status"] == "held"
        assert calls == []
        previous = sysjobs.state(realm)["prune-history"]["attempt"]
        assert sysjobs.run_one(realm, "prune-history", manual=True)["ok"]
        current = sysjobs.state(realm)["prune-history"]
        assert current["attempt"]["retry_of"] == previous["attempt_id"]
        assert current["interrupted_attempts"] == [previous]
        assert calls == [1]
    finally:
        _stop([proc])


def test_system_job_claim_write_failure_blocks_work(realm, monkeypatch):
    monkeypatch.setattr(util, "write_json_atomic", lambda *a, **kw: (_ for _ in ()).throw(OSError("disk full")))
    monkeypatch.setitem(sysjobs._BY_ID["prune-history"], "run", lambda *a: pytest.fail("unclaimed system job dispatched"))
    result = sysjobs.run_one(realm, "prune-history")
    assert result["status"] == "error" and "disk full" in result["error"]


def test_system_job_result_write_failure_preserves_claim(realm, monkeypatch):
    original = util.write_json_atomic
    calls = []
    def write(path, obj, **kw):
        if obj.get("prune-history", {}).get("attempt", {}).get("state") == "finished":
            raise OSError("disk full on completion")
        return original(path, obj, **kw)
    monkeypatch.setattr(util, "write_json_atomic", write)
    monkeypatch.setitem(sysjobs._BY_ID["prune-history"], "run", lambda *a: calls.append(1) or {"ok": True})
    assert sysjobs.run_one(realm, "prune-history")["status"] == "error"
    assert sysjobs.run_one(realm, "prune-history")["status"] == "held"
    assert sysjobs.state(realm)["prune-history"]["attempt"]["state"] == "claimed"
    assert calls == [1]


def test_dry_run_respects_claims_without_writing(realm):
    before = {p.relative_to(realm): p.read_bytes() for p in realm.rglob("*") if p.is_file()}
    assert scheduler.tick(realm, at=AT, dry_run=True)[0]["status"] == "would-fire"
    assert before == {p.relative_to(realm): p.read_bytes() for p in realm.rglob("*") if p.is_file()}
    lease = state.acquire(realm)
    try:
        attempt, fresh = state.claim(lease, "a", "daily", DAY)
        assert fresh
        assert scheduler.tick(realm, at=AT, dry_run=True)[0]["status"] == "held"
        state.finish(lease, attempt, "ok")
        assert scheduler.tick(realm, at=AT, dry_run=True) == []
    finally:
        lease.close()


def test_completion_from_a_previous_owner_cannot_change_an_attempt(realm):
    old = state.acquire(realm)
    attempt, _ = state.claim(old, "a", "daily", DAY)
    old.close()
    current = state.acquire(realm)
    try:
        with pytest.raises(util.StateError, match="ownership changed"):
            state.finish(current, attempt, "ok")
        assert state.inspect_attempt(realm, "a", "daily", DAY) == attempt
    finally:
        current.close()


def test_release_preserves_metadata_with_a_different_token(realm):
    lease = state.acquire(realm)
    changed = {"schema_version": 1, "owner_token": "different", "pid": os.getpid()}
    util.write_json_atomic(realm / "scheduler.lock.json", changed)
    lease.close()
    assert util.read_json_state(realm / "scheduler.lock.json") == changed
    assert state.holder(realm) is None


def test_legacy_report_prevents_a_new_automatic_attempt(realm, monkeypatch):
    runs = realm / "agents" / "a" / "runs"
    runs.mkdir()
    (runs / "a.jsonl").write_text(json.dumps({"task": "daily", "ts": AT.isoformat(), "status": "ok"}) + "\n")
    monkeypatch.setattr(runner, "run_job", lambda *a, **kw: pytest.fail("already reported job dispatched"))
    assert scheduler.tick(realm, at=AT) == []
    assert not state._attempt_path(realm, DAY).exists()


def test_cli_shows_why_a_claim_is_held(realm, capsys):
    from armada import cli
    lease = state.acquire(realm)
    state.claim(lease, "a", "daily", DAY)
    lease.close()
    cli._print_fired(scheduler.tick(realm, at=AT), AT)
    assert "Previous attempt has no recorded outcome" in capsys.readouterr().out


def test_bad_retry_journal_holds_only_its_job(realm):
    from armada import job_retries
    util.write_json_atomic(job_retries.state_path(realm,'a','daily'),{
        'state':'waiting','next_at':'invalid'})
    util.write_json_atomic(realm/'agents/a/jobs/other.json',{
        'id':'other','schedule':'daily 09:00'})
    results={item['job']:item for item in scheduler.tick(realm,at=AT)}
    assert results['daily']['status']=='held'
    assert 'retry journal' in results['daily']['detail']
    assert results['other']['status']=='ok'
