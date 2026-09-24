"""The Catalogue is one list obeying one set of rules.

It used to be two lists rendered one above the other. The mirrored index went through search(),
which honours every filter; the MCP registry was fetched by a call that received only the search
text. So filtering to Extensions returned forty registry entries of which thirty-six were
connectors — and because the registry joined in only when named as the source, CLEARING the source
filter dropped those forty to nothing. Asking for strictly more returned strictly less.

The rule these tests hold: a narrower filter must never return more results than a looser one.
"""
import json
import re

import pytest

from armada import catalogue as C
from armada.catalogue import _shared as CSHARED, sources as CSRC, realm as CREALM
from armada.webui import catalogue as WCAT   # the Catalogue tab's own rendering (Phase 2, 2.4)


def _srv(name, *, remote=True, desc="d"):
    """One registry record in the API's own shape."""
    s = {"name": name, "description": desc, "version": "1.0"}
    s["remotes" if remote else "packages"] = [{"type": "streamable-http", "url": "https://x"}]
    return {"server": s}


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    """Never read or write the developer's real ~/.armada or ~/.claude.

    Patched on every module that resolves the name bare, not just the package re-export — a `from
    ._shared import _dir` inside sources.py binds sources.py's OWN copy, so patching only
    armada.catalogue._dir leaves that copy pointed at the real machine. See catalogue/__init__.py's
    module docstring (Phase 2, 2.4/2.9).
    """
    monkeypatch.setattr(C, "_dir", lambda: tmp_path / "catalogue")
    monkeypatch.setattr(CSHARED, "_dir", lambda: tmp_path / "catalogue")
    monkeypatch.setattr(CSRC, "_dir", lambda: tmp_path / "catalogue")
    monkeypatch.setattr(C, "_marketplaces_dir", lambda: tmp_path / "marketplaces")
    monkeypatch.setattr(CSRC, "_marketplaces_dir", lambda: tmp_path / "marketplaces")
    monkeypatch.setattr(CREALM, "_marketplaces_dir", lambda: tmp_path / "marketplaces")
    monkeypatch.setattr(C, "_get_json", lambda url: None)
    monkeypatch.setattr(CSHARED, "_get_json", lambda url: None)
    monkeypatch.setattr(CSRC, "_get_json", lambda url: None)
    monkeypatch.setattr(CREALM, "_get_json", lambda url: None)
    monkeypatch.setattr(C, "_skill_roots", lambda: [])
    monkeypatch.setattr(CSRC, "_skill_roots", lambda: [])
    C._reg_cache.clear()
    return tmp_path


@pytest.fixture
def wired(_isolated, monkeypatch, tmp_path):
    """A mirrored index of plugins, and a registry of 2 connectors and 2 extensions."""
    from test_catalogue import _marketplace  # noqa — reuse that module's manifest builder
    _marketplace(_isolated)
    C.refresh()
    payload = {"servers": [_srv("acme/remote-one"), _srv("acme/remote-two"),
                           _srv("acme/local-one", remote=False),
                           _srv("acme/local-two", remote=False)]}
    monkeypatch.setattr(C, "_get_json", lambda url: payload)
    monkeypatch.setattr(CSHARED, "_get_json", lambda url: payload)
    monkeypatch.setattr(CSRC, "_get_json", lambda url: payload)
    C._reg_cache.clear()
    return payload


# --- the two reported bugs ------------------------------------------------------------------------

def test_a_type_filter_reaches_registry_results(wired):
    """Picking Extensions returned connectors, because the type never reached the registry leg."""
    reg, _ = C.search_registry("", sample=True)
    ext = C.search(reg, kind="extensions")
    assert {e["id"] for e in ext} == {"acme/local-one", "acme/local-two"}
    con = C.search(reg, kind="connectors")
    assert {e["id"] for e in con} == {"acme/remote-one", "acme/remote-two"}


def test_clearing_the_source_never_loses_results(wired):
    """Connectors and extensions live only in the registry, so 'any source' has to reach it."""
    assert C.registry_wanted("", C.REGISTRY, "") is True
    assert C.registry_wanted("", "", "connectors") is True, \
        "clearing the source dropped the only place connectors come from"
    assert C.registry_wanted("", "", "extensions") is True


