"""The realm's on-disk format version, and the one place that upgrades it.

A realm is a folder someone keeps for years and carries between machines — and between versions of
ARMADA. Every field added to `realm.json` this month (sections, toolkit, usage_epoch, the notify
settings, the workspace root…) was added the same way: readers default the missing key, writers add
it the next time they save. That holds up until the first change that ISN'T additive — a renamed
key, a split file, a value whose meaning changes — at which point there is no way to tell a realm
written before the change from one written after, and "default the missing key" silently reads an
old realm as if it were new.

So `realm.json` carries an integer `schema_version`, and `migrate()` walks a realm from whatever
version it is at up to `CURRENT`, one registered step at a time. It runs when a realm is opened
(server start, switching realms, the scheduler's pass) and when one is imported (adopting an
existing folder). The first step, 0 → 1, changes nothing but the stamp: it exists so that every
realm on disk states its version before any migration that actually does something is needed.

Rules a migration step follows:

- It receives the parsed `realm.json` dict and the realm root, and returns the new dict. It may
  touch other files in the realm, but must be idempotent — a step interrupted halfway (a crash, a
  locked file) will run again from the start on the next open.
- It never runs on a realm whose version is NEWER than this build knows (`CURRENT`): a realm opened
  by a newer ARMADA and then by an older one must not be "upgraded" backwards by code that doesn't
  understand it. That case is reported, and the realm is left exactly as it is.
- Nothing here raises to the caller. A realm that can't be migrated still opens — the app falls
  back to the tolerant readers it has always had — and the reason is logged.

Legacy stamp: realms scaffolded before this module existed carry `"schema_version": "0.1"` (a
string, never read by anything). It described the same format as an unstamped realm, so it counts
as version 0 and gets restamped as the integer 1.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Callable

from . import util

log = logging.getLogger("armada.realmformat")

KEY = "schema_version"

# The format this build writes and understands. Bump it together with a new entry in MIGRATIONS.
CURRENT = 2


def _m0_to_1(cfg: dict, realm_root: Path) -> dict:
    """0 → 1: no change to the data. Stamps the version so every realm states one from here on."""
    return cfg


_OLD, _NEW = "matcap", "armada"          # the app's working name → its name (v0.99.56, ADR-010)


def _renamed_run(run):
    """A command job's `run` with `-m matcap` → `-m armada`, or None if it has no such call."""
    import re
    if isinstance(run, list):
        out = list(run)
        for i in range(len(out) - 1):
            if out[i] == "-m" and out[i + 1] == _OLD:
                out[i + 1] = _NEW
        return out if out != run else None
    if isinstance(run, str):
        out = re.sub(r"(-m\s+)" + _OLD + r"\b", r"\g<1>" + _NEW, run)
        return out if out != run else None
    return None


