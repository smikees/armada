"""ARMADA's recommended capabilities: the curated set the setup wizard offers (launch plan 6.4).

Mihai, 2026-09-25: "a curated selection of capabilities that are most useful and safest relative to
their power that users can enable from the setup phase."

How the list was chosen (reviewed 2026-09-25 against the live sources):

* **Only official sources.** Every entry is in the catalogue the app already mirrors, from
  Anthropic's own `anthropics/skills` repository. Nothing self-published, nothing that needs an
  account, a key or a paid service.
* **Low risk by the app's own rule.** All are skills, which ARMADA files as Low risk: instructions an
  agent reads (catalogue.realm.inspect). Four of them (the document skills) also carry helper
  scripts, which the agent runs with the tools it already has and on files you give it; they add
  no new reach. Said here, and on each entry, because "Low" should never hide that.
* **Useful to anyone.** Things a team running someone's work or life does every week: documents,
  spreadsheets, slides, PDFs, careful writing, a second look at advice.
* **Left out on purpose:** connectors to your accounts (Notion, Slack, GitHub, Google…), browsers
  and terminals, anything with hooks. They can be the most useful of all, and they act in your
  name; each is added from Capabilities, reviewed, one agent at a time.

Each entry names its catalogue key, so the wizard adds it through the normal path
(catalogue.add_to_realm), and the Capabilities page shows it like anything else.
"""
from __future__ import annotations

REVIEWED = "2026-09-25"

# (group id, group title, one line for the wizard)
GROUPS: tuple[tuple[str, str, str], ...] = (
    ("documents", "Documents", "Read, write and edit the files work runs on."),
    ("writing", "Writing", "Drafts that are structured, clear and in the right format."),
    ("judgement", "Judgement", "Help checking advice before you act on it."),
    ("look", "Look and feel", "Make what they produce look finished."),
)

RECOMMENDED: tuple[dict, ...] = (
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