def test_naming_another_source_keeps_the_registry_out(wired):
    """'Anthropic skills' means Anthropic skills. Asking for one source is not asking for two."""
    assert C.registry_wanted("thing", C.SKILLS, "") is False
    assert C.registry_wanted("", C.marketplace_source("official"), "connectors") is False


def test_the_registry_is_in_unless_another_source_is_named(wired):
    """The earlier version of this made the registry conditional on a search, which meant an empty
    box showed a sample under "MCP registry" and LESS than that under "all sources" — the reported
    bug again, one cell over."""
    assert C.registry_wanted("", "", "") is True
    assert C.registry_wanted("", "", "skills") is True


def test_an_unreachable_registry_still_leaves_a_browsable_page(wired, realm, monkeypatch):
    """The empty-search view samples the registry (so its Source option isn't a dead end from the
    moment you open the tab — Mihai, 2026-09-21), which means it can now fail. An unreachable
    registry must not blank the page: the mirrored sources still render, with a note saying so."""
    from armada import reader
    monkeypatch.setattr(C, "_get_json", lambda url: None)
    monkeypatch.setattr(CSHARED, "_get_json", lambda url: None)
    monkeypatch.setattr(CSRC, "_get_json", lambda url: None)
    C._reg_cache.clear()
    html = WCAT._cat_results(reader.read(str(realm)), realm)
    assert "code-review" in html, "the mirrored sources are still listed"
    assert "reached" in html, "an unreachable registry should say so, not just show nothing"


# --- the rule, stated as a property ----------------------------------------------------------------

@pytest.fixture
def realm(tmp_path):
    r = tmp_path / "realm"
    r.mkdir()
    (r / "realm.json").write_text(json.dumps({"name": "Test"}), encoding="utf-8")
    return r


def _count(realm_model, root, **kw):
    import re
    h = WCAT._cat_results(realm_model, root, **kw)
    m = re.search(r"of (\d+)</span>", h)
    if m:
        return int(m.group(1))
    return 0 if "Nothing matches" in h else h.count('class="mc-cat-card')


def test_a_narrower_filter_never_returns_more(wired, realm, monkeypatch):
    """The property the old page violated, checked across every source x type pair."""
    from armada import reader
    model = reader.read(str(realm))
    sources = ["", C.REGISTRY, C.marketplace_source("official"), C.SKILLS, C.MINE]
    for kind in ("", "connectors", "extensions", "skills", "plugins"):
        loose = _count(model, realm, kind=kind)
        for s in sources[1:]:
            tight = _count(model, realm, kind=kind, source=s)
            assert tight <= loose, (
                f"source={s!r} kind={kind!r} returned {tight}, more than the {loose} you get "
                f"without naming a source")


def test_registry_entries_join_the_one_ranked_list(wired, realm):
    """Not a second block below the pager: one list, one order, one pager."""
    from armada import reader
    model = reader.read(str(realm))
    html = WCAT._cat_results(model, realm, kind="connectors", q="acme")
    assert "acme/remote-one" in html
    assert html.count('id="cat-results"') == 1
    assert "<span>MCP registry</span>" not in html, "the separate registry block is back"


# --- resilience ------------------------------------------------------------------------------------

def test_a_repeat_query_does_not_hit_the_network_again(wired, monkeypatch):
    """Every filter change re-renders server-side; at typing speed that was a call each time, and
    the registry starts refusing."""
    calls = []
    payload = {"servers": [_srv("acme/remote-one")]}

    def counted(url):
        calls.append(url)
        return payload
    monkeypatch.setattr(C, "_get_json", counted)
    monkeypatch.setattr(CSHARED, "_get_json", counted)
    monkeypatch.setattr(CSRC, "_get_json", counted)
    C._reg_cache.clear()
    C.search_registry("thing")
    C.search_registry("thing")
    C.search_registry("thing")
    assert len(calls) == 1, f"the registry was queried {len(calls)} times for one search"


