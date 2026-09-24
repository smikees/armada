"""Claude usage that stays on screen between agent runs.

ARMADA reads the subscription figures with the OAuth token Claude Code keeps locally. That token
lives about half a day, and ARMADA deliberately never refreshes it — holding another application's
refresh token is how you break its sign-in. So the bars used to vanish entirely once it lapsed, with
the message "Claude usage updates when an agent next runs": accurate, and a blank header.

Two halves fix it. A keepalive job asks Claude Code for one word every few hours so it renews its own
token (measured: a 5-second call bought ~18 hours). And every good reading is banked, so when the
live call does fail the figures are served with their age instead of not at all.
"""
import json
import time

import pytest

from armada import sysjobs, usage_api

GOOD = {"available": True,
        "session": {"pct": 12, "resets_at": "2026-09-18T16:00:00+00:00", "resets_in": "3h 39m"},
        "weekly": {"pct": 3, "resets_at": "2026-09-25T04:00:00+00:00", "resets_in": "6d 15h"}}


@pytest.fixture(autouse=True)
def _clear_cache():
    usage_api._CACHE.update({"at": 0.0, "data": None})
    yield
    usage_api._CACHE.update({"at": 0.0, "data": None})


# --------------------------------------------------------------------------- remembering a reading

def test_a_good_reading_is_banked(tmp_path, monkeypatch):
    monkeypatch.setattr(usage_api, "_fetch_live", lambda: dict(GOOD))
    d = usage_api.fetch(tmp_path)
    assert d["available"] and d["stale"] is False and d["age_sec"] == 0
    assert (tmp_path / usage_api._DISK).exists(), "nothing banked for next time"


def test_a_failure_replays_the_last_reading(tmp_path, monkeypatch):
    monkeypatch.setattr(usage_api, "_fetch_live", lambda: dict(GOOD))
    usage_api.fetch(tmp_path)
    usage_api._CACHE.update({"at": 0.0, "data": None})
    monkeypatch.setattr(usage_api, "_fetch_live",
                        lambda: {"available": False, "reason": "token-expired"})
    d = usage_api.fetch(tmp_path)
    assert d["available"] is True, "the header went blank again"
    assert d["stale"] is True and d["stale_reason"] == "token-expired"
    assert d["session"]["pct"] == 12 and d["weekly"]["pct"] == 3


def test_a_stale_reading_drops_its_countdown(tmp_path, monkeypatch):
    """The percentages were real; 'resets in 3h 39m' from hours ago is simply wrong."""
    monkeypatch.setattr(usage_api, "_fetch_live", lambda: dict(GOOD))
    usage_api.fetch(tmp_path)
    usage_api._CACHE.update({"at": 0.0, "data": None})
    monkeypatch.setattr(usage_api, "_fetch_live", lambda: {"available": False, "reason": "fetch-failed"})
    d = usage_api.fetch(tmp_path)
    assert "resets_in" not in d["session"] and "resets_in" not in d["weekly"]
    assert "resets_at" in d["session"], "the absolute time is still true and still useful"


def test_the_replay_says_how_old_it_is(tmp_path, monkeypatch):
    p = tmp_path / usage_api._DISK
    p.write_text(json.dumps({"at": time.time() - 3 * 3600, "data": GOOD}), encoding="utf-8")
    monkeypatch.setattr(usage_api, "_fetch_live", lambda: {"available": False, "reason": "token-expired"})
    d = usage_api.fetch(tmp_path)
    assert d["age_sec"] > 10_000
    assert "3h old" in d["message"]


def test_a_week_old_reading_is_not_served(tmp_path, monkeypatch):
    p = tmp_path / usage_api._DISK
    p.write_text(json.dumps({"at": time.time() - 8 * 24 * 3600, "data": GOOD}), encoding="utf-8")
    monkeypatch.setattr(usage_api, "_fetch_live", lambda: {"available": False, "reason": "token-expired"})
    d = usage_api.fetch(tmp_path)
    assert d["available"] is False, "that is history, not a reading"
    assert d["message"]


def test_a_live_reading_always_wins(tmp_path, monkeypatch):
    p = tmp_path / usage_api._DISK
    p.write_text(json.dumps({"at": time.time() - 60, "data": GOOD}), encoding="utf-8")
    fresh = {"available": True, "session": {"pct": 77, "resets_at": "", "resets_in": ""},
             "weekly": {"pct": 9, "resets_at": "", "resets_in": ""}}
    monkeypatch.setattr(usage_api, "_fetch_live", lambda: fresh)
    d = usage_api.fetch(tmp_path)
    assert d["session"]["pct"] == 77 and d["stale"] is False


def test_no_realm_still_works(monkeypatch):
    """fetch() is called from places that have no realm; it must not explode or try to persist."""
    monkeypatch.setattr(usage_api, "_fetch_live", lambda: dict(GOOD))
    assert usage_api.fetch()["available"] is True


def test_a_corrupt_cache_is_ignored(tmp_path, monkeypatch):
    (tmp_path / usage_api._DISK).write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(usage_api, "_fetch_live", lambda: {"available": False, "reason": "token-expired"})
    assert usage_api.fetch(tmp_path)["available"] is False


def test_every_unavailable_reason_still_carries_a_message():
    """A reason with no message is how the header went silently blank once before."""
    for reason in usage_api._REASONS:
        assert usage_api.message_for(reason)
    assert usage_api.message_for("something-new-we-have-not-seen")


# --------------------------------------------------------------------------- the keepalive job

def test_the_keepalive_is_registered_and_costs_quota():
    j = next((x for x in sysjobs.JOBS if x["id"] == "usage-keepalive"), None)
    assert j, "no keepalive job"
    assert j["cost"] == sysjobs.QUOTA, "it spends the subscription, however little — say so"
    assert j["every_hours"] == 8, "must beat the ~12h token life with margin"
    assert "turn it off" in j["description"], "the owner needs to know it is optional"


def test_the_keepalive_skips_when_the_signin_is_already_fresh(tmp_path, monkeypatch):
    """Three calls a day is the budget; it should not spend one it doesn't need."""
    import armada.sysjobs as S
    ran = []
    monkeypatch.setattr(S.Path, "home", staticmethod(lambda: tmp_path))
    c = tmp_path / ".claude"
    c.mkdir()
    far = int((time.time() + 20 * 3600) * 1000)
    (c / ".credentials.json").write_text(json.dumps({"claudeAiOauth": {"expiresAt": far}}),
                                         encoding="utf-8")
    monkeypatch.setattr("subprocess.run", lambda *a, **k: ran.append(a) or None)
    r = S._job_usage_keepalive(tmp_path)
    assert r["ok"] and "nothing to do" in r["detail"]
    assert not ran, "spent a call it did not need"


def test_the_keepalive_reports_a_missing_cli_rather_than_crashing(tmp_path, monkeypatch):
    import armada.sysjobs as S
    monkeypatch.setattr(S.Path, "home", staticmethod(lambda: tmp_path))
    (tmp_path / ".claude").mkdir()
    monkeypatch.setattr("armada.engine.claude.ClaudeEngine._launcher", lambda self: None)
    r = S._job_usage_keepalive(tmp_path)
    assert r["ok"] is False and "PATH" in r["detail"]


def test_armada_never_writes_the_credentials_file():
    """The whole reason the keepalive exists: consuming another app's refresh token could
    invalidate its sign-in, and writing the file back means mutating its credential store."""
    import inspect
    src = inspect.getsource(usage_api)
    assert "refreshToken" not in src
    assert "_CREDS.write" not in src and "write_text" not in src.split("_CREDS")[1][:2000]
