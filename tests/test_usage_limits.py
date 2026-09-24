"""Usage-limit reporting must never fail silently.

The bug these guard against: the Overview header rendered an empty string for every "unavailable"
reason except one, so when the stored OAuth token was emptied the header showed no bars AND no
explanation — indistinguishable from the feature being broken. The contract is now: an unavailable
result always carries a human-readable `message`, and the UI always renders it.
"""
import json
import re
from pathlib import Path

import pytest

from armada import usage_api

_JS = Path(__file__).resolve().parents[1] / "armada" / "webui" / "static" / "js" / "usage.js"


def _reasons_emitted_by_source() -> set:
    """Every reason string the module can actually return — read from the source, so a newly added
    reason fails this suite until someone writes the owner-facing line for it."""
    src = Path(usage_api.__file__).read_text(encoding="utf-8")
    body = src[src.index("def _fetch_live"):src.index("# Why the bars aren't showing")]
    return set(re.findall(r'"reason":\s*"([a-z-]+)"', body))


def test_every_reason_the_code_emits_has_a_message():
    missing = _reasons_emitted_by_source() - set(usage_api._REASONS)
    assert not missing, f"reasons with no owner-facing message: {sorted(missing)}"


@pytest.mark.parametrize("reason", sorted(usage_api._REASONS))
def test_known_reasons_produce_a_non_empty_message(reason):
    msg = usage_api.message_for(reason)
    assert msg and len(msg) > 10


@pytest.mark.parametrize("reason", ["", None, "brand-new-reason", "unexpected"])
def test_unknown_reasons_still_produce_a_message(reason):
    """Silence is the one unacceptable outcome — even a reason nobody has written copy for."""
    assert usage_api.message_for(reason) == usage_api._FALLBACK_MESSAGE
    assert usage_api._FALLBACK_MESSAGE.strip()


def test_normalise_adds_a_message_to_any_unavailable_result():
    for payload in ({"available": False, "reason": "no-credentials"},
                    {"available": False, "reason": "who-knows"},
                    {"available": False},
                    {}):
        out = usage_api._normalise(dict(payload))
        assert out["available"] is False
        assert out.get("message"), f"no message for {payload}"
        assert out.get("reason")


def test_normalise_leaves_available_results_alone():
    ok = {"available": True, "session": {"pct": 12}, "weekly": {"pct": 40}}
    assert usage_api._normalise(dict(ok)) == ok


def test_normalise_survives_garbage():
    assert usage_api._normalise(None)["message"]
    assert usage_api._normalise("nope")["message"]


def test_fetch_result_always_satisfies_the_ui_contract(monkeypatch):
    """Whatever _fetch_live returns, fetch() must hand the UI something renderable."""
    for payload in ({"available": False, "reason": "no-credentials"},
                    {"available": False, "reason": "never-seen"},
                    {"available": True, "session": None, "weekly": None}):
        usage_api._CACHE["data"] = None            # bypass the 60s cache between cases
        monkeypatch.setattr(usage_api, "_fetch_live", lambda p=payload: dict(p))
        out = usage_api.fetch()
        assert out["available"] or out.get("message")
    usage_api._CACHE["data"] = None


def test_missing_credentials_reports_no_credentials(monkeypatch, tmp_path):
    """An emptied credentials file (accessToken: "") must read as no-credentials, not crash —
    this is the exact state that took the bars down."""
    creds = tmp_path / ".credentials.json"
    creds.write_text(json.dumps({"claudeAiOauth": {
        "accessToken": "", "refreshToken": "", "expiresAt": 0}}), encoding="utf-8")
    monkeypatch.setattr(usage_api, "_CREDS", creds)
    assert usage_api._read_token() is None
    out = usage_api._normalise(usage_api._fetch_live())
    assert out["reason"] == "no-credentials" and out["message"]


def test_absent_credentials_file_is_handled(monkeypatch, tmp_path):
    monkeypatch.setattr(usage_api, "_CREDS", tmp_path / "nope.json")
    assert usage_api._read_token() is None


def test_header_renderer_never_returns_empty_for_unavailable():
    """The JS half of the contract: no early `return ""` when usage is unavailable."""
    js = _JS.read_text(encoding="utf-8")
    fn = js[js.index("function headerLimitsHTML"):]
    fn = fn[:fn.index("async function renderHeaderLimits")]
    assert "d.message" in fn, "renderer must display the server's message"
    assert 'return "";' not in fn, "unavailable must never render as nothing"


def test_header_renderer_has_its_own_fallback_string():
    """Even if the server somehow sends no message, the user sees words rather than a blank."""
    js = _JS.read_text(encoding="utf-8")
    fn = js[js.index("function headerLimitsHTML"):js.index("async function renderHeaderLimits")]
    assert re.search(r'\(d&&d\.message\)\|\|"[^"]{10,}"', fn)
