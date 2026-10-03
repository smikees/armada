"""Companion labels follow Alexander's configuration without probing provider CLIs."""
import pytest

from armada import providers
from armada.alexander import config
from armada.engine import codex
from armada.webui import alexander_window


@pytest.mark.parametrize("chosen,effort,connected,expected,label", [
    ("auto", "auto", ["claude", "codex"], "claude-opus-5-5", "Claude Opus 5.5 · medium"),
    ("auto", "auto", ["codex"], "gpt-6-sol", "gpt-6-sol · medium"),
    ("gpt-6-sol", "high", ["claude", "codex"], "gpt-6-sol", "gpt-6-sol · high"),
    ("gemini:auto", "high", ["gemini"], "gemini:auto", "Gemini Auto (latest Flash) · high"),
])
def test_header_shows_actual_selected_model_and_effort_without_status_probes(
        monkeypatch, chosen, effort, connected, expected, label):
    monkeypatch.setattr(config, "load", lambda: {"model": chosen, "effort": effort, "verbosity": "standard"})
    monkeypatch.setattr(providers, "connected", lambda: connected)
    monkeypatch.setattr(providers, "statuses", lambda **kwargs: pytest.fail("Rendering probed provider CLIs"))
    monkeypatch.setattr(config, "efforts", lambda model: ["auto", "medium", "high"])
    monkeypatch.setattr(codex, "cached_models", lambda: [{"slug": "gpt-6-sol"}])
    html = alexander_window.render()
    assert f'data-model="{expected}" data-effort="' in html
    assert label in html
    assert 'id="mc-ax-model-chip"' in html
    assert 'id="mc-ax-usage"' in html


def test_disconnected_selection_is_still_visible_and_does_not_invent_a_connected_plan(monkeypatch):
    monkeypatch.setattr(config, "load", lambda: {"model": "gpt-6-sol", "effort": "high", "verbosity": "standard"})
    monkeypatch.setattr(providers, "connected", lambda: [])
    html = alexander_window.render()
    assert "gpt-6-sol · high" in html
    assert "selected provider is disconnected" in html
    assert "Uses your Codex plan" not in html
