"""The thread rail distinguishes a capability the agent GAINED here from one it already had.

Both are "used in this thread", but only one means the agent's reach grew — and that is the half
the owner needs to notice, since an in-thread grant is a decision they made in passing.
"""
import json

from armada import capabilities as C
from armada.webui import threadsview as tv


def _realm(tmp_path):
    r = tmp_path / "realm"
    (r / "agents" / "warren").mkdir(parents=True)
    (r / "realm.json").write_text(json.dumps({"toolkit": {
        "connectors": [{"id": "ibkr", "name": "IBKR"}],
        "extensions": [{"id": "filesystem", "name": "filesystem"}]}}), encoding="utf-8")
    (r / "agents" / "warren" / "agent.json").write_text(
        json.dumps({"id": "warren"}), encoding="utf-8")
    return r


_TURN = [{"role": "assistant", "content": "done", "caps_used": [
    {"type": "extensions", "id": "filesystem", "name": "filesystem"},
    {"type": "connectors", "id": "ibkr", "name": "IBKR"}]}]


def test_a_capability_granted_in_this_thread_is_marked_new(tmp_path):
    r = _realm(tmp_path)
    C.request(r, "warren", "filesystem", "need it", thread="taxes")
    C.approve_request(r, "warren", "filesystem")
    C.grant(r, "warren", "ibkr", via="user")          # the owner mapped this one earlier

    caps = tv._thread_caps_used(_TURN, r, "warren", "taxes")
    assert caps["extensions"][0]["new"] is True
    assert caps["connectors"][0]["new"] is False


def test_the_same_capability_is_not_new_in_a_different_thread(tmp_path):
    r = _realm(tmp_path)
    C.request(r, "warren", "filesystem", "need it", thread="taxes")
    C.approve_request(r, "warren", "filesystem")
    caps = tv._thread_caps_used(_TURN, r, "warren", "main")
    assert caps["extensions"][0]["new"] is False


def test_without_context_nothing_is_marked(tmp_path):
    """The old call signature still works and simply doesn't claim anything."""
    caps = tv._thread_caps_used(_TURN)
    assert "new" not in caps["extensions"][0]


def test_the_rail_renders_a_badge_only_for_new_ones(tmp_path):
    html_new = tv._thread_caps_rail({"extensions": [{"id": "filesystem", "name": "filesystem",
                                                     "new": True}]})
    html_old = tv._thread_caps_rail({"extensions": [{"id": "filesystem", "name": "filesystem",
                                                     "new": False}]})
    assert ">new<" in html_new and "granted to this agent in this thread" in html_new
    assert ">new<" not in html_old


def test_the_rail_still_names_the_capability(tmp_path):
    """A badge must not cost the thing it is annotating."""
    for flag in (True, False):
        html = tv._thread_caps_rail({"connectors": [{"id": "ibkr", "name": "IBKR", "new": flag}]})
        assert "IBKR" in html


def test_an_empty_thread_still_shows_the_placeholder():
    assert "will appear here" in tv._thread_caps_rail({})
