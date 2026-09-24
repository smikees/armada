"""Stale temp files from an interrupted atomic write get collected at startup.

write_text_atomic tidies up in a `finally`, which a killed process never reaches. One live realm
had accumulated 67 of them over five days, almost all from the Telegram listener rewriting its
cursor in a scheduler process that kept being force-killed.
"""
import inspect
import os
import time

from armada import scheduler, util


def _aged(p, seconds):
    old = time.time() - seconds
    os.utime(p, (old, old))


def test_sweeps_an_old_temp_file(tmp_path):
    t = tmp_path / ".tmp-abc123.json"
    t.write_text("{}", encoding="utf-8")
    _aged(t, 7200)
    assert util.sweep_temp_files(tmp_path) == 1
    assert not t.exists()


def test_leaves_a_fresh_temp_alone(tmp_path):
    """It may belong to a write happening right now in the other process."""
    t = tmp_path / ".tmp-live.json"
    t.write_text("{}", encoding="utf-8")
    assert util.sweep_temp_files(tmp_path) == 0
    assert t.exists()


def test_never_touches_real_files(tmp_path):
    keep = [tmp_path / "realm.json", tmp_path / "telegram_state.json",
            tmp_path / "notifications.jsonl", tmp_path / "tmp-not-dotted.json"]
    for p in keep:
        p.write_text("{}", encoding="utf-8")
        _aged(p, 7200)
    assert util.sweep_temp_files(tmp_path) == 0
    assert all(p.exists() for p in keep)


def test_sweeps_the_whole_realm_tree(tmp_path):
    deep = tmp_path / "agents" / "warren" / "threads" / "main"
    deep.mkdir(parents=True)
    for p in (tmp_path / ".tmp-a.json", deep / ".tmp-b.json"):
        p.write_text("x", encoding="utf-8")
        _aged(p, 7200)
    assert util.sweep_temp_files(tmp_path) == 2


def test_a_missing_folder_is_not_an_error(tmp_path):
    assert util.sweep_temp_files(tmp_path / "gone") == 0


def test_the_age_threshold_is_respected(tmp_path):
    t = tmp_path / ".tmp-x.json"
    t.write_text("x", encoding="utf-8")
    _aged(t, 120)
    assert util.sweep_temp_files(tmp_path, older_than_sec=3600) == 0
    assert util.sweep_temp_files(tmp_path, older_than_sec=60) == 1


def test_the_scheduler_sweeps_on_startup():
    """Wiring, not just the helper: the daemon is where the leak actually happens."""
    assert "sweep_temp_files" in inspect.getsource(scheduler.run_daemon)


def test_atomic_write_still_cleans_up_on_the_normal_path(tmp_path):
    target = tmp_path / "realm.json"
    util.write_json_atomic(target, {"a": 1})
    assert target.exists()
    assert not list(tmp_path.glob(".tmp-*")), "a completed write must leave nothing behind"
