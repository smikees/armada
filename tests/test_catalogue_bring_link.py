"""Bring a link (ADR-004's second path): paste a URL, an agent runs the capability-review
protocol against it, and the report is what the owner reads before Add is enabled.

review_url() is the piece that talks to an engine; add_link_to_realm() is the piece that writes
the record once the owner has decided. Both are tested against a fake engine — never the real
Claude CLI, which would spend tokens and take real minutes for what should be a fast test.
"""
import json

import pytest

from armada import catalogue as C
from armada.catalogue import realm as CREALM
from armada.engine.base import RunResult, Usage


class _FakeEngine:
    """Records what it was asked to do and returns a scripted answer."""

    def __init__(self, result=None, doctor_ok=True, doctor_detail="fine"):
        self.result = result or RunResult(ok=True, output="{}")
        self.doctor_ok = doctor_ok
        self.doctor_detail = doctor_detail
        self.calls = []

    def doctor(self):
        return self.doctor_ok, self.doctor_detail

    def run(self, system, prompt, **kw):
        self.calls.append({"system": system, "prompt": prompt, **kw})
        return self.result


# --- _extract_json ---------------------------------------------------------------------------------

def test_extract_json_finds_an_object_wrapped_in_prose():
    text = 'Sure, here is the report:\n```json\n{"a": 1, "b": {"c": 2}}\n```\nLet me know if needed.'
    assert C._extract_json(text) == {"a": 1, "b": {"c": 2}}


def test_extract_json_finds_a_bare_object():
    assert C._extract_json('{"name": "x"}') == {"name": "x"}


def test_extract_json_returns_none_without_an_object():
    assert C._extract_json("no json here at all") is None


def test_extract_json_skips_a_malformed_object_and_finds_the_next():
    text = '{"broken": } then later {"ok": true}'
    assert C._extract_json(text) == {"ok": True}


# --- review_url --------------------------------------------------------------------------------

def test_review_url_rejects_something_that_is_not_a_link():
    r = C.review_url("not a link")
    assert r["ok"] is False and "http" in r["error"]


def test_review_url_reports_a_doctor_failure(_isolated):
    eng = _FakeEngine(doctor_ok=False, doctor_detail="claude not logged in")
    r = C.review_url("https://github.com/acme/thing", engine=eng)
    assert r["ok"] is False and r["error"] == "claude not logged in"
    assert not eng.calls, "must not run a turn if the engine isn't even usable"


def test_review_url_runs_the_capability_review_skill_with_tools(_isolated):
    good = RunResult(ok=True, output=json.dumps({
        "name": "Thing", "kind": "extensions", "publisher": "Acme",
        "runs": "code", "touch": ["files"], "summary": "reads local files",
        "warn": "", "confidence": "medium"}))
    eng = _FakeEngine(good)
    url = "https://github.com/acme/thing"
    r = C.review_url(url, engine=eng)
    assert r["ok"] is True
    assert len(eng.calls) == 1
    call = eng.calls[0]
    # the system prompt IS the bundled skill, not a hand-rolled summary of it
    assert "Do not execute the capability" in call["system"]
    assert url in call["prompt"]
    assert call["allow_tools"] is True, "reviewing a link neeeds to actually fetch it"


def test_review_url_normalizes_a_bad_kind_and_runs_value(_isolated):
    bad = RunResult(ok=True, output=json.dumps({
        "name": "Thing", "kind": "not-a-real-kind", "publisher": "",
        "runs": "definitely-not-valid", "touch": ["files", "made-up", "network"],
        "summary": "s", "warn": "", "confidence": "low"}))
    r = C.review_url("https://example.com/x", engine=_FakeEngine(bad))
    assert r["ok"] is True
    assert r["kind"] == "extensions", "an unrecognised kind falls back rather than corrupting the record"
    assert r["runs"] == "", "an unrecognised runs value is dropped rather than trusted verbatim"
    assert r["touch"] == ["files", "network"], "only the three real values survive"


def test_review_url_falls_back_to_the_host_when_the_agent_names_nothing():
    good = RunResult(ok=True, output=json.dumps({"kind": "extensions"}))
    r = C.review_url("https://example.com/x/y", engine=_FakeEngine(good))
    assert r["ok"] is True and r["name"] == "example.com"


