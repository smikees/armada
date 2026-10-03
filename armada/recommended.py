"""Starter capabilities with explicit upstream sources and connection requirements.

Skills are downloaded through the catalogue. Optional MCP entries are saved for setup,
not reported as connected: their upstream installers and account consent are separate.
See docs/dev/STARTER_CAPABILITIES.md for the reviewed shortlist and integration work.
"""
from __future__ import annotations

REVIEWED = "2026-09-28"

# (group id, group title, one line for the wizard)
GROUPS: tuple[tuple[str, str, str], ...] = (
    ("connections", "Connections", "Optional services and computer access; each needs its own setup."),
    ("documents", "Documents", "Read, write and edit the files work runs on."),
    ("writing", "Writing", "Drafts that are structured, clear and in the right format."),
    ("judgement", "Judgement", "Help checking advice before you act on it."),
    ("look", "Look and feel", "Make what they produce look finished."),
)

RECOMMENDED: tuple[dict, ...] = (
    {"key": "workspace-mcp/connectors/google-workspace", "id": "google-workspace", "group": "connections",
     "kind": "connectors", "name": "Google Drive, Gmail & Calendar", "author": "Taylor Wilsdon (community)",
     "source": "workspace-mcp", "homepage": "https://github.com/taylorwilsdon/google_workspace_mcp",
     "guide": "https://workspacemcp.com/quick-start",
     "does": "Search your files and email and read your calendar through one Google Workspace connection.",
     "note": "Requires a Google Cloud OAuth client and browser consent. Start with read-only access to Drive, Gmail and Calendar. Broader permissions can send mail or change files.",
     "install": {"packages": [{"identifier": "workspace-mcp"}]},
     "default": False},
    {"key": "cursortouch/extensions/windows-mcp", "id": "windows-mcp", "group": "connections",
     "kind": "extensions", "name": "Windows MCP", "author": "CursorTouch (community)",
     "source": "cursortouch", "homepage": "https://github.com/CursorTouch/Windows-MCP",
     "guide": "https://github.com/CursorTouch/Windows-MCP#-installation",
     "does": "Let agents see and operate Windows apps: click, type, inspect the screen and run commands.",
     "note": "Requires uv and the Windows MCP package. Gives access to desktop apps, files, terminal commands and the network.",
     "install": {"packages": [{"identifier": "windows-mcp"}]}, "default": False},
    {"key": "anthropic-skills/skills/docx", "id": "docx", "group": "documents",
     "name": "Word documents",
     "does": "Create, read and edit Word files: letters, reports, contracts, with proper headings, "
             "tables and page numbers.",
     "note": "Carries helper scripts the agent runs on the file it's working on.",
     "default": True},
    {"key": "anthropic-skills/skills/xlsx", "id": "xlsx", "group": "documents",
     "name": "Spreadsheets",
     "does": "Build and fix Excel and CSV files: budgets, trackers, models with working formulas "
             "and charts.",
     "note": "Carries helper scripts the agent runs on the file it's working on.",
     "default": True},
    {"key": "anthropic-skills/skills/pptx", "id": "pptx", "group": "documents",
     "name": "Presentations",
     "does": "Make and edit PowerPoint decks, or pull the content out of one.",
     "note": "Carries helper scripts the agent runs on the file it's working on.",
     "default": True},
    {"key": "anthropic-skills/skills/pdf", "id": "pdf", "group": "documents",
     "name": "PDFs",
     "does": "Read, fill in, merge, split and create PDFs, including forms and scanned pages.",
     "note": "Carries helper scripts the agent runs on the file it's working on.",
     "default": True},
    {"key": "anthropic-skills/skills/doc-coauthoring", "id": "doc-coauthoring", "group": "writing",
     "name": "Writing partner",
     "does": "Works through a proposal, plan or brief with you step by step, and checks it reads "
             "well to the person it's for.",
     "note": "", "default": True},
    {"key": "anthropic-skills/skills/internal-comms", "id": "internal-comms", "group": "writing",
     "name": "Updates and reports",
     "does": "Status reports, updates, newsletters and FAQs in the formats organisations use.",
     "note": "", "default": False, "default_for": ("company",)},
    {"key": "anthropic-skills/skills/discernment-nudge", "id": "discernment-nudge", "group": "judgement",
     "name": "Second look",
     "does": "After advice, a plan or an estimate, adds two or three pointed questions to check "
             "the facts and assumptions it rests on.",
     "note": "", "default": True},
    {"key": "anthropic-skills/skills/theme-factory", "id": "theme-factory", "group": "look",
     "name": "Themes",
     "does": "Gives slides, documents and pages a consistent set of colours and fonts.",
     "note": "", "default": False},
    {"key": "anthropic-skills/skills/canvas-design", "id": "canvas-design", "group": "look",
     "name": "Posters and visuals",
     "does": "Original posters, covers and one-page visuals as images or PDFs.",
     "note": "", "default": False},
)


def for_template(template: str) -> list[dict]:
    """The list with `on` set for this template: an entry's own default, or its default_for."""
    out = []
    for r in RECOMMENDED:
        on = bool(r.get("default")) or template in (r.get("default_for") or ())
        out.append({**r, "on": on})
    return out


def by_key(key: str) -> dict | None:
    return next((r for r in RECOMMENDED if r["key"] == key), None)