def test_a_failed_refresh_keeps_the_last_good_answer(wired, monkeypatch):
    """An unreachable registry rendering as zero results is indistinguishable from 'nothing like
    that exists', and the second is a much stronger claim than we can make."""
    payload = {"servers": [_srv("acme/remote-one")]}
    monkeypatch.setattr(C, "_get_json", lambda url: payload)
    monkeypatch.setattr(CSHARED, "_get_json", lambda url: payload)
    monkeypatch.setattr(CSRC, "_get_json", lambda url: payload)
    C._reg_cache.clear()
    first, _ = C.search_registry("thing")
    assert len(first) == 1
    C._reg_cache["thing|100"] = (0, list(first), "1 match")     # expire it
    monkeypatch.setattr(C, "_get_json", lambda url: None)        # ...and make the retry fail
    monkeypatch.setattr(CSHARED, "_get_json", lambda url: None)
    monkeypatch.setattr(CSRC, "_get_json", lambda url: None)
    again, note = C.search_registry("thing")
    assert [e["id"] for e in again] == ["acme/remote-one"]
    assert "couldn" in note, "a stale answer should say it is stale"


def test_with_nothing_cached_an_unreachable_registry_says_so(wired, monkeypatch):
    monkeypatch.setattr(C, "_get_json", lambda url: None)
    monkeypatch.setattr(CSHARED, "_get_json", lambda url: None)
    monkeypatch.setattr(CSRC, "_get_json", lambda url: None)
    C._reg_cache.clear()
    out, note = C.search_registry("thing")
    assert out == [] and "reached" in note


# --- options that would return nothing are greyed --------------------------------------------------
#
# A dropdown offering a choice that can only ever empty the page is a small lie it tells about
# itself: "MCP registry" beside "Skills" reads as though the registry might hold some.

def _empty(realm_model, root, **kw):
    import html as _h
    h = WCAT._cat_results(realm_model, root, **kw)
    m = re.search(r'data-empty="([^"]*)"', h)
    assert m, "the results block carries no availability data"
    return {k: set(v) for k, v in json.loads(_h.unescape(m.group(1))).items()}


def test_the_registry_holds_no_skills_or_plugins(wired, realm):
    """The registry answers for a search the same way it does for the empty-box sample."""
    from armada import reader
    e = _empty(reader.read(str(realm)), realm, source=C.REGISTRY, q="acme")
    assert {"skills", "plugins"} <= e["cat-kind"]
    assert not ({"connectors", "extensions"} & e["cat-kind"])


def test_a_type_greys_the_sources_that_cannot_supply_it(wired, realm):
    from armada import reader
    e = _empty(reader.read(str(realm)), realm, kind="plugins")
    assert C.REGISTRY in e["cat-source"], "the registry has no plugins"
    assert C.marketplace_source("official") not in e["cat-source"]


def test_options_are_costed_against_the_unfiltered_registry(wired, realm):
    """The bug this caught: the availability map was computed from the registry list AFTER it had
    been narrowed to the current type, so with Connectors chosen, Extensions looked empty — while
    actually holding two."""
    from armada import reader
    e = _empty(reader.read(str(realm)), realm, kind="connectors", q="acme")
    assert "extensions" not in e["cat-kind"], \
        "Extensions was greyed out while the registry holds some"


def test_the_current_choice_is_never_greyed(wired, realm):
    """Filtered into a corner, the page still has to show which corner you are in."""
    from armada import reader
    e = _empty(reader.read(str(realm)), realm, source=C.REGISTRY, kind="connectors")
    assert C.REGISTRY not in e.get("cat-source", set())
    assert "connectors" not in e.get("cat-kind", set())


def test_with_no_search_the_registry_still_answers_with_a_sample(wired, realm):
    """Browsing across the whole catalogue is still gone (ADR-004), but the registry itself is
    sampled even with nothing typed — a Source filter you can pick and then watch contribute
    nothing read as broken, not as "search instead" (Mihai, 2026-09-21). So the registry's own
    kinds (connectors, extensions) and the registry as a source are NOT empty here. This fixture
    mirrors only plugins, so mirrored Skills is the one kind that genuinely has nothing to show."""
    from armada import reader
    e = _empty(reader.read(str(realm)), realm)
    assert "skills" in e["cat-kind"]
    assert "connectors" not in e["cat-kind"]
    assert "extensions" not in e["cat-kind"]
    assert C.REGISTRY not in e["cat-source"]


