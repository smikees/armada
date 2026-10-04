"""Release-owned defaults for new teams, independent of Alexander's personal settings.

Only authenticated providers participate. Seed catalogues are UI suggestions, not evidence
that a pinned model is available: an unknown/unavailable catalogue uses the CLI's default.
Review PREFERENCES with each release; existing realms and explicit agent/job picks stay put.
"""
from __future__ import annotations

from .. import __version__

# General-purpose team preference, not a claim that one provider wins every task.
PREFERENCES = (
    ("claude", ("claude-opus-5-5", "claude-sonnet-5")),
    ("codex", ("gpt-6.1-sol", "gpt-6-sol")),
    ("gemini", ("gemini-3.8-flash", "gemini-3.7-flash")),
)


def catalogues(states: dict) -> dict:
    """Read vendor model metadata during setup, never on a page-render path."""
    from .. import models
    from .codex import cached_models
    result = {}
    if states.get("claude", {}).get("connected"):
        result["claude"] = models.fetch_live_result()[0] or []
    if states.get("codex", {}).get("connected"):
        result["codex"] = cached_models()
    if states.get("gemini", {}).get("connected"):
        # status() just queried `agy models`; do not substitute the bundled seed.
        result["gemini"] = states["gemini"].get("models") or []
    return result


def choose(states: dict, available: dict | None = None) -> dict:
    """Return persistable realm defaults, or refuse setup when no engine can run."""
    connected = [p for p, _ in PREFERENCES if states.get(p, {}).get("connected") is True]
    if not connected:
        raise ValueError("Connect a provider before appointing your team.")
    available = catalogues(states) if available is None else available
    provider, preferred = next((p, mids) for p, mids in PREFERENCES if p in connected)
    entries = available.get(provider)
    entries = entries if isinstance(entries, list) else []
    rows = {str(row.get("slug") or row.get("id")): row
            for row in entries
            if isinstance(row, dict) and row.get("active", True)
            and row.get("visibility", "list") == "list"}
    model = next((mid for mid in preferred if mid in rows), provider + ":default")
    effort = "medium" if model in rows else "auto"
    row = rows.get(model, {})
    metadata = row.get("efforts") or row.get("supported_reasoning_levels") or []
    levels = [(item.get("effort") or item.get("reasoning_effort")) if isinstance(item, dict) else item
              for item in metadata] if isinstance(metadata, list) else []
    if levels and effort not in levels:
        effort = next((level for level in ("high", "low", "xhigh", "max") if level in levels), "auto")
    return {"providers": connected, "provider": provider, "default_engine": provider,
            "default_model": model, "default_effort": effort,
            "default_selection": {"release": __version__, "reason":
                "release-preference" if model in rows else "provider-default"}}