def test_review_url_carries_the_recommendation_through(_isolated):
    """The succinct lead the report card shows first (_cat_review_card) is a field of its own, not
    derived from `summary` at render time — the agent writes both."""
    good = RunResult(ok=True, output=json.dumps({
        "name": "Thing", "kind": "extensions", "publisher": "Acme", "runs": "code",
        "touch": ["files"], "recommendation": "Reads your files. Nothing surprising.",
        "summary": "reads local files\n\nfull evidence here", "warn": "", "confidence": "medium"}))
    r = C.review_url("https://github.com/acme/thing", engine=_FakeEngine(good))
    assert r["ok"] is True
    assert r["recommendation"] == "Reads your files. Nothing surprising."


def test_review_url_defaults_a_missing_recommendation_to_empty(_isolated):
    good = RunResult(ok=True, output=json.dumps(
        {"name": "Thing", "kind": "extensions", "summary": "s", "warn": "", "confidence": "low"}))
    r = C.review_url("https://github.com/acme/thing", engine=_FakeEngine(good))
    assert r["ok"] is True
    assert r["recommendation"] == ""


def test_review_url_carries_the_risk_bucket_through(_isolated):
    good = RunResult(ok=True, output=json.dumps({
        "name": "Thing", "kind": "extensions", "runs": "code", "touch": ["shell"],
        "risk": "high", "recommendation": "r", "summary": "s", "warn": "", "confidence": "high"}))
    r = C.review_url("https://github.com/acme/thing", engine=_FakeEngine(good))
    assert r["ok"] is True
    assert r["risk"] == "high"


def test_review_url_blanks_an_invalid_risk_value(_isolated):
    good = RunResult(ok=True, output=json.dumps({
        "name": "Thing", "kind": "extensions", "risk": "catastrophic",
        "summary": "s", "warn": "", "confidence": "low"}))
    r = C.review_url("https://github.com/acme/thing", engine=_FakeEngine(good))
    assert r["ok"] is True
    assert r["risk"] == "", "an unrecognised risk word is dropped rather than trusted verbatim"


def test_review_url_surfaces_an_engine_failure():
    eng = _FakeEngine(RunResult(ok=False, error="claude timed out after 300s"))
    r = C.review_url("https://example.com/x", engine=eng)
    assert r["ok"] is False and "timed out" in r["error"]


def test_review_url_surfaces_output_it_cannot_parse():
    eng = _FakeEngine(RunResult(ok=True, output="I looked at it and it seems fine, no concerns."))
    r = C.review_url("https://example.com/x", engine=eng)
    assert r["ok"] is False and "try" in r["error"].lower()


# --- add_link_to_realm -----------------------------------------------------------------------------

@pytest.fixture
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "_dir", lambda: tmp_path / "catalogue")
    monkeypatch.setattr(C, "_marketplaces_dir", lambda: tmp_path / "marketplaces")
    return tmp_path


@pytest.fixture
def realm(tmp_path):
    r = tmp_path / "realm"
    r.mkdir()
    (r / "realm.json").write_text(json.dumps({"name": "Test"}), encoding="utf-8")
    return r


def _review(**over):
    r = {"ok": True, "name": "Weather MCP", "kind": "connectors", "publisher": "Acme",
         "runs": "service", "touch": ["network"], "summary": "reaches api.weather.example over https",
         "warn": "", "confidence": "medium", "homepage": "https://github.com/acme/weather-mcp"}
    r.update(over)
    return r


def test_add_link_to_realm_requires_a_successful_review(realm):
    r = C.add_link_to_realm(realm, "https://x.example/y", {"ok": False, "error": "boom"})
    assert r["ok"] is False and "Review" in r["error"]


def test_add_link_to_realm_writes_the_record(realm):
    url = "https://github.com/acme/weather-mcp"
    r = C.add_link_to_realm(realm, url, _review())
    assert r["ok"] is True and r["kind"] == "connectors"
    tk = json.loads((realm / "realm.json").read_text(encoding="utf-8"))["toolkit"]
    it = tk["connectors"][0]
    assert it["name"] == "Weather MCP"
    assert it["url"] == url
    assert it["enabled"] is False, "lands off, same promise as add_to_realm"
    # the review's findings feed the declared-vs-observed panel (_cap_prov) directly — no
    # separate re-scan needed before the owner sees something real there
    assert it["observed"] == "reaches api.weather.example over https"
    assert it["runs"] == "service" and it["touch"] == ["network"]
    assert it["inspected"] is True