def test_searching_also_lights_the_registry_up(wired, realm):
    """Same fixture, with a search typed: still true — a query doesn't turn the registry off."""
    from armada import reader
    e = _empty(reader.read(str(realm)), realm, q="acme")
    assert "connectors" not in e["cat-kind"]
    assert "extensions" not in e["cat-kind"]
    assert C.REGISTRY not in e["cat-source"]


def test_every_menu_row_carries_its_value(wired, realm):
    """The greying reads data-val. It used to pick the argument back out of the onclick string,
    off by one, silently greying the wrong rows."""
    from armada import reader
    pane = WCAT._catalogue_pane(reader.read(str(realm)), realm)
    # The value argument is a JSON string literal, HTML-escaped (_base._J): &quot;…&quot;.
    rows = re.findall(r'<a data-val="([^"]*)"[^>]*onclick="mcFDPick\(this,\'[^\']*\',&quot;((?:[^&]|&(?!quot;))*)&quot;',
                      pane)
    assert rows, "no menu rows found"
    for attr, arg in rows:
        assert attr == arg, f"data-val {attr!r} disagrees with the onclick value {arg!r}"


# --- the catalogue is the same everywhere ----------------------------------------------------------

def test_the_catalogue_reads_the_same_in_every_realm(wired, tmp_path, monkeypatch):
    """The catalogue is a property of this computer, not of a realm. The only thing a realm
    contributes is the "you already use this" hint on a card — which is exactly why that hint is
    gathered across ALL realms rather than from the one you happen to have open."""
    import re as _re
    from armada import reader
    roots = []
    for name in ("alpha", "beta"):
        r = tmp_path / name
        r.mkdir()
        (r / "realm.json").write_text(json.dumps({"name": name.title()}), encoding="utf-8")
        roots.append(r)
    monkeypatch.setattr(C, "_known_realms", lambda: [str(x) for x in roots])
    pages = [WCAT._cat_results(reader.read(str(r)), r) for r in roots]
    # the per-realm "in <realm>" marks are the one permitted difference
    strip = lambda s: _re.sub(r"in [A-Za-z0-9 ,]+</span>", "INREALMS", s)
    assert strip(pages[0]) == strip(pages[1])


def test_adding_it_to_one_realm_does_not_add_it_to_the_others(wired, tmp_path, monkeypatch):
    """The chip and the button ask different questions and used to share one answer.

    "in Alpha" is the hint the owner asked for: you have vetted this somewhere before. "Added",
    greyed out, is a statement about the realm you are looking at. Sharing a test meant a
    capability added anywhere could never be added anywhere else — the catalogue read the same in
    every realm but did not BEHAVE the same, which is the half that matters when you click.
    """
    from armada import reader
    roots = []
    for name in ("alpha", "beta"):
        r = tmp_path / name
        r.mkdir()
        (r / "realm.json").write_text(json.dumps({"name": name.title()}), encoding="utf-8")
        roots.append(r)
    monkeypatch.setattr(C, "_known_realms", lambda: [str(x) for x in roots])
    key = C.marketplace_source("official") + "/plugins/code-review"
    assert C.add_to_realm(roots[0], key)["ok"] is True          # into Alpha only

    def card(root):
        h = WCAT._cat_results(reader.read(str(root)), root, q="code-review")
        seg = h[h.index("code-review"):]
        return re.search(r">(Added|Add to realm)</button>", seg).group(1), "in Alpha" in seg

    assert card(roots[0]) == ("Added", True), "the realm that has it says so"
    assert card(roots[1]) == ("Add to realm", True), \
        "the realm that does NOT have it must still be able to add it, while saying where you use it"


# --- controls with nothing left to offer -----------------------------------------------------------

def _dead(realm_model, root, **kw):
    import html as _h
    h = WCAT._cat_results(realm_model, root, **kw)
    m = re.search(r'data-dead="([^"]*)"', h)
    assert m, "the results block carries no dead-control data"
    return set(json.loads(_h.unescape(m.group(1))))


