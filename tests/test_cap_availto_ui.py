"""The Capabilities page after the grant model: who a capability is available to, and how you
change it.

The page used to describe capabilities as owned by a scope. They are now held by the realm and
made available to named agents, so the column, the chips, the roster and the filter all answer the
same question — which agents can use this.
"""
import json
from pathlib import Path

import pytest

from armada import capabilities as C
from armada import reader
from armada.webui import capabilities as UI

_CAPFILTER_JS = Path(UI.__file__).with_name("static").joinpath("js", "capfilter.js")


@pytest.fixture
def realm(tmp_path):
    r = tmp_path / "Cabinet-realm"
    (r / "agents").mkdir(parents=True)
    (r / "realm.json").write_text(json.dumps({
        "name": "Cabinet", "owner": "M",
        "toolkit": {"connectors": [{"id": "ibkr", "name": "IBKR"}],
                    "extensions": [{"id": "filesystem", "name": "filesystem"},
                                   {"id": "windows-mcp", "name": "windows-mcp"}],
                    "skills": [], "plugins": []}}), encoding="utf-8")
    for aid, disp, coord in (("hand", "Marcus", True), ("finance", "Warren", False),
                             ("health", "Galen", False), ("travel", "Ibn", False)):
        (r / "agents" / aid).mkdir(parents=True, exist_ok=True)
        (r / "agents" / aid / "agent.json").write_text(json.dumps(
            {"id": aid, "display": disp, "coordinator": coord, "role": "R"}), encoding="utf-8")
    return r


def _model(r):
    return reader.read(str(r))


def _fs(r):
    return {"id": "filesystem", "name": "filesystem"}


# --------------------------------------------------------------------------- the label

def test_label_is_coordinator_plus_count(realm):
    m = _model(realm)
    C.grant(realm, "finance", "filesystem")
    C.grant(realm, "health", "filesystem")
    coords, granted = UI._cap_agents(m, realm, _fs(realm))
    assert UI._cap_availto_label(m, coords, granted) == "Marcus + 2 agents"


def test_one_agent_is_singular(realm):
    m = _model(realm)
    C.grant(realm, "finance", "filesystem")
    coords, granted = UI._cap_agents(m, realm, _fs(realm))
    assert UI._cap_availto_label(m, coords, granted) == "Marcus + 1 agent"


def test_coordinator_alone_shows_just_the_name(realm):
    m = _model(realm)
    coords, granted = UI._cap_agents(m, realm, _fs(realm))
    assert UI._cap_availto_label(m, coords, granted) == "Marcus"


def test_without_a_coordinator_it_is_a_bare_count(realm):
    """A realm with no PM has nobody with blanket access, so there's no name to lead with."""
    a = realm / "agents" / "hand" / "agent.json"
    a.write_text(json.dumps({"id": "hand", "display": "Marcus", "coordinator": False}), encoding="utf-8")
    m = _model(realm)
    C.grant(realm, "finance", "filesystem")
    C.grant(realm, "health", "filesystem")
    coords, granted = UI._cap_agents(m, realm, _fs(realm))
    assert coords == []
    assert UI._cap_availto_label(m, coords, granted) == "2 agents"


def test_nobody_at_all_says_so(realm):
    a = realm / "agents" / "hand" / "agent.json"
    a.write_text(json.dumps({"id": "hand", "display": "Marcus", "coordinator": False}), encoding="utf-8")
    m = _model(realm)
    coords, granted = UI._cap_agents(m, realm, _fs(realm))
    assert UI._cap_availto_label(m, coords, granted) == "No agents"


def test_a_realm_disabled_capability_is_available_to_nobody(realm):
    cfg = json.loads((realm / "realm.json").read_text(encoding="utf-8"))
    cfg["toolkit"]["extensions"][0]["enabled"] = False
    (realm / "realm.json").write_text(json.dumps(cfg), encoding="utf-8")
    C.grant(realm, "finance", "filesystem")       # refused, but assert on the rendering anyway
    m = _model(realm)
    _co, granted = UI._cap_agents(m, realm, {"id": "filesystem", "name": "filesystem", "enabled": False})
    assert granted == []


# --------------------------------------------------------------------------- the chips

def test_chips_pin_the_coordinator_and_make_others_removable(realm):
    C.grant(realm, "finance", "filesystem")
    html = UI._cap_availto_chips(_model(realm), realm, _fs(realm), "extensions")
    assert "Marcus" in html and "Warren" in html
    assert "mcCapRemoveAgent" in html
    # the pinned one carries no remove control
    marcus_chunk = html.split("Warren")[0]
    assert "mcCapRemoveAgent" not in marcus_chunk


def test_chips_prompt_when_nobody_is_granted(realm):
    html = UI._cap_availto_chips(_model(realm), realm, _fs(realm), "extensions")
    assert "drag an agent here" in html


# --------------------------------------------------------------------------- the card

