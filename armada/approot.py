"""The app root — the one folder on this machine that ARMADA is allowed to work in.

Set once, when ARMADA is first set up. Every realm lives inside it, and nothing an agent does is
supposed to reach outside it. One folder to point at, one folder to back up, one folder to reason
about when asking "what can this thing actually touch".

Why a machine-level setting rather than a per-realm one: containment you can turn off per realm is
not containment. The root is the boundary for the install; a realm chooses where *inside* it to
live, not whether to be inside it.

This module owns two things: what the root is, and whether a given path is inside it. It does not
enforce anything at run time — see `armada.permissions` for what the engine is actually told, and
be careful to keep the difference clear in your head. A path check here is ARMADA refusing to set
something up; it is not a guarantee about what a running agent can reach.
"""
from __future__ import annotations

from pathlib import Path

from . import appconfig

KEY = "app_root"


def root() -> str:
    """The configured app root, or '' when ARMADA hasn't been set up yet."""
    return str(appconfig.get(KEY, "") or "").strip()


def configured() -> bool:
    return bool(root())


def exists() -> bool:
    r = root()
    try:
        return bool(r) and Path(r).is_dir()
    except OSError:
        return False


def set_root(path: str) -> dict:
    """Point ARMADA at its root folder. Refuses a path that isn't a folder on this machine."""
    p = str(path or "").strip().rstrip("\\/")
    if not p:
        appconfig.save({KEY: ""})
        return {"ok": True, "root": "", "cleared": True}
    try:
        rp = Path(p)
        if not rp.is_dir():
            return {"ok": False, "error": f"{p} isn't a folder on this machine."}
        p = str(rp.resolve())
    except OSError as e:
        return {"ok": False, "error": f"Can't read {p}: {e}"}
    appconfig.save({KEY: p})
    return {"ok": True, "root": p}


def contains(path) -> bool:
    """Is `path` inside the app root? False when no root is set — nothing is 'inside' nothing.

    Resolves both sides first, so `..` segments, a symlink, or a short 8.3 Windows name can't walk
    out of the root while still looking like a child of it.
    """
    r = root()
    if not r:
        return False
    try:
        rp = Path(r).resolve()
        tp = Path(str(path)).resolve()
    except OSError:
        return False
    return tp == rp or rp in tp.parents


def check(path) -> dict:
    """Would ARMADA accept a realm at `path`? Returns {ok, error} with a sentence a person can act on."""
    if not configured():
        return {"ok": False, "code": "no-root",
                "error": "ARMADA has no root folder yet. Set one in Settings, then add the realm."}
    if not exists():
        return {"ok": False, "code": "root-missing",
                "error": f"The app root {root()} doesn't exist on this machine."}
    if not contains(path):
        return {"ok": False, "code": "outside-root",
                "error": (f"A realm has to live inside ARMADA's root folder, {root()}. "
                          f"{path} is outside it — move or copy it in, then add it from there.")}
    return {"ok": True}


def suggest_for(path) -> str:
    """If someone points at a folder outside the root, what would we move it to?"""
    r = root()
    if not r:
        return ""
    return str(Path(r) / Path(str(path)).name)
