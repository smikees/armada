"""System usage: tokens ARMADA itself spends, as opposed to the owner's agents.

Two sources today (Mihai, 2026-09-25: "System (any jobs + Alexander if any support
conversations) should be a default line in all cost reports/graphs"):

- system jobs that call Claude directly rather than through an agent (the sign-in keep-alive);
- Alexander's support conversations (docs/dev/ALEXANDER.md).

System jobs that *wake an agent* (inbox dispatch, Telegram) are not System usage: the run is the
agent's, logged in the agent's own run file, and shows under that agent.

One JSON line per run in `<realm>/system_runs.jsonl`, the same shape the agents' run files use
(`ts`, `task`, `model`, `status`, `tokens`), so the usage code can read both the same way.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from . import clock as _clock
from .util import swallowed

log = logging.getLogger(__name__)

FILE = "system_runs.jsonl"
NAME = "System"
# Neutral slate: System is always present in the legend and must never be mistaken for an agent,
# whose colours come from the ColorBrewer "Paired" palette.
COLOR = "#8a94a6"


def _path(realm_root) -> Path:
    return Path(realm_root) / FILE


def record(realm_root, task: str, model: str, tokens: dict, ok: bool = True) -> None:
    """Append one System run. Never raises: accounting must not break the work it accounts for."""
    ev = {"ts": _clock.now().replace(tzinfo=None).isoformat(timespec="seconds"),
          "task": task, "model": model or "", "status": "ok" if ok else "failed",
          "tokens": tokens if isinstance(tokens, dict) else {}}
    try:
        with _path(realm_root).open("a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    except Exception:  # noqa
        swallowed(log, 'record: failed; ignored')


def runs(realm_root) -> list[dict]:
    p = _path(realm_root)
    out: list[dict] = []
    try:
        text = p.read_text(encoding="utf-8-sig") if p.exists() else ""
    except Exception:  # noqa
        swallowed(log, 'runs: failed; returning a fallback')
        return out
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            ev = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if isinstance(ev, dict):
            out.append(ev)
    return out
