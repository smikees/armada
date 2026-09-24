"""Avatar identification: colour disc behind, status dot on the corner, no border.

Three earlier attempts (a coloured ring, a card-bottom wash, a plume under the avatar) are gone.
What's here now: the avatar has no border at all, the agent's colour is a filled disc sitting a
couple of pixels out to the left, and the activity dot is on the picture's lower-right corner
instead of floating beside the name.

Most of these guard things that break silently — paint order, and the fact that every status colour
is semi-transparent and now sits on top of a photograph.
"""
import json
import types
from pathlib import Path

import pytest

from armada.webui import agentbits

_JS = Path(agentbits.__file__).parent / "static" / "js"
_CSS = Path(agentbits.__file__).parent / "static" / "brand.css"


@pytest.fixture
def agent(tmp_path):
    def _mk(color="#1f78b4"):
        d = tmp_path / "agents" / "steve"
        d.mkdir(parents=True, exist_ok=True)
        (d / "agent.json").write_text(json.dumps({"color": color} if color else {}), encoding="utf-8")
        return tmp_path, types.SimpleNamespace(id="steve", is_coordinator=False, color="")
    return _mk


# ---- the avatar itself ---------------------------------------------------------------------

def test_the_avatar_has_no_border(agent):
    root, a = agent()
    html = agentbits._portrait(root, a, 44)
    assert "border:1px solid var(--color-divider)" not in html
    assert "border:2px solid" not in html


def test_the_colour_sits_behind_the_avatar_offset_left(agent):
    root, a = agent()
    html = agentbits._portrait(root, a, 44)
    assert "mc-avdisc" in html and "#1f78b4" in html
    assert html.index("mc-avdisc") < html.index('class="mc-av"'), \
        "the disc must precede the avatar or it paints over the face"
    assert 'class="mc-av" style="position:absolute' in html, \
        "the avatar has to be positioned to paint over the disc"


def test_nothing_hangs_outside_the_wrapper(agent):
    """The crescent used to be a negative offset on an avatar-sized wrapper, so it stuck out — and
    got sliced off by the overflow:hidden on the minister card's top row and the goal chips. The
    wrapper is wider than the avatar instead, with the avatar pushed right."""
    root, a = agent()
    html = agentbits._portrait(root, a, 44)
    assert "left:-" not in html, "nothing may sit at a negative offset; an ancestor will clip it"
    peek = agentbits._colour_peek(44)
    assert f"width:{44 + peek}px" in html, "the wrapper must make room for the crescent"
    assert f"left:{peek}px" in html, "and the avatar sits that far in"


def test_an_agent_with_no_colour_takes_no_extra_width(agent):
    root, a = agent(color="")
    assert "width:44px" in agentbits._portrait(root, a, 44)


def test_the_disc_is_the_same_size_as_the_avatar(agent):
    """Same circle, shifted — so only a crescent shows, thickest at the midline. A larger disc
    would show top and bottom too and read as a ring again."""
    root, a = agent()
    html = agentbits._portrait(root, a, 44)
    disc = html.split("mc-avdisc")[1].split("</span>")[0]
    assert "width:44px" in disc and "height:44px" in disc


@pytest.mark.parametrize("size,peek", [(18, 2), (20, 2), (26, 3), (30, 3), (44, 4), (56, 4), (64, 4)])
def test_the_crescent_scales_with_the_avatar(size, peek):
    assert agentbits._colour_peek(size) == peek


def test_even_the_smallest_avatar_gets_a_visible_crescent():
    """At 1px it read as a rendering artefact rather than as identification."""
    assert agentbits._colour_peek(18) >= 2


def test_an_agent_with_no_colour_gets_no_disc(agent):
    root, a = agent(color="")
    assert "mc-avdisc" not in agentbits._portrait(root, a, 44)


def test_a_caller_can_force_the_colour(agent):
    """The Configure preview needs a disc even for an agent that never had a colour saved, or the
    picker would have nothing to recolour."""
    root, a = agent(color="")
    assert "#33a02c" in agentbits._portrait(root, a, 64, color="#33a02c")


# ---- the status dot ------------------------------------------------------------------------

def test_the_dot_is_off_by_default_and_opt_in(agent):
    """It costs a filesystem check per avatar, and an 18px marker in a goal list doesn't want one."""
    root, a = agent()
    assert "mc-actdot" not in agentbits._portrait(root, a, 44)
    assert "mc-actdot" in agentbits._portrait(root, a, 44, dot=True)


