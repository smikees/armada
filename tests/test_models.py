"""Model catalog (armada.models): seeding, newest-first order, merge/retire, offline safety.

Network is stubbed via models.fetch_live_result (what refresh() calls) so no token is needed. _last_try is pinned so
the lazy background refresh in options() never fires during a test.
"""
from armada import models


def _no_async(monkeypatch):
    monkeypatch.setattr(models, "_last_try", 9e18)


def test_seeds_when_cache_absent(monkeypatch, tmp_path):
    _no_async(monkeypatch)
    monkeypatch.setattr(models, "fetch_live_result", lambda: (None, "unreachable (test)"))
    opts = models.options(str(tmp_path))
    assert opts and opts[0] == ("claude-fable-5-1", "Claude Fable 5.1")   # seed, newest first


def test_refresh_orders_newest_first_and_retires_missing(monkeypatch, tmp_path):
    _no_async(monkeypatch)
    monkeypatch.setattr(models, "fetch_live_result", lambda: ([
        {"id": "claude-opus-6", "label": "Claude Opus 6", "created_at": "2026-10-01T00:00:00Z"},
        {"id": "claude-opus-5", "label": "Claude Opus 5", "created_at": "2026-05-01T00:00:00Z"}], ""))
    r = models.refresh(str(tmp_path))
    assert r["ok"] and r["active"] == 2
    ids = [i for i, _ in models.options(str(tmp_path))]
    assert ids == ["claude-opus-6", "claude-opus-5"]          # newest (later created_at) first
    # seed ids not in the live list are retired (kept in cache, hidden from dropdowns)
    cached = {m["id"]: m for m in models.load(str(tmp_path))["models"]}
    assert cached["claude-fable-5-1"]["active"] is False
    assert "claude-fable-5-1" not in ids


def test_refresh_unavailable_keeps_cache(monkeypatch, tmp_path):
    _no_async(monkeypatch)
    monkeypatch.setattr(models, "fetch_live_result", lambda: ([
        {"id": "claude-opus-6", "label": "Claude Opus 6", "created_at": "2026-10-01T00:00:00Z"}], ""))
    models.refresh(str(tmp_path))
    monkeypatch.setattr(models, "fetch_live_result", lambda: (None, "unreachable (test)"))   # endpoint down / token expired
    r = models.refresh(str(tmp_path))
    assert r["ok"] is False
    assert [i for i, _ in models.options(str(tmp_path))] == ["claude-opus-6"]   # unchanged


def test_options_written_atomically_and_reload(monkeypatch, tmp_path):
    _no_async(monkeypatch)
    monkeypatch.setattr(models, "fetch_live_result", lambda: ([
        {"id": "claude-sonnet-5", "label": "Claude Sonnet 5", "created_at": "2026-06-01T00:00:00Z"}], ""))
    models.refresh(str(tmp_path))
    assert (tmp_path / ".armada" / "models.json").exists()
    assert models.load(str(tmp_path))["models"][0]["id"] == "claude-sonnet-5"
