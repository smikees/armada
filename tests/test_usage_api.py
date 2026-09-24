"""Real-usage endpoint parsing (armada.usage_api): window normalisation + reset countdown.

Network + credentials are not exercised here (they're environment-specific and best-effort at
runtime); these lock the pure parsing/formatting that turns the endpoint's JSON into widget data.
"""
import datetime as dt
from armada import usage_api


def _iso(**delta):
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(**delta)).isoformat()


def test_window_normalizes_utilization_and_reset():
    w = usage_api._window({"utilization": 43.7, "resets_at": _iso(hours=2, minutes=10)})
    assert w["pct"] == 44                       # rounded
    assert w["resets_in"] in ("2h 10m", "2h 9m")


def test_window_handles_missing_and_empty():
    assert usage_api._window(None) is None
    assert usage_api._window({}) == {"pct": 0, "resets_at": "", "resets_in": ""}


def test_countdown_formats_days_hours_and_past():
    assert usage_api._countdown(_iso(days=3, hours=4)).startswith("3d")
    assert usage_api._countdown(_iso(minutes=45)) in ("45m", "44m")
    assert usage_api._countdown(_iso(hours=-1)) == "now"
    assert usage_api._countdown("not-a-date") == ""


def test_fetch_reports_unavailable_without_a_token(monkeypatch):
    monkeypatch.setattr(usage_api, "_read_token", lambda: None)
    usage_api._CACHE["data"] = None      # bypass any cached live result
    out = usage_api.fetch()
    assert out["available"] is False and out["reason"] == "no-credentials"


def test_fetch_reports_expired_without_calling_network(monkeypatch):
    # an expired token must never hit the network (read-only, no refresh)
    monkeypatch.setattr(usage_api, "_read_token", lambda: ("tok", 1))   # expiresAt in 1970
    def _boom(*a, **k):
        raise AssertionError("network must not be called for an expired token")
    monkeypatch.setattr(usage_api.urllib.request, "urlopen", _boom)
    usage_api._CACHE["data"] = None
    out = usage_api.fetch()
    assert out["available"] is False and out["reason"] == "token-expired"