@pytest.mark.parametrize("size", [26, 30, 44, 56, 64])
def test_the_dots_centre_lands_on_the_avatars_edge(size, agent):
    """Half in, half out. The 45° point of a circle is (1-cos45°)/2 ≈ 0.1464 of the diameter in
    from the corner of its bounding box, so that's where the centre has to be — and it means the
    dot still fits inside the square box, with nothing for an ancestor to clip."""
    root, a = agent()
    html = agentbits._portrait(root, a, size, dot=True)
    dot = html.split("mc-actdot")[1].split("></i>")[0]
    right = int(dot.split("right:")[1].split("px")[0])
    d = int(dot.split("width:")[1].split("px")[0])
    centre_from_edge = right + d / 2
    assert abs(centre_from_edge - size * 0.1464) <= 1.0, \
        f"{size}px: centre is {centre_from_edge}px in, wanted ~{size * 0.1464:.1f}px"
    assert right >= 0, "the dot must not overflow the wrapper"


def test_a_call_site_can_nudge_the_dot_a_pixel(agent):
    """The Register's 30px avatars round to a 7px dot, a pixel shy of reading clearly in a dense
    row. The nudge must keep the centre on the edge, not just inflate the dot in place."""
    root, a = agent()
    plain = agentbits._portrait(root, a, 30, dot=True).split("mc-actdot")[1].split("></i>")[0]
    grown = agentbits._portrait(root, a, 30, dot=True, dot_grow=1).split("mc-actdot")[1].split("></i>")[0]
    dw = lambda s: int(s.split("width:")[1].split("px")[0])
    ri = lambda s: int(s.split("right:")[1].split("px")[0])
    assert dw(grown) == dw(plain) + 1
    assert ri(grown) + dw(grown) / 2 <= ri(plain) + dw(plain) / 2 + 0.5, \
        "growing the dot must move it out, not push its centre inward"


def test_the_register_uses_the_nudge():
    from armada.webui import widgets
    src = open(widgets.__file__, encoding="utf-8").read()
    assert "dot=True, dot_grow=1" in src


def test_the_pinned_coordinator_chip_is_grey_not_accent_tinted():
    """It's the one owner you can't remove. Wearing the same accent tint as the removable chips
    implied it could come off too."""
    from armada.webui import goalsview
    src = open(goalsview.__file__, encoding="utf-8").read()
    body = src[src.index("def _goal_owner_chips"):]
    body = body[:body.index("\ndef ", 10)]
    assert "pinned = " in body and "var(--color-divider)" in body
    assert 'style="{pinned}' in body, "the coordinator chip must use the grey style"
    # and the removable ones must still be accent-tinted, or the distinction says nothing
    assert "var(--accent-13)" in body


def test_the_dot_has_no_ring(agent):
    root, a = agent()
    for size in (26, 44, 56):
        dot = agentbits._portrait(root, a, size, dot=True).split("mc-actdot")[1].split("></i>")[0]
        assert "border:" not in dot      # border-radius is fine; a border is not


def test_every_state_colour_is_opaque():
    """They were mixed against `transparent`, which made no visible difference while the dot sat on
    the page background. On an avatar it does two kinds of damage: the photo shows through, and a
    semi-transparent colour won't interpolate, so the working pulse degraded into a flip between two
    flat values."""
    for state, (col, _pulse, _label) in agentbits._ACTIVITY_DOT.items():
        assert "transparent" not in col, f"{state} is still mixed against transparent"


def test_the_dot_paints_a_plain_colour(agent):
    root, a = agent()
    dot = agentbits._portrait(root, a, 44, dot=True).split("mc-actdot")[1].split("></i>")[0]
    assert "background-color:" in dot
    assert "background-image" not in dot, "a gradient here is what stopped the pulse interpolating"


def test_the_dot_transitions_between_states(agent):
    """So unseen→idle reads as the state changing while you watch, not as a repaint."""
    root, a = agent()
    assert "transition:background-color" in agentbits._portrait(root, a, 44, dot=True)


def test_the_pulse_animates_an_interpolatable_property():
    """Two earlier versions failed here: the `background` shorthand wiped the layer the dot needed
    on a photo, and background-image stepped between gradients instead of interpolating."""
    css = _CSS.read_text(encoding="utf-8")
    block = css.split("@keyframes mc-actwork")[1].split("}}")[0]
    assert "background-color:" in block
    assert "background-image" not in block and "{background:" not in block
    assert "transparent" not in block, "a transparent stop can't interpolate smoothly"


@pytest.mark.parametrize("js", ["chat.js", "dash.js", "dotpoll.js"])
def test_every_live_repainter_matches_the_server(js):
    """Three separate pollers repaint these dots, each with its own copy of the colour map. One of
    them drifting breaks a single page, which is the kind of thing found months later."""
    src = (_JS / js).read_text(encoding="utf-8")
    assert "backgroundColor" in src
    assert ".style.background=" not in src.replace(".style.backgroundColor=", ""), \
        "the shorthand would clear the transition and anything else the server set"
    for state, (col, _pulse, _label) in agentbits._ACTIVITY_DOT.items():
        assert col in src, f"{js} is missing the server's {state} colour"


# ---- the dot moved, it didn't multiply -------------------------------------------------------