def test_the_card_carries_the_column_and_the_drop_target(realm):
    m = _model(realm)
    C.grant(realm, "finance", "filesystem")
    html = UI._cap_card(_fs(realm), kind="extensions", manage="realm", realm=m, realm_root=realm)
    assert "Available to" in html
    assert "Marcus + 1 agent" in html
    assert "mcCapDrop" in html and "ondragover" in html


def test_the_card_lists_every_agent_that_can_use_it_for_the_filter(realm):
    m = _model(realm)
    C.grant(realm, "health", "filesystem")
    html = UI._cap_card(_fs(realm), kind="extensions", manage="realm", realm=m, realm_root=realm)
    ids = html.split('data-agents="')[1].split('"')[0].split()
    assert set(ids) == {"hand", "health"}, ids


def test_the_card_has_the_tier_gradient(realm):
    m = _model(realm)
    html = UI._cap_card(_fs(realm), kind="extensions", manage="realm", realm=m, realm_root=realm)
    assert "background-image:linear-gradient(to right" in html
    assert "transparent 28px)" in html      # width tuned in test_cap_ui_cleanup
    assert "background:" not in html.split("<summary")[0].split('style="')[1].split('"')[0], \
        "must set background-image, not the shorthand, or the card loses its own background colour"


def test_a_card_without_realm_context_is_unchanged(realm):
    """The agent tab renders cards without the roster; it must not grow an empty column."""
    html = UI._cap_card(_fs(realm), kind="extensions", manage="realm")
    assert "Available to" not in html
    assert "mcCapDrop" not in html
    # 14px is the chevron column; the type icon moved into the name column, which is why it is
    # 316 rather than the 300 it was.
    assert "14px 316px 88px 118px 1fr" in html


# --------------------------------------------------------------------------- page furniture

def test_the_legend_puts_risk_on_one_row(realm):
    html = UI._cap_legend()
    risk = html.split("Risk")[1].split("Runs")[0]
    assert "flex-wrap:wrap" in risk
    for lab in ("Trusted", "Review", "Caution"):
        assert lab in risk


def test_the_roster_is_draggable_and_excludes_the_coordinator(realm):
    html = UI._cap_roster(_model(realm), realm)
    assert 'draggable="true"' in html and "mcCapDragStart" in html
    assert "Warren" in html and "Galen" in html
    assert html.count("mcCapDragStart") == 3          # the three members, not Marcus
    assert "can use every capability" in html         # the coordinator is explained instead


def test_the_roster_explains_a_realm_with_no_coordinator(realm):
    (realm / "agents" / "hand" / "agent.json").write_text(
        json.dumps({"id": "hand", "display": "Marcus", "coordinator": False}), encoding="utf-8")
    html = UI._cap_roster(_model(realm), realm)
    assert "no coordinator" in html


def test_the_filter_asks_who_it_is_available_to(realm):
    html = UI._realm_skills(_model(realm), realm)
    assert 'id="cap-f-avail"' in html
    assert "Any agent" in html, "the default label should say the filter asks about agents"
    assert "All owners" not in html
    # The filter is the app's dropdown now, so its choices are menu rows rather than <option>s.
    for disp in ("Marcus", "Warren", "Galen", "Ibn"):
        assert f"'{disp}')\">{disp}</a>" in html or f">{disp}</a>" in html, \
            f"{disp} is missing from the Available-to filter"


def test_the_filter_matches_ids_as_whole_words(realm):
    """' hand ' inside ' hand health ' must not also match an agent called 'han'."""
    html = UI._realm_skills(_model(realm), realm)
    assert "/static/js/capfilter.js" in html
    assert 'ids.indexOf(" "+av+" ")' in _CAPFILTER_JS.read_text(encoding="utf-8")


def test_the_page_renders_with_the_roster_in_the_rail(realm):
    html = UI._realm_skills(_model(realm), realm)
    assert "Drag an agent onto a capability" in html
    assert "Legend" in html


def test_a_grant_does_not_duplicate_the_capability_as_agent_specific(realm):
    """An agent's toolkit holds grants — pointers at realm capabilities. Listing it verbatim printed
    filesystem three times: once for the realm and once per agent granted it, the copies filed under
    a heading claiming they were that agent's alone."""
    C.grant(realm, "finance", "filesystem")
    C.grant(realm, "health", "filesystem")
    html = UI._realm_skills(_model(realm), realm)
    caps = [seg.split('"')[0] for seg in html.split('data-cap="')[1:]]
    assert caps.count("filesystem") == 1, caps
    assert "Agent-specific" not in html


def test_something_only_an_agent_has_is_still_surfaced(realm):
    """The case the section is now for: in a toolkit, absent from the catalogue. Shouldn't happen,
    which is exactly why it should be visible if it does."""
    ap = realm / "agents" / "finance" / "agent.json"
    a = json.loads(ap.read_text(encoding="utf-8"))
    a["toolkit"] = {"connectors": [{"id": "orphan", "name": "Orphan"}]}
    ap.write_text(json.dumps(a), encoding="utf-8")
    html = UI._realm_skills(_model(realm), realm)
    assert "Agent-specific" in html and "Orphan" in html
