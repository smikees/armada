"""App-level (per-machine) configuration — distinct from a realm's own files.

Stored at ~/.armada/config.json, this holds preferences that belong to the ARMADA install
rather than to any single realm (e.g. the chosen visual theme). Kept tiny and best-effort:
a missing or corrupt file reads as empty defaults, never an error.
"""
from __future__ import annotations
import json
from pathlib import Path
import logging
from . import util
from .util import swallowed
log = logging.getLogger(__name__)


def _path() -> Path:
    return util.data_dir() / "config.json"


def load() -> dict:
    p = _path()
    try:
        return json.loads(p.read_text(encoding="utf-8-sig")) if p.exists() else {}
    except Exception:  # noqa — a bad config must never break rendering
        swallowed(log, 'load: failed; returning a fallback')
        return {}


def get(key: str, default=None):
    return load().get(key, default)


def save(updates: dict) -> None:
    """Merge `updates` into the existing config and write atomically."""
    from . import util
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    cfg = load()
    cfg.update(updates)
    util.write_json_atomic(p, cfg)