def test_add_link_to_realm_prefers_the_recommendation_for_the_description(realm):
    r = C.add_link_to_realm(realm, "https://x.example/y",
                            _review(recommendation="Talks to a weather API over https. No surprises."))
    tk = json.loads((realm / "realm.json").read_text(encoding="utf-8"))["toolkit"]
    it = tk[r["kind"]][0]
    assert it["description"] == "Talks to a weather API over https. No surprises."
    assert it["recommendation"] == "Talks to a weather API over https. No surprises."
    # the full evidence report still feeds the declared-vs-observed panel, unchanged
    assert it["observed"] == "reaches api.weather.example over https"


def test_add_link_to_realm_falls_back_to_summary_with_no_recommendation(realm):
    r = C.add_link_to_realm(realm, "https://x.example/y", _review())     # no recommendation key
    tk = json.loads((realm / "realm.json").read_text(encoding="utf-8"))["toolkit"]
    it = tk[r["kind"]][0]
    assert it["description"] == "reaches api.weather.example over https"


def test_add_link_to_realm_stores_the_tier_when_the_review_gave_a_clear_risk(realm):
    r = C.add_link_to_realm(realm, "https://x.example/y", _review(risk="high"))
    tk = json.loads((realm / "realm.json").read_text(encoding="utf-8"))["toolkit"]
    it = tk[r["kind"]][0]
    assert it["tier"] == "red"


def test_add_link_to_realm_leaves_the_tier_unset_with_no_risk_given(realm):
    """Same as every other capability with no verdict: _cap_tier_why derives it from runs/touch
    at render time, rather than this writing a guess of its own."""
    r = C.add_link_to_realm(realm, "https://x.example/y", _review())     # no risk key
    tk = json.loads((realm / "realm.json").read_text(encoding="utf-8"))["toolkit"]
    it = tk[r["kind"]][0]
    assert "tier" not in it


def test_add_link_to_realm_ignores_an_invalid_risk_word(realm):
    r = C.add_link_to_realm(realm, "https://x.example/y", _review(risk="somewhat"))
    tk = json.loads((realm / "realm.json").read_text(encoding="utf-8"))["toolkit"]
    it = tk[r["kind"]][0]
    assert "tier" not in it


def test_add_link_to_realm_carries_a_warning_through(realm):
    r = C.add_link_to_realm(realm, "https://x.example/y",
                            _review(warn="fetches a CDN font on every load, unannounced"))
    assert r["ok"] is True
    tk = json.loads((realm / "realm.json").read_text(encoding="utf-8"))["toolkit"]
    it = tk[r["kind"]][0]
    assert "CDN font" in it["warn"]


def test_add_link_to_realm_dedupes_by_id(realm):
    url = "https://github.com/acme/weather-mcp"
    assert C.add_link_to_realm(realm, url, _review())["ok"] is True
    again = C.add_link_to_realm(realm, url, _review())
    assert again["ok"] is False and "already in this realm" in again["error"]


def test_add_link_to_realm_catches_a_differently_punctuated_duplicate(realm):
    """The reported bug: a capability already in the realm as a catalogue entry — id
    'frontend-design' (a slug), name 'Frontend design' (its display form) — didn't stop a
    bring-a-link review of the very same source from landing as a second entry, because the old
    dedupe compared cap_key's plain lowercase against an already-alnum-stripped id and the dash
    never matched. add_to_realm's own record shape is reproduced here rather than going through
    the catalogue, since that's the shape actually on disk."""
    tk = {"skills": [{"id": "frontend-design", "name": "Frontend design",
                       "catalogue_key": "skills:frontend-design"}]}
    js = json.loads((realm / "realm.json").read_text(encoding="utf-8"))
    js["toolkit"] = tk
    (realm / "realm.json").write_text(json.dumps(js), encoding="utf-8")
    r = C.add_link_to_realm(realm, "https://github.com/anthropics/skills",
                            _review(name="frontend-design", kind="extensions"))
    assert r["ok"] is False and "already in this realm" in r["error"]


