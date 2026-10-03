"""Appointment dates are profile history, not configuration modification times."""
from __future__ import annotations

import datetime
import os
from pathlib import Path


def _birthtime(path: Path) -> float | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    # Unix ctime is metadata change time, not creation time. Windows exposes birthtime
    # on Python 3.12+, and ctime on older embedded runtimes.
    return getattr(stat, "st_birthtime", stat.st_ctime if os.name == "nt" else None)


def appointment_date(config: dict, agent_dir: Path) -> str:
    """Prefer recorded history; recover a best-known date for pre-date-field profiles.

    Folder creation survives atomic agent.json replacement on Windows. Without a
    filesystem creation time, use the oldest core profile timestamp as a legacy
    estimate. The format migration saves this result once, before future edits.
    Imported portraits are excluded: their dates can predate the agent itself.
    """
    recorded = config.get("appointed") or config.get("created")
    if recorded:
        return str(recorded)
    born = _birthtime(agent_dir)
    if born is None:
        dates = []
        for name in ("agent.json", "mandate.md", "soul.md", "tenets.md"):
            try:
                dates.append((agent_dir / name).stat().st_mtime)
            except OSError:
                continue
        born = min(dates) if dates else None
    if born is None:
        return ""
    try:
        return datetime.date.fromtimestamp(born).isoformat()
    except (OSError, OverflowError, ValueError):
        return ""
