"""Realm goals — the objectives agents actively advance (distinct from passive memory).

A goal is a Markdown file under <realm>/goals/, one per goal, with frontmatter:

    ---
    title: Reach EUR 2.5M net worth
    status: On track
    target: 2026-12-31
    agents: warren,ray
    ---
    Description / what "done" looks like...

`agents` is the explicit list of non-coordinator agents mapped to the goal. The
coordinator is ALWAYS mapped (by default, non-removable) and is handled at read
time via the is_coord flag rather than being stored in every file — so a change of
coordinator never leaves stale mappings behind.

Mapped goals are injected into an agent's always-on core (memory.assemble_core), so
they load into every thread for the agents that advance them.
"""
from __future__ import annotations
import datetime
import re
from pathlib import Path

from . import memory
from .util import safe_seg, write_text_atomic, UnsafeSegment

STATUSES = ["Not started", "On track", "At risk", "Blocked", "Done"]


def _dir(realm_root) -> Path:
    return Path(realm_root) / "goals"


def _slug(text: str) -> str:
    """A safe filename stem from arbitrary text (lowercase alnum + dashes)."""
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:60] or "goal"


def _agents_list(meta: dict) -> list[str]:
    return [a.strip() for a in (meta.get("agents") or "").split(",") if a.strip()]


def _fmt_target(target: str) -> str:
    """ISO date -> a friendlier 'dd Mon yyyy'; pass through anything unparseable."""
    t = (target or "").strip()
    if not t:
        return ""
    try:
        return datetime.date.fromisoformat(t).strftime("%d %b %Y")
    except ValueError:
        return t


def _overdue(target: str) -> bool:
    t = (target or "").strip()
    if not t:
        return False
    try:
        return datetime.date.fromisoformat(t) < datetime.date.today()
    except ValueError:
        return False


def list_goals(realm_root) -> list[dict]:
    """Every goal as a dict. `effective_status` applies the rule 'a goal whose ETA is in the
    past is At risk' (unless it's Done); `overdue` flags that case for styling."""
    d = _dir(realm_root)
    out: list[dict] = []
    if d.is_dir():
        for f in sorted(d.glob("*.md")):
            meta, body = memory._frontmatter(f.read_text(encoding="utf-8-sig"))
            target = meta.get("target", "")
            status = meta.get("status", "")
            overdue = _overdue(target)
            effective = "At risk" if (overdue and status != "Done") else status
            out.append({
                "stem": f.stem,
                "title": meta.get("title", f.stem),
                "status": status,
                "effective_status": effective,
                "target": target,
                "target_label": _fmt_target(target),
                "overdue": overdue,
                "agents": _agents_list(meta),
                "body": body.strip(),
                "modified": datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%d-%m-%y"),
            })
    return out


def get_goal(realm_root, stem: str) -> dict | None:
    stem = safe_seg(stem, "goal")
    f = _dir(realm_root) / f"{stem}.md"
    if not f.is_file():
        return None
    for g in list_goals(realm_root):
        if g["stem"] == stem:
            return g
    return None


def _write(realm_root, stem: str, title: str, status: str, target: str,
           body: str, agents: list[str]) -> None:
    stem = safe_seg(stem, "goal")
    ag = ",".join(safe_seg(a, "agent") for a in agents)
    fm = ["---", f"title: {title}", f"status: {status}", f"target: {target}", f"agents: {ag}", "---"]
    write_text_atomic(_dir(realm_root) / f"{stem}.md", "\n".join(fm) + "\n" + (body or "").strip() + "\n")


def save_goal(realm_root, title: str, body: str, status: str = "", target: str = "",
              agents: list[str] | None = None, stem: str | None = None) -> str:
    """Create a new goal or edit an existing one (when `stem` names an existing file).
    Returns the goal's stem. Preserves the existing agent mapping on edit unless
    `agents` is explicitly provided."""
    title = (title or "").strip()
    if not title and not (body or "").strip():
        raise ValueError("a goal needs a title or description")
    existing = None
    if stem:
        stem = safe_seg(stem, "goal")
        if (_dir(realm_root) / f"{stem}.md").exists():
            existing = get_goal(realm_root, stem)
    if agents is None:
        agents = existing["agents"] if existing else []
    if existing:
        _write(realm_root, stem, title or existing["title"], status, target, body, agents)
        return stem
    base = _slug(title or body[:40])
    new = base
    n = 2
    while (_dir(realm_root) / f"{new}.md").exists():
        new = f"{base}-{n}"
        n += 1
    _write(realm_root, new, title, status, target, body, agents)
    return new


def set_agents(realm_root, stem: str, agents: list[str]) -> None:
    """Replace the mapped (non-coordinator) agents for a goal."""
    g = get_goal(realm_root, stem)
    if not g:
        raise ValueError(f"no goal '{stem}'")
    _write(realm_root, g["stem"], g["title"], g["status"], g["target"], g["body"], agents)


def delete_goal(realm_root, stem: str) -> bool:
    stem = safe_seg(stem, "goal")
    f = _dir(realm_root) / f"{stem}.md"
    if f.is_file():
        f.unlink()
        return True
    return False


def goals_for_agent(realm_root, agent_id: str, is_coord: bool = False) -> list[dict]:
    """Goals this agent advances: all of them if it's the coordinator, else the ones
    whose agent mapping names it."""
    return [g for g in list_goals(realm_root) if is_coord or agent_id in g["agents"]]
