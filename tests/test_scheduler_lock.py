"""The scheduler lock — one realm, one ticker at a time (Phase 2, 2.9).

The bug this exists for: two schedulers ticking the same realm — a daemon left running in a
forgotten terminal plus a second one started later, or a persistent daemon plus a one-shot
`--once` run landing in the same minute. `ran_today()` alone only closes that race AFTER a job's
run-report is written; a job that takes any real time to run reads as "not yet run today" to a
second ticker the whole time it's in flight, and both fire it. These cover lease lifecycle and
legacy metadata. test_scheduler_claims.py also synchronizes real independent processes.
"""
import json

from armada import scheduler as S


def _realm(tmp_path, name="r"):
    r = tmp_path / name
    r.mkdir(parents=True, exist_ok=True)
    (r / "realm.json").write_text(json.dumps({"name": name}), encoding="utf-8")
    return r


def test_pid_alive_is_true_for_this_process_and_false_for_a_bogus_one():
    import os
    from armada import util
    assert util.pid_alive(os.getpid()) is True
    assert util.pid_alive(0) is False
    assert util.pid_alive(-1) is False
    assert util.pid_alive("not a pid") is False


def test_an_unlocked_realm_has_no_holder(tmp_path):
    r = _realm(tmp_path)
    assert S.lock_holder(r) is None


def test_acquiring_writes_this_process_as_the_holder(tmp_path):
    import os
    r = _realm(tmp_path)
    lease = S._lock_acquire(r)
    assert lease is not None
    holder = S.lock_holder(r)
    assert holder["pid"] == os.getpid()
    S._lock_release(lease)
    assert S.lock_holder(r) is None


def test_reacquiring_your_own_lock_is_busy(tmp_path):
    r = _realm(tmp_path)
    lease = S._lock_acquire(r)
    try:
        assert lease is not None
        assert S._lock_acquire(r) is None
    finally:
        S._lock_release(lease)


def test_a_live_different_pid_blocks_acquisition(tmp_path, monkeypatch):
    r = _realm(tmp_path)
    (r / "scheduler.lock.json").write_text(
        json.dumps({"pid": 999999, "started": "2026-01-01T00:00:00"}), encoding="utf-8")
    monkeypatch.setattr(S._util, "pid_alive", lambda pid: pid == 999999)
    assert S._lock_acquire(r) is None
    holder = S.lock_holder(r)
    assert holder["pid"] == 999999


def test_a_dead_pids_lock_is_stale_and_gets_taken_over(tmp_path, monkeypatch):
    import os
    r = _realm(tmp_path)
    (r / "scheduler.lock.json").write_text(
        json.dumps({"pid": 999999, "started": "2026-01-01T00:00:00"}), encoding="utf-8")
    # 999999 is dead; this process is (obviously) alive — a real pid_alive would agree with both.
    monkeypatch.setattr(S._util, "pid_alive", lambda pid: pid == os.getpid())
    assert S.lock_holder(r) is None, "a dead pid must not read as a live holder"
    lease = S._lock_acquire(r)
    assert lease is not None
    assert S.lock_holder(r)["pid"] == os.getpid()
    S._lock_release(lease)


def test_release_only_removes_the_lock_you_hold(tmp_path):
    r = _realm(tmp_path)
    old = S._lock_acquire(r)
    S._lock_release(old)
    new = S._lock_acquire(r)
    try:
        S._lock_release(old)
        assert S.lock_holder(r)["owner_token"] == new.token
        assert S._lock_acquire(r) is None
    finally:
        S._lock_release(new)


def test_tick_skips_firing_when_another_live_scheduler_holds_the_lock(tmp_path, monkeypatch):
    """The actual double-fire guard: a standalone tick() call backs off rather than racing a
    scheduler that's already ticking this realm."""
    r = _realm(tmp_path)
    (r / "scheduler.lock.json").write_text(
        json.dumps({"pid": 999999, "started": "2026-01-01T00:00:00"}), encoding="utf-8")
    monkeypatch.setattr(S._util, "pid_alive", lambda pid: pid == 999999)
    fired = S.tick(r)
    assert len(fired) == 1
    assert fired[0]["status"] == "skipped"
    assert fired[0]["job"] == "scheduler-lock"
    assert "999999" in fired[0]["detail"]


def test_dry_run_ticks_are_never_blocked_by_the_lock(tmp_path, monkeypatch):
    """A preview (the web UI's 'what's due' check) must work even while a real scheduler owns the
    realm — it fires nothing, so it can't race anyone."""
    r = _realm(tmp_path)
    (r / "scheduler.lock.json").write_text(
        json.dumps({"pid": 999999, "started": "2026-01-01T00:00:00"}), encoding="utf-8")
    monkeypatch.setattr(S._util, "pid_alive", lambda pid: pid == 999999)
    fired = S.tick(r, dry_run=True)
    assert fired == [], "no agents/jobs in this fixture, and no lock-skip record either"


def test_a_standalone_tick_takes_and_releases_the_lock_around_itself(tmp_path, monkeypatch):
    """After a normal (unlocked) tick, the lock must not be left behind for the next caller."""
    r = _realm(tmp_path)
    from armada import sysjobs
    monkeypatch.setattr(sysjobs, 'run_due', lambda *a, **kw: [])
    S.tick(r)
    assert S.lock_holder(r) is None


def test_run_daemon_refuses_a_second_scheduler_on_the_same_realm(tmp_path, monkeypatch):
    """The reported bug, closed at the coarse level: don't even start a second daemon."""
    r = _realm(tmp_path)
    (r / "scheduler.lock.json").write_text(
        json.dumps({"pid": 999999, "started": "2026-01-01T00:00:00"}), encoding="utf-8")
    monkeypatch.setattr(S._util, "pid_alive", lambda pid: pid == 999999)
    ticked = []
    monkeypatch.setattr(S, "tick", lambda root, **kw: ticked.append(str(root)) or [])
    assert S.run_daemon(r, interval=5) == 1
    assert ticked == [], "a refused daemon must not tick anything"
    # the other process's lock is untouched
    assert S.lock_holder(r)["pid"] == 999999


def test_run_daemon_drops_an_already_owned_also_realm_but_still_runs_the_primary(tmp_path, monkeypatch):
    a, b = _realm(tmp_path, "a"), _realm(tmp_path, "b")
    (b / "scheduler.lock.json").write_text(
        json.dumps({"pid": 999999, "started": "2026-01-01T00:00:00"}), encoding="utf-8")
    monkeypatch.setattr(S._util, "pid_alive", lambda pid: pid == 999999)
    ticked = []
    monkeypatch.setattr(S, "tick", lambda root, **kw: ticked.append(str(root)) or [])
    monkeypatch.setattr(S.time, "sleep", lambda *_: (_ for _ in ()).throw(KeyboardInterrupt))
    assert S.run_daemon(a, also=[b], interval=5) == 0
    assert ticked == [str(a)], "b is owned elsewhere and must be dropped, not ticked"
    assert S.lock_holder(a) is None, "the primary realm's lock must be released on shutdown"
    assert S.lock_holder(b)["pid"] == 999999, "the other process's lock on b is untouched"
