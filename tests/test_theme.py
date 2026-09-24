"""Realm role labels adapt to type, and 'Hand' stays private to the owner's Cabinet."""
from armada.reader import _resolve_theme


def test_type_defaults_when_theme_unspecified():
    assert _resolve_theme({"template": "state"}, {})[0] == "Prime Minister"
    assert _resolve_theme({"template": "company"}, {})[0] == "CEO"
    assert _resolve_theme({"template": "crew"}, {})[0] == "Captain"
    # unknown / scratch → neutral
    assert _resolve_theme({"template": "scratch"}, {}) == ("Coordinator", "Agent", "Realm")


def test_theme_json_overrides_default():
    coord, agent, coll = _resolve_theme({"template": "company"},
                                        {"coordinator": "Chief", "agent": "Partner", "collective": "Firm"})
    assert (coord, agent, coll) == ("Chief", "Partner", "Firm")


def test_hand_is_private_to_mihais_cabinet():
    # the owner's Cabinet gets 'Hand'
    cfg = {"name": "The Cabinet", "owner": "Mihai", "template": "state"}
    assert _resolve_theme(cfg, {"coordinator": "Hand"})[0] == "Hand"
    assert _resolve_theme(cfg, {})[0] == "Hand"  # even if theme.json doesn't say so


def test_hand_never_leaks_to_other_users():
    # same realm name but a different owner → no 'Hand'
    assert _resolve_theme({"name": "The Cabinet", "owner": "Alex", "template": "state"},
                          {"coordinator": "Hand"})[0] == "Prime Minister"
    # a stray 'Hand' in an unrelated realm's theme also falls back to the type default
    assert _resolve_theme({"name": "My Gov", "template": "state"},
                          {"coordinator": "Hand"})[0] == "Prime Minister"
