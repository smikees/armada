"""Discovered capabilities take the catalogue's name and provenance — when it is certainly the same thing.

A connector Claude sets up arrives called `claude_ai_Interactive_Brokers_IBKR`, published by
nobody, filed as "Added & authorised in Claude". The Catalogue lists the same server as
"Interactive Brokers (IBKR)" from the MCP registry, with a publisher and a link. Both were true;
only one is useful, and the owner shouldn't have to hold both in their head.

Everything here is about NOT getting that wrong. Rewriting a record's name, publisher and trust
badge on a bad guess replaces the tool the owner has been using with a stranger's project.
"""
import json

import pytest

from armada import catalogue as C


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "_dir", lambda: tmp_path / "catalogue")
    monkeypatch.setattr(C, "_marketplaces_dir", lambda: tmp_path / "marketplaces")
    monkeypatch.setattr(C, "_skill_roots", lambda: [])
    monkeypatch.setattr(C, "_known_realms", lambda: [])
    monkeypatch.setattr(C, "_get_json", lambda url: None)
    C._reg_cache.clear()
    return tmp_path


@pytest.fixture
def realm(tmp_path):
    r = tmp_path / "realm"
    r.mkdir()
    return r


def _write(realm, toolkit):
    (realm / "realm.json").write_text(json.dumps({"name": "Test", "toolkit": toolkit}),
                                      encoding="utf-8")


def _read(realm):
    return json.loads((realm / "realm.json").read_text(encoding="utf-8-sig"))["toolkit"]


# --- the case this exists for ----------------------------------------------------------------------

def test_a_connector_claude_named_gets_its_real_name(realm):
    _write(realm, {"connectors": [{"id": "claude_ai_Interactive_Brokers_IBKR",
                                   "name": "claude_ai_Interactive_Brokers_IBKR",
                                   "source": "3p", "discovered": True,
                                   "scope": "MCP server (Claude)"}]})
    known = [C._entry(C.REGISTRY, "connectors", "com.ibkr/interactive-brokers-ibkr",
                      "Interactive Brokers (IBKR)", "Trade and read your IBKR account",
                      curated=C.CURATED_REGISTRY, homepage="https://ibkr.example")]
    r = C.adopt(realm, entries=known, search=False)
    assert r["ok"] and len(r["changed"]) == 1
    c = _read(realm)["connectors"][0]
    assert c["name"] == "Interactive Brokers (IBKR)"
    assert c["scope"] == "MCP registry" and c["origin"] == "MCP registry"
    assert c["catalogue_key"] == known[0]["key"]


def test_claudes_own_prefix_is_not_part_of_the_name(realm):
    """`claude_ai_` is Claude's bookkeeping. Leaving it in the tokens is why the realm's IBKR
    connector shared no exact token with the registry's interactive-brokers-ibkr."""
    toks = C._tokens({"id": "claude_ai_Interactive_Brokers_IBKR",
                      "name": "claude_ai_Interactive_Brokers_IBKR"})
    assert "interactivebrokersibkr" in toks


# --- the ways this could go wrong --------------------------------------------------------------------

def test_an_ambiguous_name_is_left_alone(realm):
    """The realm's `filesystem` extension matches several published servers called Filesystem.
    Picking the first is a coin toss that ends with the owner's own tool credited to a stranger."""
    _write(realm, {"extensions": [{"id": "filesystem", "name": "filesystem",
                                   "source": "3p", "discovered": True}]})
    known = [C._entry(C.REGISTRY, "extensions", "io.github.a/filesystem", "Filesystem", "one"),
             C._entry(C.REGISTRY, "extensions", "io.github.b/filesystem", "Filesystem", "two")]
    r = C.adopt(realm, entries=known, search=False)
    assert r["changed"] == []
    assert _read(realm)["extensions"][0]["name"] == "filesystem"


def test_a_near_miss_is_not_a_match(realm):
    """`windows-mcp` is contained in `windows-mcp-server`, a different author's project. The hint
    on a catalogue card can afford that guess; renaming the owner's extension cannot."""
    _write(realm, {"extensions": [{"id": "windows-mcp", "name": "windows-mcp",
                                   "source": "3p", "discovered": True}]})
    known = [C._entry(C.REGISTRY, "extensions", "io.github.other/windows-mcp-server",
                      "Windows Management", "someone else's")]
    assert C.adopt(realm, entries=known, search=False)["changed"] == []
    assert _read(realm)["extensions"][0]["name"] == "windows-mcp"


