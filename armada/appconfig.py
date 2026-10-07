"""App-level (per-machine) configuration — distinct from a realm's own files.

Stored at ~/.armada/config.json, this holds preferences that belong to the ARMADA install
rather than to any single realm (e.g. the chosen visual theme). Kept tiny and best-effort:
a missing or corrupt file renders with empty defaults. Mutations require a readable object
and never overwrite an unreadable or damaged file.
"""
from __future__ import annotations
import time
from pathlib import Path
import logging
from . import util
from .util import swallowed
log = logging.getLogger(__name__)


def _path() -> Path:
    return util.data_dir() / "config.json"


def _read() -> dict:
    for attempt in range(4):
        try:
            return util.read_json_state(_path(), default=dict, max_schema=None)
        except util.StateError as error:
            if not isinstance(error.__cause__, PermissionError) or attempt == 3:
                raise
            time.sleep(.025 * 2 ** attempt)  # Brief Windows sharing/access contention.


def load() -> dict:
    try:
        return _read()
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
    with util.file_lock(p):
        cfg = _read()
        cfg.update(updates)
        util.write_json_atomic(p, cfg)
