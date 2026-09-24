"""The capability catalogue — what you could add, normalised from three very different sources.

Two are mirrored into a local index because they are small and curated; the MCP registry is
searched live because it holds over twelve thousand self-published servers, which is not a thing
anyone browses. These tests mostly protect that split, and the rule that a source which fails
keeps its last good data instead of silently shrinking the catalogue.
"""
import json

import pytest

from armada import catalogue as C
from armada import util
from armada.catalogue import _shared as CSHARED, sources as CSRC, realm as CREALM


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    """Never read or write the developer's real ~/.armada or ~/.claude.

    catalogue.py is now a package (_shared.py/sources.py/realm.py, Phase 2, 2.4/2.9). Each of these
    names is called bare from more than one of those modules — a `from ._shared import _dir` inside
    sources.py binds sources.py's OWN copy, so patching only armada.catalogue._dir (the package
    re-export) leaves that copy pointed at the real machine. Every module that resolves a name bare
    has to be patched too. See catalogue/__init__.py's module docstring.
    """
    monkeypatch.setattr(C, "_dir", lambda: tmp_path / "catalogue")
    monkeypatch.setattr(CSHARED, "_dir", lambda: tmp_path / "catalogue")
    monkeypatch.setattr(CSRC, "_dir", lambda: tmp_path / "catalogue")
    monkeypatch.setattr(C, "_marketplaces_dir", lambda: tmp_path / "marketplaces")
    monkeypatch.setattr(CSRC, "_marketplaces_dir", lambda: tmp_path / "marketplaces")
    monkeypatch.setattr(CREALM, "_marketplaces_dir", lambda: tmp_path / "marketplaces")
    monkeypatch.setattr(C, "_get_json", lambda url: None)      # offline unless a test says otherwise
    monkeypatch.setattr(CSHARED, "_get_json", lambda url: None)
    monkeypatch.setattr(CSRC, "_get_json", lambda url: None)
    monkeypatch.setattr(CREALM, "_get_json", lambda url: None)
    monkeypatch.setattr(C, "_skill_roots", lambda: [])          # no skills of your own unless asked
    monkeypatch.setattr(CSRC, "_skill_roots", lambda: [])
    return tmp_path


def _marketplace(tmp_path, name="official", plugins=None):
    d = tmp_path / "marketplaces" / name / ".claude-plugin"
    d.mkdir(parents=True, exist_ok=True)
    (d / "marketplace.json").write_text(json.dumps({
        "name": name, "owner": {"name": "Anthropic"},
        "plugins": plugins if plugins is not None else [
            {"name": "code-review", "description": "Reviews pull requests",
             "category": "productivity", "author": {"name": "Anthropic"},
             "source": "./plugins/code-review"},
            {"name": "acme-db", "description": "Talks to Acme",
             "category": "database", "author": "Acme Corp",
             "source": {"source": "url", "url": "https://github.com/acme/x.git"}},
        ]}), encoding="utf-8")


# --- the mirrored sources ------------------------------------------------------------------------

def test_marketplace_plugins_are_read_from_the_local_clone(_isolated):
    _marketplace(_isolated)
    entries, note, _ok, _lab = C.from_marketplaces()
    assert len(entries) == 2
    cr = next(e for e in entries if e["id"] == "code-review")
    assert cr["kind"] == "plugins" and cr["source"] == C.marketplace_source("official")
    assert cr["author"] == "Anthropic" and cr["category"] == "productivity"
    assert cr["curated"] == C.CURATED_OFFICIAL, "a curated directory is not an open registry"
    assert cr["install"]["marketplace"] == "official" and cr["install"]["plugin"] == "code-review"


def test_author_survives_both_shapes(_isolated):
    """Some entries carry {"author": {"name": ...}}, some a bare string."""
    _marketplace(_isolated)
    by_id = {e["id"]: e for e in C.from_marketplaces()[0]}
    assert by_id["code-review"]["author"] == "Anthropic"
    assert by_id["acme-db"]["author"] == "Acme Corp"


def test_every_configured_marketplace_counts_not_just_the_official_one(_isolated):
    _marketplace(_isolated, "official")
    _marketplace(_isolated, "mine", [{"name": "custom-thing", "description": "d"}])
    ids = {e["id"] for e in C.from_marketplaces()[0]}
    assert "custom-thing" in ids and "code-review" in ids


def test_a_corrupt_marketplace_manifest_is_skipped_not_fatal(_isolated):
    _marketplace(_isolated, "good")
    bad = _isolated / "marketplaces" / "bad" / ".claude-plugin"
    bad.mkdir(parents=True)
    (bad / "marketplace.json").write_text("{not json", encoding="utf-8")
    entries, _n, _ok, _lab = C.from_marketplaces()
    assert {e["id"] for e in entries} == {"code-review", "acme-db"}


def test_no_marketplaces_at_all_is_not_an_error(_isolated):
    """A machine can legitimately have none set up. Reporting that as a failure would put a red
    mark on the catalogue job forever on a machine where nothing is wrong."""
    entries, note, answered, labels = C.from_marketplaces()
    assert entries == [] and "no marketplaces" in note and answered is True
    C.refresh()
    assert C.load()["sources"][C.MARKETPLACE]["ok"] is True


def test_skills_come_back_as_skills(_isolated, monkeypatch):
    _skills_payload = [
        {"type": "dir", "name": "canvas-design", "html_url": "https://x/1"},
        {"type": "file", "name": "README.md"},
    ]
    monkeypatch.setattr(C, "_get_json", lambda url: _skills_payload)
    monkeypatch.setattr(CSHARED, "_get_json", lambda url: _skills_payload)
    monkeypatch.setattr(CSRC, "_get_json", lambda url: _skills_payload)
    monkeypatch.setattr(CREALM, "_get_json", lambda url: _skills_payload)
    entries, _n, _ok, _lab = C.from_skills()
    assert len(entries) == 1
    assert entries[0]["kind"] == "skills" and entries[0]["author"] == "Anthropic"
    assert entries[0]["curated"] == C.CURATED_OFFICIAL


# --- the index ------------------------------------------------------------------------------------

def test_refresh_writes_an_index_that_loads_back(_isolated):
    _marketplace(_isolated)
    r = C.refresh()
    assert r["total"] == 2
    assert {e["id"] for e in C.load()["entries"]} == {"code-review", "acme-db"}


def test_a_source_that_fails_keeps_its_last_good_data(_isolated, monkeypatch):
    """An empty fetch is far more often a network blip than a source that genuinely emptied. The
    catalogue going quietly short is worse than it being out of date and saying so."""
    _marketplace(_isolated)
    monkeypatch.setattr(C, "_get_json", lambda url: [{"type": "dir", "name": "docx"}])
    monkeypatch.setattr(CSHARED, "_get_json", lambda url: [{"type": "dir", "name": "docx"}])
    monkeypatch.setattr(CSRC, "_get_json", lambda url: [{"type": "dir", "name": "docx"}])
    monkeypatch.setattr(CREALM, "_get_json", lambda url: [{"type": "dir", "name": "docx"}])
    C.refresh()
    assert len(C.load()["entries"]) == 3
    monkeypatch.setattr(C, "_get_json", lambda url: None)      # skills source goes down
    monkeypatch.setattr(CSHARED, "_get_json", lambda url: None)
    monkeypatch.setattr(CSRC, "_get_json", lambda url: None)
    monkeypatch.setattr(CREALM, "_get_json", lambda url: None)
    C.refresh()
    entries = C.load()["entries"]
    assert len(entries) == 3, "the skill stays"
    meta = C.load()["sources"][C.SKILLS]
    assert meta["ok"] is False and "unreachable" in meta["note"]


