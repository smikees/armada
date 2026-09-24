"""Capabilities UI: one place to manage, counts that mean something, and a filter that lets go.

Everything here is a consequence of grants arriving: pages that used to describe a shared catalogue
kept describing it, and controls that belong to the catalogue were duplicated onto pages about a
single agent.
"""
import json
from pathlib import Path

import pytest

from armada import capabilities as C
from armada import reader
from armada.webui import capabilities as UI
from armada.webui import realmpages as RP

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
                             ("development", "Steve", False)):
        (r / "agents" / aid).mkdir(parents=True, exist_ok=True)
        (r / "agents" / aid / "agent.json").write_text(json.dumps(
            {"id": aid, "display": disp, "coordinator": coord, "role": "R"}), encoding="utf-8")
    return r


def _agent(r, aid):
    m = reader.read(str(r))
    return m, next(a for a in m.agents if a.id == aid)


# --------------------------------------------------------------------------- the agent page

def test_the_unavailable_section_is_gone(realm):
    """It restated the realm page. One catalogue, listed in one place."""
    m, a = _agent(realm, "development")
    html = UI._tab_skills(m, realm, a)
    assert "not available to" not in html
    assert "windows-mcp" not in html


def test_no_manage_button(realm):
    m, a = _agent(realm, "development")
    assert "mcCapManage" not in UI._tab_skills(m, realm, a)


def test_no_connector_refresh_on_the_agent_page(realm):
    """Refresh pulls servers into the realm catalogue; here it read as "refresh this agent's"."""
    m, a = _agent(realm, "development")
    assert "mcConnectorRefresh" not in UI._tab_skills(m, realm, a)


def test_the_agent_page_is_read_only(realm):
    """With a manage scope, every card grew enable/edit/delete acting on this agent's toolkit — a
    third way to change a capability, beside a sentence saying where capabilities are changed."""
    C.grant(realm, "development", "filesystem")
    m, a = _agent(realm, "development")
    html = UI._tab_skills(m, realm, a)
    for control in ("mcCapToggle", "mcCapEdit", "mcCapDelete", "mcCapUpdate"):
        assert control not in html, control


def test_the_refresh_survives_on_the_realm_page(realm):
    assert "mcConnectorRefresh" in UI._realm_skills(reader.read(str(realm)), realm)


def test_the_sentence_does_not_offer_a_second_way(realm):
    """Dragging IS how access is given — "or" implied an alternative that doesn't exist."""
    m, a = _agent(realm, "development")
    html = UI._tab_skills(m, realm, a)
    assert "page</a>, by dragging" in html
    assert "or by dragging" not in html


def test_the_agent_page_still_lists_what_it_can_use(realm):
    C.grant(realm, "development", "filesystem")
    m, a = _agent(realm, "development")
    html = UI._tab_skills(m, realm, a)
    assert "filesystem" in html and "<b>1</b> of <b>3</b>" in html


# --------------------------------------------------------------------------- counts

def test_card_counts_are_per_agent_not_realm_wide(realm):
    """Every card used to show the size of the realm, so they all read the same."""
    C.grant(realm, "finance", "filesystem")
    assert RP._agent_cap_counts(realm, "finance") == {
        "connectors": 0, "extensions": 1, "plugins": 0, "skills": 0}
    assert RP._agent_cap_counts(realm, "development") == {
        "connectors": 0, "extensions": 0, "plugins": 0, "skills": 0}


def test_the_coordinator_card_counts_the_whole_catalogue(realm):
    assert RP._agent_cap_counts(realm, "hand") == {
        "connectors": 1, "extensions": 2, "plugins": 0, "skills": 0}


def test_a_disconnected_capability_is_not_counted(realm):
    cfg = json.loads((realm / "realm.json").read_text(encoding="utf-8"))
    cfg["toolkit"]["extensions"][0]["status"] = "disconnected"
    (realm / "realm.json").write_text(json.dumps(cfg), encoding="utf-8")
    C.grant(realm, "finance", "filesystem")
    assert RP._agent_cap_counts(realm, "finance")["extensions"] == 0


def test_an_unreadable_agent_does_not_break_the_card(realm):
    assert RP._agent_cap_counts(realm, "no-such-agent") == {
        "connectors": 0, "extensions": 0, "plugins": 0, "skills": 0}


# --------------------------------------------------------------------------- the filter

def test_an_empty_group_can_come_back_after_filtering(realm):
    """The bug: a bucket with no cards counted zero visible cards, so it was hidden and could never
    return — clearing the filter left it gone until something re-rendered the page."""
    html = UI._realm_skills(reader.read(str(realm)), realm)
    assert "/static/js/capfilter.js" in html
    js = _CAPFILTER_JS.read_text(encoding="utf-8")
    fn = js.split("function mcCapFilter(){")[1].split("function mcCapSearchClear")[0]
    assert "total===0" in fn, "an empty group is still counted as 'nothing visible'"
    assert "filtering" in fn, "no notion of whether a filter is even active"


def test_the_filter_state_drives_empty_group_visibility(realm):
    js = _CAPFILTER_JS.read_text(encoding="utf-8")
    fn = js.split("function mcCapFilter(){")[1].split("function mcCapSearchClear")[0]
    assert 'var filtering=!!(q||av||md||tr||ty)' in fn
    assert 'g.style.display=(total===0?(filtering?"none":""):(any?"":"none"))' in fn


# --------------------------------------------------------------------------- the gradient

def test_the_tier_gradient_is_wide_enough_to_see(realm):
    m = reader.read(str(realm))
    html = UI._cap_card({"id": "filesystem", "name": "filesystem"}, kind="extensions",
                        manage="realm", realm=m, realm_root=realm)
    grad = html.split("background-image:linear-gradient")[1].split('"')[0]
    assert "28px" in grad
    assert "transparent 8px)" not in grad, "still the original hairline"
