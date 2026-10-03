"""Resolve the provider from the chosen model, keeping old Claude realms readable."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)
PROVIDERS = ("claude", "codex", "gemini")


def read_config(path) -> dict:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        log.debug("Provider configuration unavailable: %s", path, exc_info=True)
        return {}


def model_provider(model: str) -> str:
    value = str(model or "").strip().lower()
    if value.startswith(("gemini:", "gemini-", "gemini ", "google · gemini")):
        return "gemini"
    if value.startswith(("codex:", "openai:", "gpt-", "gpt ", "chatgpt-")) or re.match(r"o[1-9](?:-|$)", value):
        return "codex"
    if value.startswith("claude") or value in ("opus", "sonnet", "haiku", "fable"):
        return "claude"
    return ""


def enabled_providers(realm_root) -> list[str]:
    cfg = read_config(Path(realm_root) / "realm.json")
    configured = cfg.get("providers")
    if not isinstance(configured, list) or not configured:
        configured = [cfg.get("provider") or cfg.get("default_engine") or "claude"]
    return [p for p in PROVIDERS if p in configured] or ["claude"]


def engine_for(realm_root, agent=None, job=None, override=None) -> str:
    """Explicit CLI override → job model → agent model → realm model → legacy engine.

    The provider checkboxes control the picker, not stored choices: hiding a provider must not
    silently migrate an existing agent or scheduled job to a different model.
    """
    if override and override != "auto":
        return str(override)
    root = Path(realm_root)
    if isinstance(agent, str):
        agent = read_config(root / "agents" / agent / "agent.json")
    agent = agent or {}
    cfg = read_config(root / "realm.json")
    for value in ((job or {}).get("model"), agent.get("model"), cfg.get("default_model")):
        provider = model_provider(value)
        if provider:
            return provider
    return str(agent.get("engine") or cfg.get("provider") or cfg.get("default_engine") or "claude")