def test_one_source_failing_does_not_block_the_others(_isolated):
    _marketplace(_isolated)                      # skills is offline via the autouse fixture
    C.refresh()
    assert C.load()["sources"][C.MARKETPLACE]["ok"] is True
    assert C.load()["sources"][C.SKILLS]["ok"] is False
    assert len(C.load()["entries"]) == 2, "the working source still contributes"


def test_health_is_reported_per_source_not_per_marketplace(_isolated):
    """Reading the clones directory either worked or it didn't — it is one act. Which marketplace
    an entry came from is carried on the entry, and named in source_labels."""
    _marketplace(_isolated, "official")
    _marketplace(_isolated, "mine", [{"name": "thing"}])
    C.refresh()
    idx = C.load()
    assert set(idx["sources"]) <= set(C._FETCHERS)
    assert {e["source"] for e in idx["entries"]} == {
        C.marketplace_source("official"), C.marketplace_source("mine")}
    assert idx["source_labels"][C.marketplace_source("mine")] == "mine"


def test_a_marketplace_you_removed_stops_being_listed(_isolated):
    import shutil
    _marketplace(_isolated, "official")
    _marketplace(_isolated, "gone", [{"name": "thing"}])
    C.refresh()
    assert len(C.load()["entries"]) == 3
    shutil.rmtree(_isolated / "marketplaces" / "gone")
    C.refresh()
    assert {e["id"] for e in C.load()["entries"]} == {"code-review", "acme-db"}


def test_the_registry_is_not_mirrored(_isolated):
    """It is searched live. An index that mirrored it would be a stale slice of twelve thousand
    entries presented as though it were the catalogue."""
    _marketplace(_isolated)
    C.refresh()
    assert C.REGISTRY not in C.load()["sources"]
    assert not any(e["source"] == C.REGISTRY for e in C.load()["entries"])


def test_an_old_index_that_mirrored_the_registry_is_pruned(_isolated):
    """Written by the version that did mirror it. Left alone, it would serve that slice forever."""
    d = _isolated / "catalogue"
    d.mkdir(parents=True)
    (d / "index.json").write_text(json.dumps({
        "entries": [{"key": "mcp-registry/connectors/x", "id": "x", "name": "x", "kind": "connectors",
                     "source": C.REGISTRY}],
        "sources": {C.REGISTRY: {"count": 2000, "ok": True, "note": "2000 (capped)"}},
        "fetched": "2026-01-01T00:00:00+00:00"}), encoding="utf-8")
    _marketplace(_isolated)
    C.refresh()
    assert C.REGISTRY not in C.load()["sources"]
    assert not any(e["source"] == C.REGISTRY for e in C.load()["entries"])


def test_age_is_minus_one_before_the_first_fetch(_isolated):
    assert C.age_hours() == -1.0


def test_a_missing_index_loads_as_empty_rather_than_raising(_isolated):
    assert C.load() == {"entries": [], "sources": {}, "fetched": ""}


# --- the live registry search ----------------------------------------------------------------------

_SRV = {"servers": [{"server": {
    "name": "io.github.acme/thing", "title": "Thing", "description": "Does things",
    "version": "1.2.0", "remotes": [{"type": "streamable-http", "url": "https://x/mcp"}]}}],
    "metadata": {"count": 1}}


def test_registry_search_normalises_into_the_same_shape(_isolated, monkeypatch):
    monkeypatch.setattr(C, "_get_json", lambda url: _SRV)
    monkeypatch.setattr(CSHARED, "_get_json", lambda url: _SRV)
    monkeypatch.setattr(CSRC, "_get_json", lambda url: _SRV)
    monkeypatch.setattr(CREALM, "_get_json", lambda url: _SRV)
    entries, note = C.search_registry("thing")
    assert len(entries) == 1
    e = entries[0]
    assert e["kind"] == "connectors" and e["source"] == C.REGISTRY
    assert e["curated"] == C.CURATED_REGISTRY, "listing there implies no review by anyone"
    assert e["author"] == "" and e["category"] == "", "the registry carries neither; don't invent them"
    assert "1 match" in note


def test_a_packaged_server_is_an_extension_not_a_connector(_isolated, monkeypatch):
    """Same rule capscan uses, so a thing doesn't change bucket between here and the realm."""
    _payload = {"servers": [{"server": {
        "name": "local/thing", "description": "", "packages": [{"registryType": "npm"}]}}]}
    monkeypatch.setattr(C, "_get_json", lambda url: _payload)
    monkeypatch.setattr(CSHARED, "_get_json", lambda url: _payload)
    monkeypatch.setattr(CSRC, "_get_json", lambda url: _payload)
    monkeypatch.setattr(CREALM, "_get_json", lambda url: _payload)
    assert C.search_registry("thing")[0][0]["kind"] == "extensions"


def test_an_empty_query_returns_nothing(_isolated, monkeypatch):
    """An open registry has no meaningful first page. Showing an arbitrary alphabetical slice of
    twelve thousand servers as a catalogue would misrepresent what you're looking at."""
    called = []
    monkeypatch.setattr(C, "_get_json", lambda url: called.append(url) or _SRV)
    monkeypatch.setattr(CSHARED, "_get_json", lambda url: called.append(url) or _SRV)
    monkeypatch.setattr(CSRC, "_get_json", lambda url: called.append(url) or _SRV)
    monkeypatch.setattr(CREALM, "_get_json", lambda url: called.append(url) or _SRV)
    assert C.search_registry("   ") == ([], "")
    assert not called, "and it doesn't call out to say so"


def test_an_unreachable_registry_says_so_rather_than_looking_empty(_isolated):
    entries, note = C.search_registry("thing")       # _get_json returns None via the fixture
    assert entries == [] and "be reached" in note   # typographic apostrophe, as everywhere else


def test_more_results_than_one_page_says_to_narrow_the_search(_isolated, monkeypatch):
    monkeypatch.setattr(C, "_get_json", lambda url: dict(_SRV, metadata={"nextCursor": "more"}))
    monkeypatch.setattr(CSHARED, "_get_json", lambda url: dict(_SRV, metadata={"nextCursor": "more"}))
    monkeypatch.setattr(CSRC, "_get_json", lambda url: dict(_SRV, metadata={"nextCursor": "more"}))
    monkeypatch.setattr(CREALM, "_get_json", lambda url: dict(_SRV, metadata={"nextCursor": "more"}))
    assert "narrow the search" in C.search_registry("thing")[1]


# --- filtering ---------------------------------------------------------------------------------------

def _entries(_isolated):
    _marketplace(_isolated)
    C.refresh()
    return C.load()["entries"]


def test_search_matches_name_and_description(_isolated):
    e = _entries(_isolated)
    assert {x["id"] for x in C.search(e, q="pull requests")} == {"code-review"}
    assert {x["id"] for x in C.search(e, q="ACME")} == {"acme-db"}


def test_filters_combine(_isolated):
    e = _entries(_isolated)
    assert C.search(e, author="Anthropic", category="database") == []
    assert len(C.search(e, author="Anthropic", category="productivity")) == 1


def test_facets_only_offer_values_that_exist(_isolated):
    """The sources don't agree on what they carry — the marketplace has authors and categories,
    the registry has neither. A filter offering values that can never match looks broken."""
    e = _entries(_isolated)
    f = C.facets(e)
    assert dict(f["author"]) == {"Anthropic": 1, "Acme Corp": 1}
    assert dict(f["category"]) == {"productivity": 1, "database": 1}
    assert dict(f["kind"]) == {"plugins": 2}
    # registry entries contribute no author/category, so the facet stays empty rather than blank-filled
    reg = C._registry_entry({"name": "x", "description": "", "remotes": [{"url": "u"}]})
    assert C.facets([reg])["author"] == [] and C.facets([reg])["category"] == []


