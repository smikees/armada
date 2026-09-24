"""The dashboard's top and bottom edges.

The header casts a shadow once the grid scrolls, which is the line between the fixed header and the
content moving under it — but its box started 24px in from the left and ran to the right edge, so
the line stopped short on one side only. And below the grid sat a solid 20px band of page
background, which cut whatever happened to be at the bottom in half: not "there is more below",
just a row of text with its descenders missing.
"""
import json
import re

import pytest

from armada import reader
from armada.webui import pages as P


@pytest.fixture
def realm(tmp_path):
    root = tmp_path / "Cabinet-realm"
    ad = root / "agents" / "finance"
    (ad / "jobs").mkdir(parents=True)
    (root / "realm.json").write_text(json.dumps({"name": "Cabinet"}), encoding="utf-8")
    (ad / "agent.json").write_text(json.dumps({"id": "finance", "display": "Warren"}),
                                   encoding="utf-8")
    return root


def _dash(realm):
    return P.render_dashboard(reader.read(str(realm)), realm)


def _ovh(html):
    i = html.index('id="mc-ovh"')
    return html[i:html.index(">", i)]


def _grid(html):
    i = html.index('id="mc-grid"')
    return html[i:html.index(">", i)]


# --------------------------------------------------------------------------- the header shadow

def test_the_header_reaches_both_window_edges(realm):
    """Its shadow is its edge; a box that stops short on one side draws half a line."""
    ovh = _ovh(_dash(realm))
    assert "margin-left:-24px" in ovh, "the header still starts inside the left gutter"
    assert "padding:0 24px 14px" in ovh, "the pulled-out header no longer re-pays the indent"


def test_the_header_content_has_not_moved(realm):
    """The point is a symmetric shadow, not a shifted title."""
    ovh = _ovh(_dash(realm))
    pad = re.search(r"padding:0 (\d+)px 14px", ovh)
    pull = re.search(r"margin-left:-(\d+)px", ovh)
    assert pad and pull and pad.group(1) == pull.group(1), "the pull-out and the re-paid padding differ"


def test_the_shadow_still_only_appears_on_scroll(realm):
    from pathlib import Path
    js = (Path(P.__file__).parent / "static" / "js" / "dash.js").read_text(encoding="utf-8")
    assert "g.scrollTop>2" in js


# --------------------------------------------------------------------------- the bottom edge

def test_the_solid_band_below_the_grid_is_gone(realm):
    html = _dash(realm)
    block = html[html.index("flex:1;min-height:0;padding:16px"):][:120]
    assert "padding:16px 0 0 24px" in block, "the block still pads the bottom"


def test_a_fade_covers_the_last_strip_instead(realm):
    assert "linear-gradient(to bottom,transparent,var(--color-bg))" in _dash(realm)


def test_the_fade_does_not_swallow_clicks(realm):
    html = _dash(realm)
    i = html.index("bottom:0;height:22px;pointer-events:none")
    tag = html[html.rindex("<div", 0, i):html.index(">", i)]
    assert "pointer-events:none" in tag and "linear-gradient(to bottom,transparent" in tag


def test_the_scroller_makes_room_for_the_fade(realm):
    """Otherwise the last row parks under the gradient at full scroll and can never be read."""
    grid = _grid(_dash(realm))
    pb = re.search(r"padding-bottom:(\d+)px", grid)
    assert pb, "the grid has no bottom padding"
    html = _dash(realm)
    fade_h = int(re.search(r"bottom:0;height:(\d+)px;pointer-events:none", html).group(1))
    assert int(pb.group(1)) >= fade_h, "the fade is taller than the room the scroller leaves"


def test_the_fade_sits_under_the_header(realm):
    """Both are overlays; the header has to win where they meet."""
    html = _dash(realm)
    fade_z = int(re.search(r"pointer-events:none;z-index:(\d+)", html).group(1))
    ovh_z = int(re.search(r"z-index:(\d+);transition:box-shadow", _ovh(html)).group(1))
    assert ovh_z > fade_z
