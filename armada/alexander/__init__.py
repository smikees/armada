"""Alexander — ARMADA's guide (Phase 6; docs/dev/ALEXANDER.md, ADR-012).

The one bundled agent: the same identity in every install, not part of any realm.
Scripted in the setup wizard (`wizard_script`), live in support. This module holds what's fixed
about him; the prompt is `PROMPT.md` beside it, shipped with the app.
"""
from __future__ import annotations

from pathlib import Path

NAME = "Alexander"
ROLE = "ARMADA's guide"
# Preferred Claude defaults. App → Advanced overrides model/effort via config.py;
# Automatic chooses these whenever Claude is connected, otherwise the Codex defaults.
MODEL = "claude-opus-5-5"
EFFORT = "medium"
# The oldest Claude Code that can run MODEL. Claude Code refuses an older one with "API Error: 400 …
# version 2.1.280 or newer is required" (seen 2026-09-25 on 2.1.263). The setup wizard checks it.
MIN_CLAUDE_CODE = "2.1.280"
AVATAR = "/static/alexander.png"
PROMPT_FILE = Path(__file__).resolve().parent / "PROMPT.md"


def prompt() -> str:
    """The system prompt, without the leading reviewer comment."""
    text = PROMPT_FILE.read_text(encoding="utf-8")
    start = text.find("-->")
    return text[start + 3:].strip() if text.lstrip().startswith("# Alexander") and start != -1 else text