def test_facets_are_alphabetical(_isolated):
    """A dropdown is somewhere you look a value up, and the only order you can guess in advance is
    A–Z. By-frequency means hunting for a name whose position depends on data you can't see."""
    _marketplace(_isolated, "official", [
        {"name": "a", "category": "development"}, {"name": "b", "category": "development"},
        {"name": "c", "category": "design"}])
    C.refresh()
    assert [c for c, _ in C.facets(C.load()["entries"])["category"]] == ["design", "development"]


def test_keys_are_unique_across_sources(_isolated, monkeypatch):
    """A plugin and an MCP server can share a vendor's name; collapsing them would make 'add this
    one' ambiguous at exactly the moment it matters."""
    _marketplace(_isolated, "official", [{"name": "sentry", "description": "p"}])
    monkeypatch.setattr(C, "_get_json", lambda url: [{"type": "dir", "name": "sentry"}])
    monkeypatch.setattr(CSHARED, "_get_json", lambda url: [{"type": "dir", "name": "sentry"}])
    monkeypatch.setattr(CSRC, "_get_json", lambda url: [{"type": "dir", "name": "sentry"}])
    monkeypatch.setattr(CREALM, "_get_json", lambda url: [{"type": "dir", "name": "sentry"}])
    C.refresh()
    keys = [e["key"] for e in C.load()["entries"]]
    assert len(keys) == len(set(keys)) == 2


# --- the daily job ------------------------------------------------------------------------------

def test_the_catalogue_job_is_free_and_daily():
    """It is a git-clone read and one HTTPS call. A job that spends quota has to say so, and this
    one doesn't spend any."""
    from armada import sysjobs
    j = sysjobs._BY_ID["catalogue-refresh"]
    assert j["cost"] == sysjobs.FREE
    assert sysjobs.interval_minutes(j) == 24 * 60


def test_the_catalogue_job_only_touches_metadata(_isolated, monkeypatch):
    """It must never install anything or change a capability you already have — it refreshes the
    list you browse and counts the registry, nothing else."""
    from armada import sysjobs
    calls = []
    monkeypatch.setattr(C, "refresh", lambda: calls.append("refresh") or {"total": 7, "sources": {}})
    monkeypatch.setattr(C, "refresh_registry_count",
                        lambda: calls.append("count") or {"ok": True, "count": 12000})
    r = sysjobs._BY_ID["catalogue-refresh"]["run"](_isolated)
    assert calls == ["refresh", "count"]
    assert r["ok"] and "7 listed" in r["detail"] and "12,000" in r["detail"]


def test_the_catalogue_job_reports_a_source_it_could_not_reach(_isolated, monkeypatch):
    from armada import sysjobs
    monkeypatch.setattr(C, "refresh", lambda: {"total": 297, "sources": {
        C.MARKETPLACE: {"ok": True}, C.SKILLS: {"ok": False}}})
    monkeypatch.setattr(C, "refresh_registry_count", lambda: {"ok": True, "count": 1})
    r = sysjobs._BY_ID["catalogue-refresh"]["run"](_isolated)
    assert r["ok"] is False and C.SKILLS in r["detail"] and "297 listed" in r["detail"]


# --- ordering, post-reframe -------------------------------------------------------------------
# The "Suggested" order (rank/suggested/why_ranked/multi_vendors) is gone — ADR-004 drops browsing,
# so there is no default list left to rank. What replaced it is alphabetical sort at the call site
# (_cat_results in webui/catalogue.py). This section keeps the one invariant worth keeping from
# the old one: nothing here claims a popularity signal neither source actually provides.

def _e(name, author="", key=None, source="marketplace:x"):
    return {"key": key or f"{source}/plugins/{name}", "id": name, "name": name,
            "author": author, "source": source, "kind": "plugins", "description": ""}


def test_the_suggested_order_is_gone():
    """Pinned so a future session doesn't reintroduce it by another name."""
    for gone in ("suggested", "why_ranked", "multi_vendors", "rank"):
        assert not hasattr(C, gone), f"C.{gone} should have been removed with the Suggested order"