def test_no_wrapper_clips_a_portrait():
    """overflow:hidden immediately around a portrait slices the crescent off. The portrait already
    rounds itself, so those wrappers were only ever belt-and-braces."""
    webui = Path(agentbits.__file__).parent
    for mod in webui.glob("*.py"):
        for line in mod.read_text(encoding="utf-8").splitlines():
            if "_portrait(" in line and "def _portrait" not in line:
                assert "overflow:hidden" not in line, f"{mod.name}: {line.strip()[:90]}"


def test_the_streaming_turn_clones_the_whole_portrait():
    """While an agent is thinking, chat.js builds its turn client-side. It used to copy the avatar's
    innerHTML into its own round box, which threw the colour crescent away — so the live turn looked
    different from every finished turn above it. It also selected '.mc-av', which matches the header
    portrait's inner circle first, not the template."""
    src = (_JS / "chat.js").read_text(encoding="utf-8")
    assert "querySelector('template.mc-av')" in src, "select the template, not the first .mc-av"
    assert "querySelector('.mc-av')" not in src
    # the line that drops the portrait into the turn — not the bare-SVG fallback above it, which
    # legitimately rounds itself because it isn't a portrait
    insert = next(l for l in src.splitlines() if "'+av+'" in l)
    assert "overflow:hidden" not in insert, "a clipping box here slices the crescent off"


def _seen_fn():
    src = (_JS / "chat.js").read_text(encoding="utf-8")
    return src, src.split("function mcSeenNow(force){")[1].split("\n}")[0]


def test_seeing_a_thread_fades_the_dot_locally_without_waiting():
    """Firing the read request and refreshing immediately raced it, so the dot stayed teal until
    the 4-second poller caught up."""
    _src, fn = _seen_fn()
    assert "mcPaintDot(d,'idle')" in fn, "fade to idle straight away"
    assert "d.dataset.act==='unseen'" in fn, "and only for a dot that was actually unseen"
    assert "mcMarkThreadRead" in fn, "the server still has to be told"


def test_the_fade_does_not_re_enter_the_poller():
    """mcSeenNow is called FROM the poll callback. Calling the poller back from inside it would
    recurse; the next poll reconciles anyway."""
    _src, fn = _seen_fn()
    assert "mcRefreshAgentDot" not in fn
    assert "mcSeenAt" in fn, "and it needs a debounce, since the poll runs every 4s"


def test_a_reply_arriving_while_you_watch_clears_the_dot_again():
    """The case that was actually broken: the thread page was already open when a job finished, so
    nothing marked it read until you navigated away and back."""
    src, _fn = _seen_fn()
    poll = src.split("async function mcRefreshAgentDot")[1].split("\nfunction ")[0]
    assert "mcSeenNow()" in poll


def test_seen_is_wired_to_load_visibility_and_clicks():
    src, _fn = _seen_fn()
    boot = src.split("if(!document.getElementById('mc-turns'))return;")[1].split("})();")[0]
    for hook in ("DOMContentLoaded", "visibilitychange", "'click'"):
        assert hook in boot, f"missing the {hook} trigger"


def test_a_background_tab_does_not_count_as_seen():
    _src, fn = _seen_fn()
    assert "document.hidden" in fn


def test_the_widget_tells_the_page_it_was_read():
    """In a thread widget the thread and the dot describing it are in different documents."""
    src, fn = _seen_fn()
    assert "postMessage({mcThreadSeen:" in fn
    dash = (_JS / "dash.js").read_text(encoding="utf-8")
    assert "mcThreadSeen" in dash and "mcFadeAgentDots" in dash
    assert "mcSeenWidgets" in dash, \
        "the next poll would repaint it teal before the server caught up without this"


def test_the_thread_widget_dot_lives_on_its_avatar():
    dash = (_JS / "dash.js").read_text(encoding="utf-8")
    # mc-tw-dots (the options button) is a different element — match the class exactly
    assert 'class="mc-tw-dot"' not in dash and "'.mc-tw-dot'" not in dash, \
        "the standalone header dot should be gone"
    assert 'class="mc-tw-ava" data-agentdot=' in dash, "the avatar is the poller's hook now"
    pages = (Path(agentbits.__file__).parent / "pages.py").read_text(encoding="utf-8")
    assert "_portrait(realm_root, a, 22, dot=True)" in pages


def test_no_page_still_draws_a_free_standing_status_dot():
    """The dot lives on the avatar now. A page rendering its own would show two."""
    webui = Path(agentbits.__file__).parent
    for mod in webui.glob("*.py"):
        src = mod.read_text(encoding="utf-8")
        body = src.split("def _activity_dot")[0] + src.split("def _activity_dot")[-1] \
            if "def _activity_dot" in src else src
        assert "_activity_dot(_agent_activity" not in body, f"{mod.name} still renders its own dot"
