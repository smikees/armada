"""System skills — the skills ARMADA itself needs to work.

A system skill ships inside the package (armada/system_skills/<id>/SKILL.md), not in the realm
folder. That's the whole mechanism behind "locked": there is nothing in the user's realm to edit or
delete, and the skill is versioned with the app, so it improves when ARMADA updates. They're shown
in the UI rather than hidden — the app runs these against the user's own capabilities, and that
should be inspectable.

Everything here is read-only and best-effort: a missing or malformed bundle degrades to "no system
skills" rather than breaking the Capabilities page.
"""
from __future__ import annotations
from pathlib import Path

from . import __version__
import logging
from .util import swallowed
log = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent / "system_skills"


def _parse_front(text: str) -> tuple:
    """Split a leading '---' frontmatter block off a SKILL.md. Returns (meta, body).

    Deliberately tiny (stdlib-only, no yaml): keys are `key: value`, one per line. Anything more
    elaborate belongs in the body, not the header.
    """
    meta, body = {}, text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            head = text[3:end]
            body = text[end + 4:].lstrip("\n")
            for ln in head.splitlines():
                ln = ln.strip()
                if not ln or ln.startswith("#") or ":" not in ln:
                    continue
                k, v = ln.split(":", 1)
                meta[k.strip().lower()] = v.strip().strip('"').strip("'")
    return meta, body


def _one(d: Path) -> dict | None:
    md = d / "SKILL.md"
    try:
        text = md.read_text(encoding="utf-8-sig")
    except Exception:  # noqa — unreadable bundle: skip it, don't break the page
        swallowed(log, '_one: failed; returning a fallback')
        return None
    meta, body = _parse_front(text)
    return {
        "id": d.name,
        "name": meta.get("name") or d.name.replace("-", " ").title(),
        "description": meta.get("description") or "",
        # system skills are versioned with the app: they update when ARMADA updates
        "version": meta.get("version") or __version__,
        "runs": meta.get("runs") or "reads",
        "why": meta.get("why") or "Bundled with ARMADA — it updates with the app.",
        "path": str(md),
        "body": body,
        "system": True,
        "locked": True,
    }


def list_system_skills() -> list:
    """Every bundled system skill, sorted by name. [] if the bundle is missing."""
    if not _ROOT.is_dir():
        return []
    out = []
    for d in sorted(_ROOT.iterdir()):
        if d.is_dir() and (d / "SKILL.md").exists():
            it = _one(d)
            if it:
                out.append(it)
    return sorted(out, key=lambda x: x["name"].lower())


def get_system_skill(sid: str) -> dict | None:
    """One system skill by id, or None. Guards against path traversal via the id."""
    if not sid or "/" in sid or "\\" in sid or ".." in sid:
        return None
    d = _ROOT / sid
    return _one(d) if (d.is_dir() and (d / "SKILL.md").exists()) else None