def test_nothing_in_the_module_claims_a_popularity_signal():
    """No source provides one. A list that claims popularity reads as a recommendation from
    thousands of other users, and there is no basis for that claim.

    Checks the code rather than the comments — the comments have to be able to explain why we
    don't say it."""
    import ast, inspect
    tree = ast.parse(inspect.getsource(C))
    strings = {n.value.lower() for n in ast.walk(tree)
               if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    names = {n.id.lower() for n in ast.walk(tree) if isinstance(n, ast.Name)}
    names |= {n.name.lower() for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    for bad in ("popular", "top", "stars", "downloads", "trending"):
        assert not any(bad == s for s in strings), f"'{bad}' implies data neither source has"
        assert not any(bad in n for n in names), f"'{bad}' implies data neither source has"


# --- adding to a realm ---------------------------------------------------------------------------

@pytest.fixture
def realm(tmp_path):
    r = tmp_path / "realm"
    r.mkdir()
    (r / "realm.json").write_text(json.dumps({"name": "Test"}), encoding="utf-8")
    return r


def test_adding_puts_it_in_the_right_bucket(_isolated, realm):
    _marketplace(_isolated)
    C.refresh()
    key = C.marketplace_source("official") + "/plugins/code-review"
    assert C.add_to_realm(realm, key)["ok"] is True
    tk = json.loads((realm / "realm.json").read_text(encoding="utf-8"))["toolkit"]
    assert [c["id"] for c in tk["plugins"]] == ["code-review"]


def test_what_is_added_carries_its_provenance(_isolated, realm):
    """made_by and curated are what _cap_tier reads. Dropping them on the way in would make every
    added capability an unknown, which is the omission bug in a new coat."""
    _marketplace(_isolated)
    C.refresh()
    C.add_to_realm(realm, C.marketplace_source("official") + "/plugins/code-review")
    it = json.loads((realm / "realm.json").read_text(encoding="utf-8"))["toolkit"]["plugins"][0]
    assert it["made_by"] == "Anthropic" and it["curated"] == C.CURATED_OFFICIAL
    assert it["catalogue_key"] == C.marketplace_source("official") + "/plugins/code-review"


def test_an_added_capability_reaches_no_agent_until_you_say_so(_isolated, realm):
    """The grant model is the point. An add that silently handed it to every agent would undo it."""
    from armada import capabilities as caps
    _marketplace(_isolated)
    C.refresh()
    C.add_to_realm(realm, C.marketplace_source("official") + "/plugins/code-review")
    (realm / "agents" / "warren").mkdir(parents=True)
    (realm / "agents" / "warren" / "agent.json").write_text(
        json.dumps({"id": "warren", "display": "Warren"}), encoding="utf-8")
    usable = caps.usable(realm, "warren")
    assert not any(usable.get(k) for k in caps.KINDS), "ungranted means unusable"


def test_adding_the_same_thing_twice_is_refused(_isolated, realm):
    _marketplace(_isolated)
    C.refresh()
    C.add_to_realm(realm, C.marketplace_source("official") + "/plugins/code-review")
    r = C.add_to_realm(realm, C.marketplace_source("official") + "/plugins/code-review")
    assert r["ok"] is False and "already in this realm" in r["error"]


def test_adding_something_the_catalogue_no_longer_lists(_isolated, realm):
    r = C.add_to_realm(realm, C.marketplace_source("official") + "/plugins/vanished")
    assert r["ok"] is False and "Refresh" in r["error"]


def test_a_registry_server_lands_as_a_connector(_isolated, realm, monkeypatch):
    """The kind travels with the entry, so a thing doesn't change bucket between the catalogue and
    the realm it lands in."""
    monkeypatch.setattr(C, "_get_json", lambda url: _SRV)
    monkeypatch.setattr(CSHARED, "_get_json", lambda url: _SRV)
    monkeypatch.setattr(CSRC, "_get_json", lambda url: _SRV)
    monkeypatch.setattr(CREALM, "_get_json", lambda url: _SRV)
    entries, _ = C.search_registry("thing")
    monkeypatch.setattr(C, "find", lambda key, extra=None: entries[0])
    monkeypatch.setattr(CREALM, "find", lambda key, extra=None: entries[0])
    C.add_to_realm(realm, entries[0]["key"])
    tk = json.loads((realm / "realm.json").read_text(encoding="utf-8"))["toolkit"]
    assert "connectors" in tk and tk["connectors"][0]["curated"] == C.CURATED_REGISTRY


def test_a_realm_without_realm_json_is_refused_not_crashed(_isolated, tmp_path):
    assert C.add_to_realm(tmp_path / "nope", "x")["ok"] is False


# --- adding something the catalogue only knows live -----------------------------------------------

def test_a_live_registry_result_can_be_added(_isolated, realm, monkeypatch):
    """The bug: the registry is searched and never mirrored, so a result you are looking at exists
    only in the page that rendered it. find() couldn't see it and every add failed with "no longer
    in the catalogue"."""
    monkeypatch.setattr(C, "_get_json", lambda url: _SRV)
    monkeypatch.setattr(CSHARED, "_get_json", lambda url: _SRV)
    monkeypatch.setattr(CSRC, "_get_json", lambda url: _SRV)
    monkeypatch.setattr(CREALM, "_get_json", lambda url: _SRV)
    key = "mcp-registry/connectors/io.github.acme/thing"
    assert C.find(key) is not None, "resolved by asking the registry again"
    assert C.add_to_realm(realm, key)["ok"] is True
    tk = json.loads((realm / "realm.json").read_text(encoding="utf-8"))["toolkit"]
    assert tk["connectors"][0]["id"] == "io.github.acme/thing"


def test_the_registry_lookup_only_accepts_an_exact_name(_isolated, monkeypatch):
    """A search for a name can return near matches. Installing whichever one came back first would
    be a different capability than the one you clicked."""
    monkeypatch.setattr(C, "_get_json", lambda url: _SRV)
    monkeypatch.setattr(CSHARED, "_get_json", lambda url: _SRV)
    monkeypatch.setattr(CSRC, "_get_json", lambda url: _SRV)
    monkeypatch.setattr(CREALM, "_get_json", lambda url: _SRV)
    assert C.lookup_registry("io.github.acme/thing") is not None
    assert C.lookup_registry("io.github.acme/thing-else") is None


# --- knowing what you already have ----------------------------------------------------------------

def _realm_with(tmp_path, name, caps_):
    r = tmp_path / name
    r.mkdir(parents=True, exist_ok=True)
    (r / "realm.json").write_text(json.dumps(
        {"name": name, "toolkit": {"connectors": caps_}}), encoding="utf-8")
    return r


def test_the_same_capability_under_three_different_names_is_recognised(_isolated, tmp_path):
    """IBKR is `com.ibkr/interactive-brokers-ibkr` in the registry, `Interactive Brokers (IBKR)` as
    its title, and `claude.ai Interactive Brokers (IBKR)` once Claude has connected it. Comparing
    ids alone said a connector in daily use wasn't in the realm."""
    r = _realm_with(tmp_path, "Cabinet", [
        {"id": "claude_ai_Interactive_Brokers_IBKR", "name": "claude.ai Interactive Brokers (IBKR)"}])
    e = C._entry(C.REGISTRY, "connectors", "com.ibkr/interactive-brokers-ibkr",
                 "Interactive Brokers (IBKR)")
    assert C.installed_keys([r], [e]) == {e["key"]: ["Cabinet"]}


def test_a_catalogue_key_recorded_on_add_beats_any_name_guess(_isolated, tmp_path):
    e = C._entry("marketplace:x", "connectors", "weird-id", "Nothing Alike")
    r = _realm_with(tmp_path, "Cabinet", [{"id": "other", "catalogue_key": e["key"]}])
    assert C.installed_keys([r], [e]) == {e["key"]: ["Cabinet"]}


def test_short_shared_tails_do_not_count_as_a_match(_isolated, tmp_path):
    """"mcp", "api", "ai" are in half the index. Below the floor, containment means nothing."""
    r = _realm_with(tmp_path, "Cabinet", [{"id": "my-mcp", "name": "my mcp"}])
    e = C._entry(C.REGISTRY, "connectors", "someone/other-mcp", "Other MCP")
    assert C.installed_keys([r], [e]) == {}


def test_an_unreadable_realm_just_contributes_no_hints(_isolated, tmp_path):
    assert C.installed_keys([tmp_path / "nope"], [C._entry("s", "skills", "x", "x")]) == {}


# --- skills you wrote yourself ----------------------------------------------------------------------

def _skill(root, name, desc="Does a thing"):
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {desc}\n---\n\nBody.\n",
                                encoding="utf-8")
    return d


def test_your_own_skills_are_listed_so_they_can_move_realms(_isolated, monkeypatch):
    """A skill written for one agent in one realm is invisible everywhere else, and the only way to
    reuse it is to know where the folder is and copy it by hand."""
    root = _isolated / "mine"
    _skill(root, "tax-notes", "How we file")
    monkeypatch.setattr(C, "_skill_roots", lambda: [(root, "Cabinet")])
    monkeypatch.setattr(CSRC, "_skill_roots", lambda: [(root, "Cabinet")])
    entries, _n, ok, _l = C.from_mine()
    assert ok and len(entries) == 1
    e = entries[0]
    assert e["kind"] == "skills" and e["source"] == C.MINE
    assert e["author"] == "You" and e["description"] == "How we file"
    assert e["install"]["from_realm"] == "Cabinet"


def test_your_own_skill_is_trusted(_isolated, monkeypatch):
    """You wrote it. _cap_made reads source == custom, which add_to_realm sets for these."""
    from armada.webui.capabilities import _cap_tier
    root = _isolated / "mine"
    _skill(root, "tax-notes")
    monkeypatch.setattr(C, "_skill_roots", lambda: [(root, "Cabinet")])
    monkeypatch.setattr(CSRC, "_skill_roots", lambda: [(root, "Cabinet")])
    C.refresh()
    r = _isolated / "target"
    r.mkdir()
    (r / "realm.json").write_text(json.dumps({"name": "Other"}), encoding="utf-8")
    assert C.add_to_realm(r, C.load()["entries"][0]["key"])["ok"] is True
    it = json.loads((r / "realm.json").read_text(encoding="utf-8"))["toolkit"]["skills"][0]
    assert _cap_tier(it) == "green"


def test_adding_your_own_skill_copies_the_folder(_isolated, monkeypatch):
    """The entry alone would be a listing pointing at nothing, and an export of the realm would
    carry a skill that isn't there."""
    root = _isolated / "mine"
    _skill(root, "tax-notes")
    monkeypatch.setattr(C, "_skill_roots", lambda: [(root, "Cabinet")])
    monkeypatch.setattr(CSRC, "_skill_roots", lambda: [(root, "Cabinet")])
    C.refresh()
    r = _isolated / "target"
    r.mkdir()
    (r / "realm.json").write_text(json.dumps({"name": "Other"}), encoding="utf-8")
    C.add_to_realm(r, C.load()["entries"][0]["key"])
    assert (r / "skills" / "tax-notes" / "SKILL.md").is_file()


def test_a_skill_whose_folder_has_gone_says_so(_isolated, monkeypatch):
    import shutil
    root = _isolated / "mine"
    _skill(root, "tax-notes")
    monkeypatch.setattr(C, "_skill_roots", lambda: [(root, "Cabinet")])
    monkeypatch.setattr(CSRC, "_skill_roots", lambda: [(root, "Cabinet")])
    C.refresh()
    shutil.rmtree(root / "tax-notes")
    r = _isolated / "target"
    r.mkdir()
    (r / "realm.json").write_text(json.dumps({"name": "Other"}), encoding="utf-8")
    res = C.add_to_realm(r, C.load()["entries"][0]["key"])
    assert res["ok"] is False and "no longer on this computer" in res["error"]


# --- source naming -----------------------------------------------------------------------------------

def test_a_marketplace_is_named_not_called_marketplace(_isolated):
    """"Marketplace" isn't a source: a machine can have several, and which one an entry came from
    is the whole provenance story."""
    _marketplace(_isolated, "claude-plugins-official")
    C.refresh()
    idx = C.load()
    src = C.marketplace_source("claude-plugins-official")
    assert C.source_label(src, idx["source_labels"]) == "Claude plugin marketplace"


def test_an_unknown_marketplace_falls_back_to_its_own_name(_isolated):
    _marketplace(_isolated, "someone-elses")
    C.refresh()
    idx = C.load()
    assert C.source_label(C.marketplace_source("someone-elses"), idx["source_labels"]) == "someone-elses"


# --- inspection at add time -------------------------------------------------------------------
# Worked out when you add something, not eagerly for a catalogue of thousands, and only from
# evidence: a transport, a folder on disk, a declared component. The answer sets the risk tier,
# which is the only reason to do it before you decide whether to switch the thing on.

def _plugin(tmp_path, name, mp="official", **dirs):
    d = tmp_path / "marketplaces" / mp / "plugins" / name
    d.mkdir(parents=True, exist_ok=True)
    for sub in dirs.get("subdirs", ()):
        (d / sub).mkdir(exist_ok=True)
    if dirs.get("mcp") is not None:
        (d / ".mcp.json").write_text(json.dumps({"mcpServers": dirs["mcp"]}), encoding="utf-8")
    return d


def _entry_for(name, mp="official", **install):
    return C._entry(C.marketplace_source(mp), "plugins", name, name,
                    install=dict({"marketplace": mp, "plugin": name}, **install))


def test_a_remote_mcp_server_exchanges_data_with_a_service(_isolated):
    e = C._entry(C.REGISTRY, "connectors", "x", "X", install={"remotes": [{"url": "https://x"}]})
    assert C.inspect(e) == {"runs": "service", "touch": ["network"], "inspected": True,
                            "detail": "remote MCP server"}


def test_a_packaged_mcp_server_runs_code_here(_isolated):
    e = C._entry(C.REGISTRY, "extensions", "x", "X", install={"packages": [{"registryType": "npm"}]})
    got = C.inspect(e)
    assert got["runs"] == "code" and set(got["touch"]) == {"files", "network"}


def test_a_skill_executes_nothing(_isolated):
    """The one kind that can honestly come out Trusted without anyone opening it: it is markdown
    an agent reads."""
    e = C._entry(C.SKILLS, "skills", "x", "X")
    assert C.inspect(e)["runs"] == "reads" and C.inspect(e)["touch"] == []


def test_hooks_are_found_by_opening_the_plugin(_isolated):
    """The thing we are really looking for. Hooks run on the engine's lifecycle events without any
    agent asking, and nothing in the listing metadata mentions them."""
    _plugin(_isolated, "hookify", subdirs=("hooks", "agents"))
    got = C.inspect(_entry_for("hookify"))
    assert "hooks" in got["touch"] and got["inspected"] is True
    assert "hooks" in got["detail"]


def test_a_bundled_mcp_server_is_found_too(_isolated):
    _plugin(_isolated, "withmcp", mcp={"s": {"command": "node", "args": []}})
    got = C.inspect(_entry_for("withmcp"))
    assert got["runs"] == "code" and set(got["touch"]) == {"files", "network"}


def test_a_bundled_remote_server_is_a_service_not_local_code(_isolated):
    _plugin(_isolated, "remote", mcp={"s": {"type": "http", "url": "https://x/mcp"}})
    got = C.inspect(_entry_for("remote"))
    assert got["runs"] == "service" and got["touch"] == ["network"]


def test_a_language_server_runs_code_even_though_its_folder_is_empty(_isolated):
    """typescript-lsp's directory is a LICENSE and a README — the binary it launches is declared in
    the marketplace manifest. Without carrying that, a plugin that starts a process on your machine
    inspected as "nothing that executes"."""
    _plugin(_isolated, "typescript-lsp")
    got = C.inspect(_entry_for("typescript-lsp", lspServers={"typescript": {"command": "tsserver"}}))
    assert got["runs"] == "code" and "files" in got["touch"]
    assert "language server" in got["detail"]


def test_a_plugin_whose_files_are_elsewhere_is_not_guessed_at(_isolated):
    """244 of the marketplace's entries are a git URL and nothing more. "Not looked at" is a true
    answer; an empty ability list that reads as "harmless" is not."""
    got = C.inspect(_entry_for("remote-only"))
    assert got["inspected"] is False and got["runs"] == "" and got["touch"] == []
    from armada.webui.capabilities import _cap_tier
    assert _cap_tier({"runs": "", "touch": [], "source": "3p"}) == "amber"


def test_adding_records_what_was_found_so_the_tier_is_real(_isolated, realm):
    from armada.webui.capabilities import _cap_tier
    _marketplace(_isolated, "official", [{"name": "hookify", "description": "d"}])
    _plugin(_isolated, "hookify", subdirs=("hooks",))
    C.refresh()
    key = C.marketplace_source("official") + "/plugins/hookify"
    r = C.add_to_realm(realm, key)
    assert r["ok"] and r["inspected"] is True
    it = json.loads((realm / "realm.json").read_text(encoding="utf-8"))["toolkit"]["plugins"][0]
    assert it["touch"] == ["hooks"] and it["inspect_note"]
    assert _cap_tier(it) == "red", "the risk level is on the card before you switch it on"


def test_what_you_add_arrives_switched_off(_isolated, realm):
    """Adding is "I want to look at this", not "I want my agents using it"."""
    _marketplace(_isolated)
    C.refresh()
    C.add_to_realm(realm, C.marketplace_source("official") + "/plugins/code-review")
    it = json.loads((realm / "realm.json").read_text(encoding="utf-8"))["toolkit"]["plugins"][0]
    assert it["enabled"] is False and it["added"]


# --- the "new" badge -------------------------------------------------------------------------------

def _realm_obj(members=()):
    class _A:
        def __init__(self, i):
            self.id, self.display, self.is_coordinator = i, i.title(), False
    class _R:
        pass
    r = _R()
    r.members = [_A(m) for m in members]
    return r


def test_new_clears_by_being_put_to_work_not_by_waiting(_isolated, realm, monkeypatch):
    """A capability added a fortnight ago and never wired up is exactly the loose end worth
    showing, so this is a state you leave by doing something rather than a timer."""
    from armada.webui import capabilities as W
    from armada import capabilities as caps
    it = {"id": "x", "name": "X", "added": "2026-01-01T00:00:00+00:00", "enabled": False}
    r = _realm_obj(["warren"])
    assert W._cap_is_new(it, r, realm) is True
    it["enabled"] = True
    monkeypatch.setattr(caps, "granted_keys", lambda root, aid: set())
    assert W._cap_is_new(it, r, realm) is True, "on, but nobody can use it"
    monkeypatch.setattr(caps, "granted_keys", lambda root, aid: {caps.cap_key(it)})
    assert W._cap_is_new(it, r, realm) is False


def test_the_coordinator_does_not_clear_the_new_badge(_isolated, realm, monkeypatch):
    """It can use everything by virtue of the role, so counting it would clear the badge the
    instant anything was added."""
    from armada.webui import capabilities as W
    from armada import capabilities as caps
    it = {"id": "x", "name": "X", "added": "2026-01-01T00:00:00+00:00", "enabled": True}
    monkeypatch.setattr(caps, "granted_keys", lambda root, aid: {caps.cap_key(it)})
    assert W._cap_is_new(it, _realm_obj([]), realm) is True, "no members = nobody but the coordinator"


def test_something_that_predates_the_catalogue_is_not_new(_isolated, realm):
    from armada.webui import capabilities as W
    assert W._cap_is_new({"id": "x", "enabled": False}, _realm_obj(["a"]), realm) is False


# --- how big is the registry ----------------------------------------------------------------------

def _pages(monkeypatch, sizes):
    """Fake the registry paging: each call returns the next page."""
    calls = {"n": 0}
    def fake(url):
        i = calls["n"]
        calls["n"] += 1
        if i >= len(sizes):
            return None
        more = i + 1 < len(sizes)
        return {"servers": [{"server": {"name": f"s{i}-{j}"}} for j in range(sizes[i])],
                "metadata": {"nextCursor": f"c{i}" if more else ""}}
    monkeypatch.setattr(C, "_get_json", fake)
    monkeypatch.setattr(CSHARED, "_get_json", fake)
    monkeypatch.setattr(CSRC, "_get_json", fake)
    monkeypatch.setattr(CREALM, "_get_json", fake)
    return calls


def test_the_registry_is_counted_by_paging(_isolated, monkeypatch):
    """The API caps its page size, has no stats endpoint and reports no total — checked, not
    assumed — so a count is ~130 requests. That is daily-job work; the page only ever reads the
    remembered answer."""
    _pages(monkeypatch, [100, 100, 43])
    assert C.count_registry() == (243, False)


def test_a_count_that_hits_the_page_cap_says_so(_isolated, monkeypatch):
    monkeypatch.setattr(C, "_COUNT_MAX_PAGES", 2)
    monkeypatch.setattr(CSRC, "_COUNT_MAX_PAGES", 2)
    _pages(monkeypatch, [100, 100, 100])
    assert C.count_registry() == (200, True)


def test_a_count_cut_off_mid_way_is_a_floor_not_a_total(_isolated, monkeypatch):
    calls = {"n": 0}
    def flaky(url):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"servers": [{"server": {"name": "x"}}] * 100,
                    "metadata": {"nextCursor": "c"}}
        return None
    monkeypatch.setattr(C, "_get_json", flaky)
    monkeypatch.setattr(CSHARED, "_get_json", flaky)
    monkeypatch.setattr(CSRC, "_get_json", flaky)
    monkeypatch.setattr(CREALM, "_get_json", flaky)
    assert C.count_registry() == (100, True), "at least 100, honestly capped"


