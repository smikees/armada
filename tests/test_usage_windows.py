"""Usage line-mode windowing (armada.webui._usage_data): today / 7d / mtd filter run telemetry.

Stubs _runs so no realm on disk is needed. Asserts hold regardless of the calendar date the test
runs on: 'today' is only the current day, '7d' includes a 2-days-ago run, and a 40-day-old run is
excluded from every window (guards against the old 'all windows show the same total' behaviour).
"""
import datetime
import types
from armada import webui


def _ts(d):
    return d.isoformat() + "T10:00:00"


def _run(webui_mod, tok, day_offset):
    d = datetime.date.today() - datetime.timedelta(days=day_offset)
    return {"ts": _ts(d), "tokens": {"total": tok, "api_equiv_usd": 0.0}, "model": "claude-opus-5"}


def _make(monkeypatch):
    warren = types.SimpleNamespace(id="warren", display="Warren")
    realm = types.SimpleNamespace(coordinator=None, members=[warren])
    runs = [_run(webui, 100, 0),      # today
            _run(webui, 50, 2),       # 2 days ago  -> in 7d
            _run(webui, 9999, 40)]    # 40 days ago -> outside today / 7d / mtd
    # _runs is an internal helper in webui._core; patch it there so the internal callers see it
    monkeypatch.setattr(webui._core, "_runs", lambda root, aid: runs if aid == "warren" else [])
    # stop _usage_data's model-catalog lookup from touching the network/disk during tests
    monkeypatch.setattr(webui.models, "options", lambda root: [("claude-opus-5", "Claude Opus 5")])
    return realm


def _total(monkeypatch, window):
    realm = _make(monkeypatch)
    return webui._usage_data(realm, "/nonexistent", "line", window)


def test_today_is_only_the_current_day(monkeypatch):
    d = _total(monkeypatch, "today")
    assert d["window"] == "today"
    assert d["total"] == 100
    assert next(a["tok"] for a in d["agents"] if a["name"] == "Warren") == 100


def test_7d_includes_recent_but_not_the_40_day_old_run(monkeypatch):
    d = _total(monkeypatch, "7d")
    assert d["window"] == "7d"
    assert d["total"] == 150            # 100 today + 50 two-days-ago; 9999 excluded


def test_mtd_starts_at_first_of_month_and_excludes_old_run(monkeypatch):
    d = _total(monkeypatch, "mtd")
    assert d["window"] == "mtd"
    assert d["total"] >= 100 and d["total"] < 9999   # includes today's run, never the 40-day-old one


def test_unknown_window_falls_back_to_7d(monkeypatch):
    d = _total(monkeypatch, "bogus")
    assert d["window"] == "7d" and d["total"] == 150


def _graph(monkeypatch, window, by="agents"):
    realm = _make(monkeypatch)
    return webui._usage_data(realm, "/nonexistent", "graph", window, by)


def test_graph_daily_has_7_day_bars(monkeypatch):
    d = _graph(monkeypatch, "daily")
    assert d["window"] == "daily" and len(d["bars"]) == 7
    assert d["total"] == 150            # today + 2-days-ago; 40-day-old run is outside 7 days


def test_graph_weekly_has_8_week_bars(monkeypatch):
    d = _graph(monkeypatch, "weekly")
    assert d["window"] == "weekly" and len(d["bars"]) == 8


def test_graph_monthly_has_12_month_bars(monkeypatch):
    d = _graph(monkeypatch, "monthly")
    assert d["window"] == "monthly" and len(d["bars"]) == 12


def test_graph_unknown_window_falls_back_to_daily(monkeypatch):
    d = _graph(monkeypatch, "bogus")
    assert d["window"] == "daily" and len(d["bars"]) == 7


def test_graph_by_models_splits_segments(monkeypatch):
    d = _graph(monkeypatch, "daily", by="models")
    assert d["by"] == "models"
    segs = [s for b in d["bars"] for s in b["segments"]]
    assert segs and all("color" in s and s["tok"] > 0 for s in segs)
