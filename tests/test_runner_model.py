"""Model-label -> CLI-selector mapping. Regression guard for two prod bugs:

  1. an inaccessible default ('Claude Opus 4.8') reaching the CLI verbatim, and
  2. that same label silently resolving to the family alias 'opus', so an agent the UI showed as
     Opus 4.8 actually ran on claude-opus-5. The run reports in the live realm recorded the
     upgrade; nothing in the interface did.

The catalogue is the label -> id authority. The alias path is the fallback for when it has no
answer, so the tests below pin BOTH: with a catalogue we demand the exact id, without one we
accept the alias.
"""
import json

from armada import runner


def _catalogue(tmp_path, rows):
    """Write a models cache where armada.models.load() will find it."""
    from armada import models
    p = models._path(tmp_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"updated_at": "2026-09-16", "models": rows}), encoding="utf-8")
    return tmp_path


REAL_ROWS = [
    {"id": "claude-opus-5", "label": "Claude Opus 5", "active": True},
    {"id": "claude-opus-4-8", "label": "Claude Opus 4.8", "active": True},
    {"id": "claude-sonnet-4-6", "label": "Claude Sonnet 4.6", "active": True},
    {"id": "claude-haiku-4-5-20251001", "label": "Claude Haiku 4.5", "active": True},
    {"id": "claude-haiku-4-5", "label": "Claude Haiku 4.5", "active": False},
]


def test_catalogue_pins_the_named_version(tmp_path):
    """The whole point: the label names 4.8, so 4.8 is what runs."""
    r = _catalogue(tmp_path, REAL_ROWS)
    assert runner._cli_model("Claude Opus 4.8", r) == "claude-opus-4-8"
    assert runner._cli_model("Claude Sonnet 4.6", r) == "claude-sonnet-4-6"
    assert runner._cli_model("Claude Opus 5", r) == "claude-opus-5"


def test_catalogue_lookup_ignores_retired_entries(tmp_path):
    """Two rows share the label 'Claude Haiku 4.5'; only the live one is a valid pin."""
    r = _catalogue(tmp_path, REAL_ROWS)
    assert runner._cli_model("Claude Haiku 4.5", r) == "claude-haiku-4-5-20251001"


def test_catalogue_lookup_is_case_and_space_insensitive(tmp_path):
    r = _catalogue(tmp_path, REAL_ROWS)
    assert runner._cli_model("  claude opus 4.8 ", r) == "claude-opus-4-8"


def test_label_absent_from_catalogue_falls_back_to_family_alias(tmp_path):
    r = _catalogue(tmp_path, [{"id": "claude-opus-5", "label": "Claude Opus 5", "active": True}])
    assert runner._cli_model("Claude Opus 4.7", r) == "opus"


def test_family_aliases_without_a_catalogue():
    # No realm root -> no catalogue to consult; an alias is the safest thing we can still say.
    assert runner._cli_model("Claude Opus 4.8") == "opus"
    assert runner._cli_model("opus") == "opus"
    assert runner._cli_model("Claude Sonnet 4.5") == "sonnet"
    assert runner._cli_model("Claude Haiku 4.5") == "haiku"


def test_exact_v5_ids_without_a_catalogue():
    assert runner._cli_model("Claude Opus 5") == "claude-opus-5"
    assert runner._cli_model("Claude Sonnet 5") == "claude-sonnet-5"
    assert runner._cli_model("Claude Fable 5") == "claude-fable-5"


def test_concrete_ids_pass_through(tmp_path):
    r = _catalogue(tmp_path, REAL_ROWS)
    for mid in ["claude-fable-5-1", "claude-haiku-4-5-20251001", "claude-opus-4-8"]:
        assert runner._cli_model(mid, r) == mid
        assert runner._cli_model(mid) == mid


def test_empty_and_unknown():
    assert runner._cli_model("") == ""
    assert runner._cli_model(None) == ""
    assert runner._cli_model("Some Other Model") == ""


def test_never_returns_raw_inaccessible_label():
    # whatever we pass, we never hand the CLI a spaced display label
    for label in ["Claude Opus 4.8", "Claude Sonnet 5", "opus", "weird"]:
        assert " " not in runner._cli_model(label)


def test_resolution_chain_uses_the_catalogue(tmp_path):
    """_resolve_model / _resolve_fallback_model must pass the realm through, or the fix is
    real in _cli_model and absent everywhere it matters."""
    r = _catalogue(tmp_path, REAL_ROWS)
    (r / "realm.json").write_text(json.dumps({
        "default_model": "Claude Opus 4.8",
        "default_fallback_model": "Claude Sonnet 4.6",
    }), encoding="utf-8")

    # agent inherits the realm default
    assert runner._resolve_model(r, {}) == "claude-opus-4-8"
    assert runner._resolve_fallback_model(r, {}) == "claude-sonnet-4-6"

    # agent overrides win, and are pinned too
    assert runner._resolve_model(r, {"model": "Claude Opus 5"}) == "claude-opus-5"
    assert runner._resolve_fallback_model(r, {"fallback_model": "Claude Opus 4.8"}) == "claude-opus-4-8"
