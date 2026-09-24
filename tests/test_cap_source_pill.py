"""The pill on a User-tab capability says where it came from, in the Catalogue's words.

It used to say "by <maker>", and for most things the maker was unknown, so it said
"by Third-party" — which is not a publisher, not a place, and not any of the answers the
Catalogue's own Source filter offers. The two views were describing the same capability with
vocabularies that had nothing in common.
"""
import json
import re

import pytest

from armada import catalogue as C
from armada.webui import capabilities as CAP


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "_dir", lambda: tmp_path / "catalogue")
    monkeypatch.setattr(C, "_marketplaces_dir", lambda: tmp_path / "marketplaces")
    monkeypatch.setattr(C, "_skill_roots", lambda: [])
    monkeypatch.setattr(C, "_known_realms", lambda: [])
    monkeypatch.setattr(C, "_get_json", lambda url: None)
    return tmp_path


@pytest.fixture
def realm(tmp_path):
    r = tmp_path / "realm"
    r.mkdir()
    (r / "realm.json").write_text(json.dumps({"name": "Test", "toolkit": {
        "connectors": [{"id": "claude_ai_Interactive_Brokers_IBKR",
                        "name": "Interactive Brokers (IBKR)", "source": "3p",
                        "catalogue_key": "mcp-registry/connectors/com.ibkr/interactive-brokers-ibkr",
                        "origin": "MCP registry", "made_by": ""}],
        "extensions": [{"id": "filesystem", "name": "filesystem", "source": "3p",
                        "discovered": True}],
        "skills": [{"id": "frontend-design", "name": "Frontend design", "source": "3p",
                    "catalogue_key": "anthropic-skills/skills/frontend-design",
                    "origin": "Anthropic skills", "made_by": "Anthropic"},
                   {"id": "house-style", "name": "House style", "source": "custom"}],
        "plugins": [],
    }}), encoding="utf-8")
    return r


# --- the label ---------------------------------------------------------------------------------

def test_a_catalogue_capability_names_its_catalogue_source():
    it = {"source": "3p", "catalogue_key": "anthropic-skills/skills/frontend-design"}
    assert CAP._cap_source_label(it) == "Anthropic skills"


def test_the_source_is_read_off_the_key_so_the_two_cannot_drift():
    """The key IS the source. Trusting a separately stored label would let them disagree."""
    it = {"source": "3p", "catalogue_key": "mcp-registry/connectors/com.ibkr/x",
          "origin": "something stale"}
    assert CAP._cap_source_label(it) == "MCP registry"


def test_your_own_capability_says_created_by_you():
    assert CAP._cap_source_label({"source": "custom"}) == C.SOURCE_LABEL[C.MINE]


def test_something_wired_up_in_claude_says_so_rather_than_inventing_a_source():
    """A local MCP server configured in Claude belongs to no browsable source. Naming one would
    be a guess dressed as provenance."""
    assert CAP._cap_source_label({"source": "3p", "discovered": True}) == "Claude"


def test_no_capability_is_ever_labelled_third_party(realm):
    from armada import reader
    html = CAP._realm_skills(reader.read(str(realm)), realm)
    assert "Third-party" not in html


# --- the pill ----------------------------------------------------------------------------------

def test_every_pill_reads_from_not_by(realm):
    from armada import reader
    html = CAP._realm_skills(reader.read(str(realm)), realm)
    pills = re.findall(r'class="mc-pill is-(?:ok|neutral)"[^>]*>(from [^<]*|by [^<]*)</span>', html)
    assert pills, "no source pills rendered"
    assert not [p for p in pills if p.startswith("by ")]
    assert "from Anthropic skills" in pills
    assert "from MCP registry" in pills
    assert f"from {C.SOURCE_LABEL[C.MINE]}" in pills


# --- the filter --------------------------------------------------------------------------------

def test_the_filter_offers_the_sources_actually_present(realm):
    """Built from the capabilities on the page, so the menu can only offer values that appear on
    a card — and so it stops offering "Third-party (company)", which appears on none."""
    from armada import reader
    html = CAP._realm_skills(reader.read(str(realm)), realm)
    seg = html[html.index('id="cap-f-source"'):]
    seg = seg[:seg.index("</details>")]
    vals = set(re.findall(r'<a data-val="([^"]*)"', seg))
    assert {"mcp-registry", "anthropic-skills", "claude", C.MINE} <= vals
    assert "company" not in vals and "oss" not in vals


def test_the_filter_matches_what_the_pill_shows(realm):
    """data-source is the value the filter compares and the pill displays. A filter whose values
    you cannot see on the cards is one you have to guess at."""
    from armada import reader
    html = CAP._realm_skills(reader.read(str(realm)), realm)
    assert 'data-source="anthropic-skills"' in html
    assert 'data-source="claude"' in html
    assert 'data-made=' not in html, "the old maker attribute is still being written"


# --- what the pill stopped carrying --------------------------------------------------------------

def test_the_publisher_did_not_just_disappear(realm):
    """The page is headed "who made it". The pill now answers a different question, so the
    publisher gets a line of its own."""
    from armada import reader
    html = CAP._realm_skills(reader.read(str(realm)), realm)
    assert "Published by" in html and ">Anthropic</div>" in html


def test_no_publisher_row_when_nobody_is_named(realm):
    """Better a missing row than one reading "Published by:" followed by nothing."""
    html = CAP._cap_prov({"id": "x", "source": "3p", "discovered": True}, "extensions")
    assert "Published by" not in html