def test_the_count_is_remembered_on_the_index(_isolated, monkeypatch):
    _marketplace(_isolated)
    C.refresh()
    _pages(monkeypatch, [100, 34])
    assert C.refresh_registry_count() == {"ok": True, "count": 134, "capped": False}
    assert C.registry_count_label() == "134"
    monkeypatch.setattr(C, "_COUNT_MAX_PAGES", 1)
    monkeypatch.setattr(CSRC, "_COUNT_MAX_PAGES", 1)
    _pages(monkeypatch, [100, 100])
    C.refresh_registry_count()
    assert C.registry_count_label() == "100+", "a capped count never claims to be the total"


def test_no_number_before_the_first_count(_isolated):
    """A guess is not a count."""
    assert C.registry_count_label() == ""


def test_an_unreachable_registry_keeps_the_last_count(_isolated, monkeypatch):
    _pages(monkeypatch, [50])
    C.refresh_registry_count()
    monkeypatch.setattr(C, "_get_json", lambda url: None)
    monkeypatch.setattr(CSHARED, "_get_json", lambda url: None)
    monkeypatch.setattr(CSRC, "_get_json", lambda url: None)
    monkeypatch.setattr(CREALM, "_get_json", lambda url: None)
    r = C.refresh_registry_count()
    assert r["ok"] is False
    assert C.registry_count_label() == "50", "yesterday's count beats no count"


