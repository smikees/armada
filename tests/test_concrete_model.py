"""Engine logs the concrete versioned model id, not a bare family alias (so usage shows 'Opus 4.8').

The Claude CLI's result `model` field is sometimes just the alias we passed ('opus'); the concrete id
lives in `modelUsage`. _concrete_model prefers that — this is what makes the graph tooltip show the
exact version.
"""
from armada.engine.claude import _concrete_model
from armada.webui import _pretty_model


def test_prefers_modelusage_when_reported_is_a_bare_alias():
    got = _concrete_model("opus", {"claude-opus-4-8-20260501": {"in": 1}}, "opus")
    assert got == "claude-opus-4-8-20260501"
    assert _pretty_model(got) == "Opus 4.8"          # what the tooltip/legend will show


def test_keeps_reported_when_already_concrete():
    assert _concrete_model("claude-opus-5", {}, "") == "claude-opus-5"


def test_uses_modelusage_when_reported_empty():
    assert _concrete_model("", {"claude-sonnet-4-5-x": {}}, "sonnet") == "claude-sonnet-4-5-x"


def test_falls_back_to_alias_when_no_modelusage():
    assert _concrete_model("opus", {}, "opus") == "opus"        # nothing better available


def test_picks_primary_model_not_a_background_model():
    # Claude Code may use a small background model (e.g. Haiku for titles) alongside the real one;
    # even when it's listed first, we must report the model that did the most work.
    mu = {"claude-haiku-4-5-20251001": {"inputTokens": 40, "outputTokens": 10},
          "claude-opus-5": {"inputTokens": 5000, "outputTokens": 1200}}
    assert _concrete_model("opus", mu, "claude-opus-5") == "claude-opus-5"
