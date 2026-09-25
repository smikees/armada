"""Alexander — ARMADA's guide (Phase 6; docs/dev/ALEXANDER.md, ADR-012).

The one bundled agent: the same in every install, not part of any realm, not editable by the owner.
Scripted in the setup wizard (`wizard_script`), live in support. This module holds what's fixed
about him; the prompt is `PROMPT.md` beside it, shipped with the app.
"""
from __future__ import annotations

from pathlib import Path

NAME = "Alexander"
ROLE = "ARMADA's guide"
# Fixed for this version (Mihai, 2026-09-25): Opus 5.5 at High effort for in-app support. The id is
# the one Anthropic's model list returns (checked against the synced catalogue, 2026-09-25).
MODEL = "claude-opus-5-5"
EFFORT = "high"
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