# --- a skill you add has to actually arrive -------------------------------------------------------
#
# The bug behind this block: adding an Anthropic skill wrote a catalogue entry and downloaded
# nothing. "View contents" had no file to open — which is how it surfaced — but the quieter half
# was that an agent granted the skill was told it had one the engine could not load. A listing is
# not a capability.

def _skills_repo(monkeypatch, tree: dict, *, fail: set = frozenset()):
    """Fake the GitHub contents API for one skill folder. `tree` maps relative path -> text."""
    dirs: dict = {}
    for rel in tree:
        parts = rel.split("/")
        for i in range(len(parts)):
            dirs.setdefault("/".join(parts[:i]), set()).add(parts[i])

    def listing(prefix: str):
        out = []
        for name in sorted(dirs.get(prefix, ())):
            rel = f"{prefix}/{name}" if prefix else name
            if rel in tree:
                out.append({"name": name, "type": "file", "download_url": f"blob:{rel}"})
            else:
                out.append({"name": name, "type": "dir", "url": f"dir:{rel}"})
        return out

    def get_json(url: str):
        if url.startswith("dir:"):
            return listing(url[4:])
        if "/contents/skills/" in url:
            return listing("")
        return None

    def get_bytes(url: str):
        rel = url[5:]
        if rel in fail:
            return None
        return tree[rel].encode("utf-8")

    monkeypatch.setattr(C, "_get_json", get_json)
    monkeypatch.setattr(CSHARED, "_get_json", get_json)
    monkeypatch.setattr(CSRC, "_get_json", get_json)
    monkeypatch.setattr(CREALM, "_get_json", get_json)
    monkeypatch.setattr(C, "_get_bytes", get_bytes)
    monkeypatch.setattr(CREALM, "_get_bytes", get_bytes)


def _skill_entry(cid="frontend-design", name="Frontend design"):
    return C._entry(C.SKILLS, "skills", cid, name, "Design for the front end",
                    author="Anthropic", curated=C.CURATED_OFFICIAL,
                    install={"repo": "anthropics/skills", "path": cid})


def test_adding_an_anthropic_skill_puts_the_files_in_the_realm(_isolated, realm, monkeypatch):
    e = _skill_entry()
    _skills_repo(monkeypatch, {"SKILL.md": "# Frontend design\n"})
    monkeypatch.setattr(C, "find", lambda key, extra=None: e)
    monkeypatch.setattr(CREALM, "find", lambda key, extra=None: e)
    assert C.add_to_realm(realm, e["key"])["ok"] is True
    md = realm / "skills" / "frontend-design" / "SKILL.md"
    assert md.is_file(), "the skill has to be on disk, not just in the listing"
    assert "Frontend design" in md.read_text(encoding="utf-8")


