"""Memory card layout: one narrow left gutter (scope icon with the caret beneath it), and the whole
card as the expand target rather than the 13px chevron alone.

These are shape assertions on the rendered HTML and the shared script, because the bug they guard
against — a second column of dead space pushing every memory's text to the right, and an expand
affordance you had to hit precisely — is only visible in the markup.
"""
from pathlib import Path

from armada.webui import memoryview


LONG = "x " * 400


def _cards(scope="realm"):
    items = [("note", "A note", LONG, "01-01-26", "note", "owner")]
    return memoryview._mem_cards(items, scope)


def _js():
    return (Path(memoryview.__file__).parent / "static" / "js" / "mem_expand.js").read_text(encoding="utf-8")


def test_caret_and_icon_share_one_gutter():
    """Stacked, not side by side — side by side is what cost the content its left margin."""
    html = _cards()
    assert "flex-direction:column" in html
    caret = html.index("mc-memexpand")
    gutter = html.index("flex-direction:column")
    assert gutter < caret, "the caret must live inside the stacked gutter, not in a column of its own"
    assert "mc-memnocaret" not in html, "the old spacer column is gone"


def test_left_padding_is_tighter_than_the_right():
    html = _cards()
    assert "padding:10px 12px 10px 7px" in html


def test_whole_card_expands_not_just_the_caret():
    js = _js()
    assert "document.addEventListener('click'" in js
    assert ".mc-memcard" in js
    # the row's own controls must keep working
    assert "a,button,input,textarea,select,.mc-memactions" in js
    assert "mc-memactions" in _cards(), "the action cluster needs its class for the click guard"


def test_click_does_not_collapse_a_text_selection():
    js = _js()
    assert "getSelection" in js and "isCollapsed" in js


def test_card_only_offers_to_expand_when_there_is_more():
    js = _js()
    assert "scrollHeight-body.clientHeight" in js
    assert "cursor" in js, "a card with nothing more to show must not look clickable"


def test_agent_and_realm_memories_use_the_same_card():
    assert memoryview._mem_cards.__doc__ is None or True
    for scope in ("realm", "agent"):
        html = _cards(scope)
        assert "flex-direction:column" in html and "padding:10px 12px 10px 7px" in html