def _m1_to_2(cfg: dict, realm_root: Path) -> dict:
    """1 → 2: the app's internal name changed from `matcap` to `armada` (ADR-010).

    Three things in a realm carried the old name: command jobs that call ARMADA's own CLI
    (`python -m matcap system-refresh …` would now fail with "No module named matcap"), the realm's
    private cache folder `.matcap/` (the model catalogue), and the "App" line of the environment
    block agents are shown. Each is rewritten in place; each step is a no-op the second time.
    """
    old_dir, new_dir = realm_root / ("." + _OLD), realm_root / ("." + _NEW)
    if old_dir.is_dir() and not new_dir.exists():
        old_dir.rename(new_dir)
    for jf in sorted((realm_root / "agents").glob("*/jobs/*.json")):
        try:
            job = json.loads(jf.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        new_run = _renamed_run(job.get("run")) if isinstance(job, dict) else None
        if new_run is not None:
            job["run"] = new_run
            util.write_json_atomic(jf, job)
    env = cfg.get("env")
    if isinstance(env, dict) and isinstance(env.get("App"), str) and _OLD.upper() in env["App"]:
        env["App"] = env["App"].replace(_OLD.upper(), "ARMADA")
    return cfg


# MIGRATIONS[n] upgrades a realm at version n to version n + 1.
MIGRATIONS: dict[int, Callable[[dict, Path], dict]] = {
    0: _m0_to_1,
    1: _m1_to_2,
}


def version_of(cfg) -> int:
    """The version a parsed realm.json is at. Unstamped, the legacy "0.1", or unreadable → 0."""
    if not isinstance(cfg, dict):
        return 0
    v = cfg.get(KEY)
    if v is None or isinstance(v, bool):
        return 0
    if isinstance(v, int):
        return max(v, 0)
    if isinstance(v, str):
        s = v.strip()
        if s.isdigit():
            return int(s)
        # "0.1" and any other non-integer stamp predate this scheme.
        return 0
    return 0


def _stamp(cfg: dict, version: int) -> dict:
    """Return cfg with schema_version set, placed right after `name` (or first) so it's visible."""
    out: dict = {}
    placed = False
    if "name" not in cfg:
        out[KEY] = version
        placed = True
    for k, val in cfg.items():
        if k == KEY:
            continue
        out[k] = val
        if k == "name" and not placed:
            out[KEY] = version
            placed = True
    return out


def plan(cfg) -> dict:
    """What migrate() would do to this config, without doing it: {from, to, steps, newer}."""
    v = version_of(cfg)
    if v > CURRENT:
        return {"from": v, "to": v, "steps": [], "newer": True}
    return {"from": v, "to": CURRENT, "steps": list(range(v, CURRENT)), "newer": False}


def migrate(realm_root) -> dict:
    """Bring `realm_root`'s realm.json up to CURRENT. Never raises.

    Returns {ok, from, to, changed} and, when relevant, `newer` (the realm was written by a newer
    ARMADA and was left alone), `skipped` (no realm.json — e.g. the legacy cabinet layout, which has
    no realm.json to stamp), or `error`.
    """
    root = Path(realm_root)
    p = root / "realm.json"
    if not p.is_file():
        return {"ok": True, "from": None, "to": None, "changed": False, "skipped": "no realm.json"}
    try:
        # Same lock every other realm.json read-modify-write takes, so a migration can't interleave
        # with a settings save from the web UI or the scheduler's own writes.
        with util.file_lock(p):
            raw = p.read_text(encoding="utf-8-sig")
            cfg = json.loads(raw) if raw.strip() else {}
            if not isinstance(cfg, dict):
                return {"ok": False, "from": None, "to": None, "changed": False,
                        "error": "realm.json is not a JSON object"}
            pl = plan(cfg)
            if pl["newer"]:
                log.warning("realm %s is format v%s, newer than this ARMADA understands (v%s); "
                            "leaving it untouched", root, pl["from"], CURRENT)
                return {"ok": True, "from": pl["from"], "to": pl["from"], "changed": False, "newer": True}
            # Already current AND stamped as a real integer (a "1" string gets rewritten as 1).
            if not pl["steps"] and type(cfg.get(KEY)) is int:
                return {"ok": True, "from": pl["from"], "to": CURRENT, "changed": False}
            for n in pl["steps"]:
                step = MIGRATIONS.get(n)
                if step is None:  # a gap in the registry is a programming error, not a data one
                    raise RuntimeError(f"no migration registered for v{n} → v{n + 1}")
                cfg = step(cfg, root)
                if not isinstance(cfg, dict):
                    raise RuntimeError(f"migration v{n} → v{n + 1} returned {type(cfg).__name__}, not a dict")
            cfg = _stamp(cfg, CURRENT)
            util.write_json_atomic(p, cfg)
        if pl["from"] != CURRENT:
            log.info("realm %s migrated from format v%s to v%s", root, pl["from"], CURRENT)
        return {"ok": True, "from": pl["from"], "to": CURRENT, "changed": True}
    except Exception as e:
        log.exception("realm %s: format migration failed; opening it as-is", root)
        return {"ok": False, "from": None, "to": None, "changed": False, "error": str(e)[:200]}


# Opening a realm happens often (every scheduler pass, every switch); after the first successful
# migration the answer only changes if realm.json does. Keyed on the file's mtime so a realm.json
# restored from an old backup mid-session is looked at again.
_checked: dict[str, int] = {}


def ensure(realm_root) -> dict | None:
    """migrate() once per realm per change to its realm.json. Cheap on the hot path: one stat()."""
    p = Path(realm_root) / "realm.json"
    try:
        key = str(p.resolve())
        mt = os.stat(p).st_mtime_ns
    except OSError:
        return None
    if _checked.get(key) == mt:
        return None
    res = migrate(realm_root)
    # Remembered on failure too: retrying an unchanged file every scheduler pass would only log the
    # same traceback once a minute. Editing realm.json (or restarting) is what earns another try.
    try:
        _checked[key] = os.stat(p).st_mtime_ns
    except OSError:
        pass
    return res