def test_a_skill_arrives_whole_including_its_subfolders(_isolated, realm, monkeypatch):
    """A skill is a folder: SKILL.md routinely references scripts and templates beside it."""
    e = _skill_entry()
    _skills_repo(monkeypatch, {"SKILL.md": "# x\n", "reference/rules.md": "r",
                               "scripts/run.py": "print(1)"})
    monkeypatch.setattr(C, "find", lambda key, extra=None: e)
    monkeypatch.setattr(CREALM, "find", lambda key, extra=None: e)
    C.add_to_realm(realm, e["key"])
    root = realm / "skills" / "frontend-design"
    assert (root / "reference" / "rules.md").is_file()
    assert (root / "scripts" / "run.py").read_text(encoding="utf-8") == "print(1)"


def test_a_download_that_fails_leaves_nothing_behind(_isolated, realm, monkeypatch):
    """Half a skill is worse than none: it loads, then fails at the step that needed the missing
    piece. Nothing is added unless everything arrived."""
    e = _skill_entry()
    _skills_repo(monkeypatch, {"SKILL.md": "# x\n", "scripts/run.py": "print(1)"},
                 fail={"scripts/run.py"})
    monkeypatch.setattr(C, "find", lambda key, extra=None: e)
    monkeypatch.setattr(CREALM, "find", lambda key, extra=None: e)
    r = C.add_to_realm(realm, e["key"])
    assert r["ok"] is False
    assert not (realm / "skills" / "frontend-design").exists()
    tk = json.loads((realm / "realm.json").read_text(encoding="utf-8")).get("toolkit") or {}
    assert not tk.get("skills"), "a skill that didn't download must not be listed as added"


def test_an_offline_add_says_so_rather_than_adding_an_empty_folder(_isolated, realm, monkeypatch):
    e = _skill_entry()
    monkeypatch.setattr(C, "_get_json", lambda url: None)
    monkeypatch.setattr(CSHARED, "_get_json", lambda url: None)
    monkeypatch.setattr(CSRC, "_get_json", lambda url: None)
    monkeypatch.setattr(CREALM, "_get_json", lambda url: None)
    monkeypatch.setattr(C, "find", lambda key, extra=None: e)
    monkeypatch.setattr(CREALM, "find", lambda key, extra=None: e)
    r = C.add_to_realm(realm, e["key"])
    assert r["ok"] is False and "connection" in r["error"]
    assert not (realm / "skills" / "frontend-design").exists()


def test_a_folder_without_skill_md_is_not_a_skill(_isolated, realm, monkeypatch):
    e = _skill_entry()
    _skills_repo(monkeypatch, {"README.md": "nothing here"})
    monkeypatch.setattr(C, "find", lambda key, extra=None: e)
    monkeypatch.setattr(CREALM, "find", lambda key, extra=None: e)
    assert C.add_to_realm(realm, e["key"])["ok"] is False
    assert not (realm / "skills" / "frontend-design").exists()


def test_the_source_row_names_the_source_it_came_from(_isolated, realm, monkeypatch):
    """The card's Source row used to fall back to "Added & authorised in Claude" — true of things
    discovered from the CLI, false of everything added from the Catalogue."""
    e = _skill_entry()
    _skills_repo(monkeypatch, {"SKILL.md": "# x\n"})
    monkeypatch.setattr(C, "find", lambda key, extra=None: e)
    monkeypatch.setattr(CREALM, "find", lambda key, extra=None: e)
    C.add_to_realm(realm, e["key"])
    it = json.loads((realm / "realm.json").read_text(encoding="utf-8"))["toolkit"]["skills"][0]
    assert it["origin"] == "Anthropic skills"


def test_a_skill_you_wrote_is_still_copied_not_downloaded(_isolated, realm, monkeypatch, tmp_path):
    src = tmp_path / "mine" / "my-skill"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("# Mine\n", encoding="utf-8")
    e = C._entry(C.MINE, "skills", "my-skill", "My skill", install={"path": str(src)})
    monkeypatch.setattr(C, "find", lambda key, extra=None: e)
    monkeypatch.setattr(CREALM, "find", lambda key, extra=None: e)
    monkeypatch.setattr(C, "_get_json", lambda url: pytest.fail("a local skill must not be fetched"))
    monkeypatch.setattr(CSHARED, "_get_json", lambda url: pytest.fail("a local skill must not be fetched"))
    monkeypatch.setattr(CSRC, "_get_json", lambda url: pytest.fail("a local skill must not be fetched"))
    monkeypatch.setattr(CREALM, "_get_json", lambda url: pytest.fail("a local skill must not be fetched"))
    assert C.add_to_realm(realm, e["key"])["ok"] is True
    assert (realm / "skills" / "my-skill" / "SKILL.md").read_text(encoding="utf-8") == "# Mine\n"


@pytest.mark.parametrize("name", ["../evil", "..", "a/b", "a\\b", "", ".hidden"])
def test_a_remote_filename_cannot_escape_the_folder_we_chose(name):
    """These names arrive from a server we don't control and are used to build a path."""
    assert C._safe_name(name) == ""


@pytest.mark.parametrize("name", ["SKILL.md", "run.py", "a-b_c.1.txt"])
def test_ordinary_filenames_still_pass(name):
    assert C._safe_name(name) == name


# --- "You" means you wrote it -------------------------------------------------------------------
#
# Downloading an added Anthropic skill into <realm>/skills put it in the same folder as the skills
# you write there. They are indistinguishable on disk, so "Source: You" started listing other
# people's skills back to you — offering to move a thing to another realm that the other realm can
# already add from its own source, filed under the wrong author.

def _realm_with_skill(tmp_path, sid, *, catalogue_key=None, name="R"):
    r = tmp_path / name
    (r / "skills" / sid).mkdir(parents=True)
    (r / "skills" / sid / "SKILL.md").write_text("---\ndescription: d\n---\nbody\n", encoding="utf-8")
    entry = {"id": sid, "name": sid}
    if catalogue_key:
        entry["catalogue_key"] = catalogue_key
    (r / "realm.json").write_text(
        json.dumps({"name": name, "toolkit": {"skills": [entry]}}), encoding="utf-8")
    return r


def test_a_skill_you_downloaded_is_not_one_you_wrote(_isolated, tmp_path, monkeypatch):
    r = _realm_with_skill(tmp_path, "frontend-design",
                          catalogue_key="anthropic-skills/skills/frontend-design")
    monkeypatch.setattr(C, "_known_realms", lambda: [str(r)])
    monkeypatch.setattr(CSHARED, "_known_realms", lambda: [str(r)])
    monkeypatch.setattr(CREALM, "_known_realms", lambda: [str(r)])
    monkeypatch.setattr(CSRC, "_known_realms", lambda: [str(r)])
    monkeypatch.setattr(C, "_skill_roots", lambda: [(r / "skills", "R")])
    monkeypatch.setattr(CSRC, "_skill_roots", lambda: [(r / "skills", "R")])
    ids = [e["id"] for e in C.from_mine()[0]]
    assert "frontend-design" not in ids