def test_one_possibility_is_not_a_choice(wired, realm):
    """Filter to a source that is all one type, by one publisher, with no categories, and the
    three remaining dropdowns are three invitations to change nothing."""
    from armada import reader
    model = reader.read(str(realm))
    # the marketplace fixture is all plugins
    assert "cat-kind" in _dead(model, realm, source=C.marketplace_source("official"))


def test_a_control_you_have_already_used_stays_live(wired, realm):
    """Otherwise there is no way to undo your way back out of a corner."""
    from armada import reader
    model = reader.read(str(realm))
    dead = _dead(model, realm, source=C.marketplace_source("official"), kind="plugins")
    assert "cat-kind" not in dead


def test_nothing_is_dead_with_a_search_that_matches_everything(wired, realm):
    """The registry sample already keeps its own kinds and its Source option alive with nothing
    typed (test_with_no_search_the_registry_still_answers_with_a_sample); this is the mirrored
    index's turn — a search that also matches the mirrored plugin leaves nothing dead at all."""
    from armada import reader
    assert _dead(reader.read(str(realm)), realm, q="e") == set()


def test_you_can_switch_straight_to_the_registry(wired, realm):
    """The bug: with another source chosen we never fetch the registry, so it costed as zero and
    greyed itself out — you had to go back to All sources first. Not looking is not the same as
    finding nothing. A search, so there is something for the registry to answer with at all."""
    from armada import reader
    model = reader.read(str(realm))
    for src in (C.SKILLS, C.marketplace_source("official")):
        e = _empty(model, realm, source=src, q="acme")
        assert C.REGISTRY not in e["cat-source"], f"the registry is unreachable from {src}"


# --- the explainer ---------------------------------------------------------------------------------

def test_the_catalogue_explainer_is_closed_by_default(wired, realm):
    """It was four paragraphs and a bullet list pinned above the results — a lot of reading to
    scroll past every time you come here to find one thing."""
    from armada import reader
    pane = WCAT._catalogue_pane(reader.read(str(realm)), realm)
    assert '<details class="mc-catinfo' in pane
    box = pane[pane.index('<details class="mc-catinfo'):]
    assert " open>" not in box[:80] and ' open ' not in box[:80]
    assert "Expand to learn" in box


def test_the_explainer_covers_types_sources_and_risk(wired, realm):
    from armada import reader, catalogue as C2
    box = WCAT._cat_infobox(reader.read(str(realm)), C2.load())
    for kind in ("Connector", "Extension", "Skill", "Plugin"):
        assert f"<b>{kind}</b>" in box, f"{kind} is not explained"
    assert "Sources for this catalogue" in box
    assert "until you have turned it on" in box, "the grant rule has to be stated"


def test_the_marketplace_line_is_not_hardcoded_to_anthropic(wired, realm):
    """A machine can have several marketplaces — the CLI clones whichever the owner configured,
    and Anthropic's is only the one that ships by default. Naming Anthropic in a fixed sentence
    would be right today and quietly wrong for anyone who adds a second directory."""
    notes = dict(WCAT._cat_source_notes({"entries": [
        {"source": C.marketplace_source("claude-plugins-official")},
        {"source": C.marketplace_source("acme-internal")},
    ], "source_labels": {}}))
    assert "curated by Anthropic" in notes["Claude plugin marketplace"]
    assert "curated by its owner" in notes["acme-internal"]


def test_the_two_local_sources_are_described_separately(wired, realm):
    """Skills written here and skills an agent fetched are both folders on this machine and read
    identically on disk. They are opposite answers to "should I look at this before switching it
    on", so the explainer has to tell them apart rather than lumping both under "You"."""
    notes = dict(WCAT._cat_source_notes({
        "entries": [{"source": C.MINE}, {"source": C.INSTALLED}], "source_labels": {}}))
    assert "written here" in notes["Created by you"]
    assert "fetched" in notes["Installed by an agent"]
    assert "Nobody reviewed" in notes["Installed by an agent"], \
        "the point of separating them is the review they did not get"
