"""Model token-consumption index — colours the model icon on a light→dark gradient.

model_index ranks a model on its own (cheapest model = 0, priciest = 99); combo_index ranks a
model + effort + verbosity against the cheapest/priciest combination reachable. Log-scaled, so the
~100x cost span reads evenly.
"""
from armada import models as m
from armada.webui import _consumption_color


def test_model_index_spans_full_range_cheapest_to_priciest():
    assert m.model_index("Haiku 4.5") == 0            # cheapest family → 0
    assert m.model_index("Fable 5.1") == 99           # priciest family → 99
    # monotonic by price: Haiku < Sonnet < Opus < Fable
    order = [m.model_index(x) for x in ("Haiku 4.5", "Sonnet 5", "Opus 5", "Fable 5.1")]
    assert order == sorted(order) and len(set(order)) == 4


def test_combo_index_effort_raises_consumption():
    lo = m.combo_index("Opus 5", "low")
    hi = m.combo_index("Opus 5", "max")
    assert 0 <= lo < hi <= 99                          # more effort → higher on the gradient


def test_combo_extremes_pin_to_0_and_99():
    """The scale spans what is actually reachable, so the ends include verbosity too — otherwise
    the marker could never touch either end of the bar it sits on."""
    assert m.combo_index("Haiku 4.5", "low", "terse") == 0
    assert m.combo_index("Fable 5.1", "max", "full") == 99


def test_unknown_model_falls_back_not_crash():
    assert 0 <= m.model_index("claude-something-new") <= 99


def test_gradient_endpoints_are_green_and_red():
    # traffic-light spectrum: green (low cost) -> red (high cost)
    assert _consumption_color(0).lower() == "#469b52"   # green (low)
    assert _consumption_color(99).lower() == "#c43a2e"  # red (high)


# --------------------------------------------------------------------------- verbosity

def test_verbosity_moves_the_marker():
    """It buys WRITING where effort buys THINKING — a real driver, so the widget should react."""
    idx = [m.combo_index("Opus 5", "high", v) for v in ("terse", "brief", "standard", "full")]
    assert idx == sorted(idx), f"not monotonic: {idx}"
    assert idx[0] < idx[-1], "verbosity changes nothing"


def test_verbosity_stays_the_junior_partner():
    """The reply is the smaller half of an agent's output, so this must not outrank effort — a
    detailed low-effort agent has to read as cheaper than a terse high-effort one."""
    assert m.combo_index("Opus 5", "low", "full") < m.combo_index("Opus 5", "high", "terse")
    assert m.combo_index("Opus 5", "medium", "full") < m.combo_index("Opus 5", "high", "terse")


def test_verbosity_does_not_outrank_the_model_either():
    assert m.combo_index("Haiku 4.5", "high", "full") < m.combo_index("Opus 5", "high", "terse")


def test_its_span_is_narrower_than_efforts():
    """A judgement, but a checkable one: 1.6x against effort's 10x."""
    vs = list(m._VERBOSITY_MULT.values())
    es = list(m._EFFORT_MULT.values())
    assert (max(vs) / min(vs)) < (max(es) / min(es)) / 4


def test_standard_is_the_neutral_point():
    """An agent that never touched the setting should sit where it always did."""
    assert m.verbosity_mult("standard") == 1.0
    assert m.verbosity_mult("") == 1.0
    assert m.verbosity_mult("nonsense") == 1.0


def test_every_verbosity_level_has_a_multiplier():
    """A level in the UI with no entry here would silently price as standard."""
    from armada import verbosity as V
    assert set(m._VERBOSITY_MULT) == set(V.LEVELS)
    assert m._VERBOSITY_DEFAULT == V.DEFAULT


def test_callers_that_know_nothing_about_verbosity_still_work():
    """The Usage breakdown and the model chips pass model+effort only."""
    assert 0 <= m.combo_index("Opus 5", "high") <= 99
    assert m.combo_index("Opus 5", "high") == m.combo_index("Opus 5", "high", "standard")


def test_the_browser_gets_the_same_tables():
    """The marker is computed client-side; it has to arrive at the number this module would."""
    t = m.js_tables()
    assert t["verbosity"] == m._VERBOSITY_MULT
    assert t["verbosityDefault"] == m._VERBOSITY_DEFAULT
    assert t["comboMin"] < t["comboMax"]


def test_the_js_mirror_applies_all_three_factors():
    from pathlib import Path
    from armada.webui.consumption import _consumption_js
    import armada.webui as webui_pkg

    class _R:
        default_model, default_effort, root = "Claude Opus 5", "high", "."
    js = _consumption_js(_R(), verbosity_id="c-verbosity")
    static_js = (Path(webui_pkg.__file__).parent / "static" / "js" / "consumption.js").read_text(
        encoding="utf-8")
    assert "baseCost(m)*mult*vm" in static_js, "the JS still ignores verbosity"
    assert "defaultVerbosity" in js, "a blank (inherit) verbosity has nothing to fall back to"
    assert "c-verbosity" in js