def test_a_skill_you_actually_wrote_still_shows(_isolated, tmp_path, monkeypatch):
    """A hand-written skill has no catalogue entry at all — which is the case this list exists for."""
    r = _realm_with_skill(tmp_path, "house-style")
    monkeypatch.setattr(C, "_known_realms", lambda: [str(r)])
    monkeypatch.setattr(CSHARED, "_known_realms", lambda: [str(r)])
    monkeypatch.setattr(CREALM, "_known_realms", lambda: [str(r)])
    monkeypatch.setattr(CSRC, "_known_realms", lambda: [str(r)])
    monkeypatch.setattr(C, "_skill_roots", lambda: [(r / "skills", "R")])
    monkeypatch.setattr(CSRC, "_skill_roots", lambda: [(r / "skills", "R")])
    assert [e["id"] for e in C.from_mine()[0]] == ["house-style"]


def test_a_skill_moved_from_another_realm_is_still_yours(_isolated, tmp_path, monkeypatch):
    """Copied from your own work in another realm, so it stays under You — the exclusion is about
    where a skill came from, not about whether it has a catalogue entry."""
    r = _realm_with_skill(tmp_path, "house-style", catalogue_key="mine/skills/house-style")
    monkeypatch.setattr(C, "_known_realms", lambda: [str(r)])
    monkeypatch.setattr(CSHARED, "_known_realms", lambda: [str(r)])
    monkeypatch.setattr(CREALM, "_known_realms", lambda: [str(r)])
    monkeypatch.setattr(CSRC, "_known_realms", lambda: [str(r)])
    monkeypatch.setattr(C, "_skill_roots", lambda: [(r / "skills", "R")])
    monkeypatch.setattr(CSRC, "_skill_roots", lambda: [(r / "skills", "R")])
    assert [e["id"] for e in C.from_mine()[0]] == ["house-style"]


def test_a_realm_with_no_toolkit_does_not_break_the_check(_isolated, tmp_path, monkeypatch):
    r = tmp_path / "bare"
    r.mkdir()
    (r / "realm.json").write_text(json.dumps({"name": "bare"}), encoding="utf-8")
    monkeypatch.setattr(C, "_known_realms", lambda: [str(r), str(tmp_path / "gone")])
    monkeypatch.setattr(CSHARED, "_known_realms", lambda: [str(r), str(tmp_path / "gone")])
    monkeypatch.setattr(CREALM, "_known_realms", lambda: [str(r), str(tmp_path / "gone")])
    monkeypatch.setattr(CSRC, "_known_realms", lambda: [str(r), str(tmp_path / "gone")])
    assert C._imported_skill_ids() == set()


# --- counting the registry -------------------------------------------------------------------------

def test_the_count_retries_before_giving_up(_isolated, monkeypatch):
    """The bug: the count ran, the SECOND request came back empty, and the job recorded
    '100, capped' — which the filter then showed as '100+' beside a source holding thousands. A
    hundred back-to-back requests is exactly the pattern a public index rate-limits, and a
    rate-limited page is not the end of the list."""
    monkeypatch.setattr(CSRC.time, "sleep", lambda s: None)
    calls = []

    def flaky(url):
        calls.append(url)
        if len(calls) == 2:
            return None                       # one refusal, mid-walk
        if "cursor" in url:
            return {"servers": [{"server": {"name": "b"}}], "metadata": {}}
        return {"servers": [{"server": {"name": "a"}}], "metadata": {"nextCursor": "c1"}}
    monkeypatch.setattr(C, "_get_json", flaky)
    monkeypatch.setattr(CSHARED, "_get_json", flaky)
    monkeypatch.setattr(CSRC, "_get_json", flaky)
    monkeypatch.setattr(CREALM, "_get_json", flaky)
    n, capped = C.count_registry()
    assert (n, capped) == (2, False), "a single refusal should not end the count"


def test_a_count_that_really_stops_is_marked_capped(_isolated, monkeypatch):
    monkeypatch.setattr(CSRC.time, "sleep", lambda s: None)
    calls = []

    def dies(url):
        calls.append(url)
        if len(calls) == 1:
            return {"servers": [{"server": {"name": "a"}}], "metadata": {"nextCursor": "c1"}}
        return None
    monkeypatch.setattr(C, "_get_json", dies)
    monkeypatch.setattr(CSHARED, "_get_json", dies)
    monkeypatch.setattr(CSRC, "_get_json", dies)
    monkeypatch.setattr(CREALM, "_get_json", dies)
    n, capped = C.count_registry()
    assert (n, capped) == (1, True)
    assert len(calls) == 1 + C._COUNT_RETRIES, "it should have retried before capping"


def test_an_unreachable_registry_counts_as_unknown_not_zero(_isolated, monkeypatch):
    monkeypatch.setattr(CSRC.time, "sleep", lambda s: None)
    monkeypatch.setattr(C, "_get_json", lambda url: None)
    monkeypatch.setattr(CSHARED, "_get_json", lambda url: None)
    monkeypatch.setattr(CSRC, "_get_json", lambda url: None)
    monkeypatch.setattr(CREALM, "_get_json", lambda url: None)
    assert C.count_registry() == (-1, False)
    assert C.registry_count_label({"registry_count": -1}) == ""


def test_the_sample_note_quotes_the_counted_size_not_a_number_in_the_code(_isolated, monkeypatch):
    """It said "over twelve thousand" whatever the registry actually held."""
    _payload = {"servers": [{"server": {"name": "a"}}], "metadata": {}}
    monkeypatch.setattr(C, "_get_json", lambda url: _payload)
    monkeypatch.setattr(CSHARED, "_get_json", lambda url: _payload)
    monkeypatch.setattr(CSRC, "_get_json", lambda url: _payload)
    monkeypatch.setattr(CREALM, "_get_json", lambda url: _payload)
    C._reg_cache.clear()
    C.refresh()
    idx = C.load()
    idx["registry_count"] = 12345
    util.write_json_atomic(C._index_path(), idx)
    C._reg_cache.clear()
    _out, note = C.search_registry("", sample=True)
    assert "12,345" in note and "twelve thousand" not in note


def test_our_own_name_for_a_marketplace_beats_the_stored_one(_isolated):
    """The labels in the index are a snapshot from the last refresh, so a rename here would
    otherwise sit invisible for up to a day."""
    stale = {"marketplace:claude-plugins-official": "Claude marketplace"}
    assert C.source_label(C.marketplace_source("claude-plugins-official"), stale) == \
        "Claude plugin marketplace"
    # a marketplace we have no opinion about still uses whatever it calls itself
    assert C.source_label(C.marketplace_source("acme"), {"marketplace:acme": "Acme"}) == "Acme"


# --- counting the registry ------------------------------------------------------------------------

def test_the_count_ceiling_clears_the_real_registry(_isolated):
    """It was 250 pages — 25,000 servers — and a full walk on 2026-09-20 found 33,657. The count
    stopped dead on the ceiling and reported "25,000+", which reads as a fact about the registry
    and was really "this is as far as we were allowed to look"."""
    assert C._COUNT_MAX_PAGES * C._COUNT_PAGE >= 60000


def test_two_counts_do_not_run_at_once(_isolated, monkeypatch):
    """The daily job and the Refresh button can both ask. A few hundred requests to a public
    index is enough to send once."""
    calls = []
    monkeypatch.setattr(C, "count_registry", lambda: (calls.append(1), (5, False))[1])
    monkeypatch.setattr(CSRC, "count_registry", lambda: (calls.append(1), (5, False))[1])
    real = C._refresh_registry_count

    def reentrant():
        C.refresh_registry_count()          # asked for again while the first is still running
        return real()
    monkeypatch.setattr(C, "_refresh_registry_count", reentrant)
    monkeypatch.setattr(CSRC, "_refresh_registry_count", reentrant)
    C.refresh_registry_count()
    assert len(calls) == 1, f"the registry was walked {len(calls)} times"
