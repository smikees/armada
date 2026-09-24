"""Atomic writes survive Windows' momentary file locks (seen 2026-09-24 in scheduler.log: the
Telegram listener's state write failed with WinError 32 while another process read the file)."""
import os

import pytest

from armada import util


def _busy(n, winerror=32):
    calls = {"n": 0}
    real = os.replace

    def fake(src, dst):
        calls["n"] += 1
        if calls["n"] <= n:
            e = PermissionError(13, "The process cannot access the file because it is being used by another process")
            e.winerror = winerror
            raise e
        return real(src, dst)
    return fake, calls


def test_a_brief_lock_is_waited_out(tmp_path, monkeypatch):
    fake, calls = _busy(3)
    monkeypatch.setattr(util.os, "replace", fake)
    monkeypatch.setattr(util.time, "sleep", lambda s: None)
    util.write_json_atomic(tmp_path / "s.json", {"a": 1})
    assert (tmp_path / "s.json").read_text(encoding="utf-8").strip().startswith("{")
    assert calls["n"] == 4
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".tmp-")]    # no temp left behind


def test_a_lock_that_never_clears_still_raises(tmp_path, monkeypatch):
    fake, _ = _busy(99)
    monkeypatch.setattr(util.os, "replace", fake)
    monkeypatch.setattr(util.time, "sleep", lambda s: None)
    with pytest.raises(PermissionError):
        util.write_text_atomic(tmp_path / "s.txt", "x")
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".tmp-")]


def test_other_permission_errors_are_not_retried(tmp_path, monkeypatch):
    fake, calls = _busy(99, winerror=1234)
    monkeypatch.setattr(util.os, "replace", fake)
    with pytest.raises(PermissionError):
        util.write_text_atomic(tmp_path / "s.txt", "x")
    assert calls["n"] == 1