def test_the_exact_match_wins_over_the_near_one(realm):
    _write(realm, {"extensions": [{"id": "windows-mcp", "name": "windows-mcp",
                                   "source": "3p", "discovered": True}]})
    known = [C._entry(C.REGISTRY, "extensions", "io.github.other/windows-mcp-server",
                      "Windows Management", "not it"),
             C._entry(C.REGISTRY, "extensions", "io.github.CursorTouch/Windows-MCP",
                      "", "the real one")]
    r = C.adopt(realm, entries=known, search=False)
    assert len(r["changed"]) == 1
    assert _read(realm)["extensions"][0]["catalogue_key"] == known[1]["key"]


def test_a_nameless_registry_record_does_not_supply_a_worse_name(realm):
    """Registry records often have no title, so their "name" is the reverse-DNS id.
    `io.github.CursorTouch/Windows-MCP` is not an improvement on `windows-mcp`."""
    _write(realm, {"extensions": [{"id": "windows-mcp", "name": "windows-mcp",
                                   "source": "3p", "discovered": True}]})
    known = [C._entry(C.REGISTRY, "extensions", "io.github.CursorTouch/Windows-MCP", "", "x")]
    C.adopt(realm, entries=known, search=False)
    c = _read(realm)["extensions"][0]
    assert c["name"] == "windows-mcp"
    assert c["catalogue_key"], "it still adopts the provenance, just not the ugly name"


# --- what must never be touched ---------------------------------------------------------------------

def test_a_capability_you_wrote_is_never_renamed(realm):
    """You named it. A catalogue coincidence is not a reason to rename it for you."""
    _write(realm, {"skills": [{"id": "house-style", "name": "House style",
                               "source": "custom"}]})
    known = [C._entry(C.SKILLS, "skills", "house-style", "House Style", "Anthropic's")]
    assert C.adopt(realm, entries=known, search=False)["changed"] == []
    assert _read(realm)["skills"][0]["name"] == "House style"


def test_the_id_never_changes(realm):
    """Grants are keyed by id. Renaming it would silently revoke every agent's access."""
    _write(realm, {"connectors": [{"id": "claude_ai_Interactive_Brokers_IBKR",
                                   "name": "claude_ai_Interactive_Brokers_IBKR",
                                   "source": "3p", "discovered": True}]})
    known = [C._entry(C.REGISTRY, "connectors", "com.ibkr/interactive-brokers-ibkr",
                      "Interactive Brokers (IBKR)", "x")]
    C.adopt(realm, entries=known, search=False)
    assert _read(realm)["connectors"][0]["id"] == "claude_ai_Interactive_Brokers_IBKR"


def test_it_does_not_switch_anything_on_or_change_what_it_can_reach(realm):
    """Whether it runs is the owner's decision; what it can reach is what inspection found on THIS
    machine, which beats a catalogue blurb."""
    _write(realm, {"connectors": [{"id": "claude_ai_Interactive_Brokers_IBKR",
                                   "name": "claude_ai_Interactive_Brokers_IBKR",
                                   "source": "3p", "discovered": True, "enabled": False,
                                   "runs": "service", "touch": ["network"]}]})
    known = [C._entry(C.REGISTRY, "connectors", "com.ibkr/interactive-brokers-ibkr",
                      "Interactive Brokers (IBKR)", "x")]
    C.adopt(realm, entries=known, search=False)
    c = _read(realm)["connectors"][0]
    assert c["enabled"] is False and c["runs"] == "service" and c["touch"] == ["network"]


def test_running_it_twice_changes_nothing_the_second_time(realm):
    _write(realm, {"connectors": [{"id": "claude_ai_Interactive_Brokers_IBKR",
                                   "name": "claude_ai_Interactive_Brokers_IBKR",
                                   "source": "3p", "discovered": True}]})
    known = [C._entry(C.REGISTRY, "connectors", "com.ibkr/interactive-brokers-ibkr",
                      "Interactive Brokers (IBKR)", "x")]
    assert len(C.adopt(realm, entries=known, search=False)["changed"]) == 1
    assert C.adopt(realm, entries=known, search=False)["changed"] == []


def test_a_realm_with_no_toolkit_is_not_a_crash(realm):
    (realm / "realm.json").write_text(json.dumps({"name": "Bare"}), encoding="utf-8")
    assert C.adopt(realm, entries=[], search=False)["ok"] is True


# --- looking things up the registry can actually find -------------------------------------------------

def test_the_search_terms_are_shaped_for_the_registry(realm):
    """Its search does not tokenise: "Interactive Brokers IBKR" finds nothing, "interactive-brokers"
    finds exactly one. So words are joined with hyphens, and the short distinctive tail is tried."""
    qs = C._adopt_queries({"id": "claude_ai_Interactive_Brokers_IBKR",
                           "name": "claude_ai_Interactive_Brokers_IBKR"})
    assert qs[0] == "interactive-brokers-ibkr"
    assert "ibkr" in qs
    assert not any(" " in q for q in qs)
