"""Usage-limit reporting must never fail silently.

The bug these guard against: the Overview header rendered an empty string for every "unavailable"
reason except one, so when the stored OAuth token was emptied the header showed no bars AND no
explanation — indistinguishable from the feature being broken. The contract is now: an unavailable
result always carries a human-readable `message`, and the UI always renders it.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from armada import usage_api

_JS = Path(__file__).resolve().parents[1] / "armada" / "webui" / "static" / "js" / "usage.js"


def test_browser_limits_cache_is_scoped_to_launch_and_retries_stale_early():
    if not shutil.which('node'):
        pytest.skip('node not available')
    script = r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(process.argv[1],'utf8');
const store=new Map(),header={dataset:{appSession:'first'}}; let now=100000;
const context={window:{},Date:{now:()=>now},document:{getElementById:()=>header},
sessionStorage:{getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v)}};
vm.runInNewContext(source.slice(0,source.indexOf('function uKey'))+
'globalThis.cache={get:cacheGet,set:cacheSet};})();',context);
context.cache.set('mc_uc_lim_v3',{available:true,weekly:{pct:20}});
now+=40000;
assert.equal(context.cache.get('mc_uc_lim_v3',300000).weekly.pct,20);
header.dataset.appSession='second';
assert.equal(context.cache.get('mc_uc_lim_v3',Infinity),null);
context.cache.set('mc_uc_lim_v3',{available:true,stale:true,weekly:{pct:20}});
now+=31000;
assert.equal(context.cache.get('mc_uc_lim_v3',300000),null);
assert.equal(context.cache.get('mc_uc_lim_v3',Infinity).weekly.pct,20);
'''
    result = subprocess.run(['node','-e',script,str(_JS)], capture_output=True,text=True,timeout=10)
    assert result.returncode == 0, result.stderr


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


def _render_limits(claude=None, codex=None, bucket=None, gemini=None):
    """Exercise the actual renderer without starting a browser or contacting either provider."""
    if not shutil.which("node"):
        pytest.skip("node not available")
    script = r'''
const fs=require('node:fs'), vm=require('node:vm');
const source=fs.readFileSync(process.argv[1], 'utf8');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const context={window:{}};
vm.runInNewContext(input.icons,context);
vm.runInNewContext(source.slice(0,source.indexOf('// Keep the Overview'))
  +'globalThis.renderLimits=headerLimitsHTML;})();',context);
process.stdout.write(context.renderLimits(...input.args));
'''
    from armada.icons import _ICONS_JS
    result = subprocess.run(["node", "-e", script, str(_JS)],
                            input=json.dumps({"args": [claude, codex, bucket, gemini],
                                              "icons": _ICONS_JS.replace("<script>", "").replace("</script>", "")}),
                            capture_output=True, text=True, encoding="utf-8", timeout=10)
    assert result.returncode == 0, result.stderr
    return result.stdout


def _rows(html):
    return re.findall(r'<div class="mc-limit-row\b.*?</div>', html)


def test_header_renderer_never_returns_empty_for_unavailable():
    html = _render_limits({"available": False, "message": 'Please sign in to "Claude".'})
    assert html.count("Subscription limits") == 1
    assert html.index('aria-label="Codex subscription limits"') < html.index('aria-label="Claude subscription limits"')
    assert html.count('class="mc-limit-provider"') == 3 and html.count('class="mc-engine-logo') == 3
    assert html.count('>Week</span>') == 1 and html.count('>Session</span>') == 1
    rows = _rows(html)
    assert len(rows) == 6 and all("is-unavailable" in row for row in rows)
    assert all("mc-limit-pct" not in row and "mc-limit-reset" not in row and "aria-valuenow" not in row for row in rows)
    assert "Please sign in to &quot;Claude&quot;." in rows[2]
    assert "Codex usage is unavailable right now." in rows[0]
    assert html.count('is-inactive') == 3
    assert 'is-placeholder' not in html and 'Checking Gemini connection' in rows[4]


def test_header_maps_codex_windows_by_duration_and_preserves_zero():
    codex = {"available": True, "groups": [{"id": "codex", "name": "Codex", "windows": [
        {"window_minutes": 10080, "pct": 8, "resets_in": "6d 22h"},
        {"window_minutes": 300, "pct": 0, "resets_in": "4h 59m"}]}]}
    claude = {"available": True, "weekly": {"pct": 72, "resets_in": "2d 3h"},
              "session": {"pct": 17, "resets_in": "1h 20m"}}
    rows = _rows(_render_limits(claude, codex))
    for row, provider, pct, reset in zip(rows, ["Codex", "Codex", "Claude", "Claude"],
                                       [8, 0, 72, 17], ["6d 22h", "4h 59m", "2d 3h", "1h 20m"]):
        assert f'aria-label="{provider} · ' in row
        assert f'>{provider}</span>' not in row and f'>{pct}%</span>' in row
        assert f'resets in {reset}' in row and 'is-unavailable' not in row


def test_weekly_only_account_does_not_invent_a_session_limit():
    codex = {"available": True, "groups": [{"id": "codex", "windows": [
        {"window_minutes": 10080, "pct": 8, "resets_in": "6d 22h"}]}]}
    rows = _rows(_render_limits(None, codex))
    assert '>8%</span>' in rows[0]
    assert 'is-unavailable' in rows[1] and 'does not report a session limit' in rows[1]
    assert 'aria-valuenow' not in rows[1]


def test_stale_or_null_percentages_are_not_shown_as_current_values():
    claude = {"available": True, "stale": True, "age_sec": 172800,
              "weekly": {"pct": 89, "resets_in": "1h 0m"}}
    codex = {"available": True, "groups": [{"id": "codex", "windows": [
        {"window_minutes": 300, "pct": None, "resets_in": "1h 0m"}]}]}
    html = _render_limits(claude, codex)
    assert 'Last reading: 89%, 2d ago.' in html
    assert all('is-unavailable' in row and 'mc-limit-pct' not in row and 'mc-limit-reset' not in row for row in _rows(html))


def test_selected_codex_bucket_applies_to_both_periods():
    codex = {"available": True, "groups": [
        {"id": "codex", "name": "Codex", "windows": [{"window_minutes": 10080, "pct": 8}]},
        {"id": "extra", "name": "Extra", "windows": [{"window_minutes": 300, "pct": 45}]}]}
    html = _render_limits(None, codex, "extra")
    assert '<option value="extra" selected>' in html
    assert 'is-unavailable' in _rows(html)[0] and '>45%</span>' in _rows(html)[1]
    assert 'mc-limit-reset' not in html, 'An unreported reset must not show placeholder text.'


def test_loading_preserves_landmarks_and_never_implies_a_zero_or_unavailable_reading():
    loading = {'loading':True}
    html = _render_limits(loading,loading,gemini=loading)
    rows = _rows(html)
    assert len(rows) == 6 and all('aria-busy="true"' in row for row in rows)
    assert html.count('mc-limit-loading') == 6 and html.count('<i aria-hidden="true">') == 18
    assert html.count('class="mc-engine-logo') == 3
    assert html.count('>Week</span>') == html.count('>Session</span>') == 1
    assert 'is-inactive' not in html and 'is-unavailable' not in html
    assert 'mc-limit-bar' not in html and 'mc-limit-pct' not in html and 'aria-valuenow' not in html


def test_slow_provider_keeps_dots_while_ready_and_unavailable_providers_settle():
    html = _render_limits({'available':False,'message':'Sign in required'},
        {'available':True,'groups':[{'id':'codex','windows':[{'window_minutes':10080,'pct':24}]}]},
        gemini={'loading':True})
    rows = _rows(html)
    assert '>24%</span>' in rows[0]
    assert 'does not report a session limit' in rows[1] and 'mc-limit-loading' not in rows[1]
    assert all('is-unavailable' in row and 'mc-limit-loading' not in row for row in rows[2:4])
    assert all('mc-limit-loading' in row for row in rows[4:])


def test_server_render_contains_loading_landmarks_before_javascript():
    from armada.webui.pages import _initial_header_limits
    html = _initial_header_limits(True)
    assert len(_rows(html)) == 6 and html.count('mc-limit-loading') == 6
    assert html.count('>Week</span>') == html.count('>Session</span>') == 1
    assert html.count('mc-limit-provider') == 3
    assert _initial_header_limits(False).count('mc-limit-loading') == 4