def test_add_link_to_realm_checks_every_kind_bucket_not_just_its_own(realm):
    """The existing record may sit under a different kind than this review's own guess — the
    identity check has to look at the whole toolkit, not just the bucket this entry would land in."""
    tk = {"connectors": [{"id": "weather-mcp", "name": "Weather MCP"}]}
    js = json.loads((realm / "realm.json").read_text(encoding="utf-8"))
    js["toolkit"] = tk
    (realm / "realm.json").write_text(json.dumps(js), encoding="utf-8")
    r = C.add_link_to_realm(realm, "https://github.com/acme/weather-mcp",
                            _review(name="Weather MCP", kind="extensions"))    # different kind
    assert r["ok"] is False and "already in this realm" in r["error"]


# --- realms_with_capability -------------------------------------------------------------------

@pytest.fixture
def _two_realms(tmp_path, monkeypatch):
    """Two realms, one holding a capability under its slug id, registered like ARMADA's own
    ~/.armada/realms.json — realms_with_capability reads the registry the same way
    catalogue._known_realms does everywhere else."""
    a = tmp_path / "cabinet2"
    b = tmp_path / "skunkworks"
    a.mkdir()
    b.mkdir()
    (a / "realm.json").write_text(json.dumps({
        "name": "Cabinet2",
        "toolkit": {"skills": [{"id": "frontend-design", "name": "Frontend design"}]}}),
        encoding="utf-8")
    (b / "realm.json").write_text(json.dumps({"name": "Skunkworks", "toolkit": {}}), encoding="utf-8")
    reg = tmp_path / "realms.json"
    reg.write_text(json.dumps([{"name": "Cabinet2", "path": str(a)},
                               {"name": "Skunkworks", "path": str(b)}]), encoding="utf-8")
    # realms_with_capability() is defined in catalogue/realm.py and calls _known_realms() bare, a
    # module-level name it imported from _shared — patching the package re-export (C) alone leaves
    # realm.py's own bound copy untouched (Phase 2, 2.4/2.9's monkeypatch/bare-name trap).
    monkeypatch.setattr(C, "_known_realms", lambda: [str(a), str(b)])
    monkeypatch.setattr(CREALM, "_known_realms", lambda: [str(a), str(b)])
    return a, b


def test_realms_with_capability_finds_a_match_by_name_across_the_punctuation_gap(_two_realms):
    hits = C.realms_with_capability("frontend-design", "https://github.com/anthropics/skills")
    assert [h["name"] for h in hits] == ["Cabinet2"]


def test_realms_with_capability_finds_nothing_for_an_unrelated_link(_two_realms):
    assert C.realms_with_capability("Totally Different Thing", "https://example.com/x") == []


def test_realms_with_capability_can_match_several_realms(tmp_path, monkeypatch):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "realm.json").write_text(json.dumps({
        "name": "A", "toolkit": {"skills": [{"id": "frontend-design", "name": "Frontend design"}]}}),
        encoding="utf-8")
    (b / "realm.json").write_text(json.dumps({
        "name": "B", "toolkit": {"extensions": [{"id": "frontend-design", "name": "Frontend design"}]}}),
        encoding="utf-8")
    monkeypatch.setattr(C, "_known_realms", lambda: [str(a), str(b)])
    monkeypatch.setattr(CREALM, "_known_realms", lambda: [str(a), str(b)])
    hits = C.realms_with_capability("Frontend design", "")
    assert sorted(h["name"] for h in hits) == ["A", "B"]


def test_realms_with_capability_skips_an_unreadable_realm(tmp_path, monkeypatch):
    ghost = tmp_path / "ghost"      # registered, but the folder is gone
    monkeypatch.setattr(C, "_known_realms", lambda: [str(ghost)])
    monkeypatch.setattr(CREALM, "_known_realms", lambda: [str(ghost)])
    assert C.realms_with_capability("anything", "") == []


def test_add_link_to_realm_defaults_an_invalid_kind(realm):
    r = C.add_link_to_realm(realm, "https://x.example/y", _review(kind="nonsense"))
    assert r["ok"] is True and r["kind"] == "extensions"


def test_add_link_to_realm_falls_back_to_the_host_with_no_name(realm):
    r = C.add_link_to_realm(realm, "https://example.com/pkg", _review(name=""))
    assert r["ok"] is True
    tk = json.loads((realm / "realm.json").read_text(encoding="utf-8"))["toolkit"]
    it = tk[r["kind"]][0]
    assert "example.com" in it["name"]


def test_add_link_to_realm_needs_a_realm(tmp_path):
    r = C.add_link_to_realm(tmp_path / "nope", "https://x.example/y", _review())
    assert r["ok"] is False and "realm.json" in r["error"]
