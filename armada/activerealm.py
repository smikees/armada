"""Which realm the app opens when nobody says — the last one you were actually in.

Switching realms used to live entirely in the running process: `/switch` moved `Handler.realm`
and that was the end of it. Update & Restart carried the change forward (it re-execs with the
live realm), but a cold start did not — the launcher passed a path chosen when it was written,
so closing the app and reopening it silently put you back in a realm you had left, possibly days
ago, with a full week of someone else's jobs on the dashboard. A switch that survives a restart
but not a relaunch is worse than no memory at all, because the two behave differently and nothing
on screen says which one you just did.

So the active realm is remembered on the machine, beside the app root and the visual theme: it is
a property of this install, not of any realm, and not of the folder the launcher happens to point
at. An explicit path still wins — someone typing `armada app <folder>` means that folder, and it
becomes the remembered one — but with no path given, the app reopens where you left it.
"""
from __future__ import annotations

from pathlib import Path

from . import appconfig
import logging
from . import util
from .util import swallowed
log = logging.getLogger(__name__)

KEY = "last_realm"


def is_realm(path) -> bool:
    """Does this folder look like a realm ARMADA can open?

    Both shapes count: `realm.json` is the native one, `cabinet/schedule.json` the older layout
    that predates it and is still readable. Deliberately a cheap existence check rather than a
    full validation — this decides whether to *offer* a folder, and `armada validate` is what says
    whether it will actually run.
    """
    try:
        p = Path(str(path))
        return (p / "realm.json").exists() or (p / "cabinet" / "schedule.json").exists()
    except OSError:
        return False


def remembered() -> str:
    """The last realm the app was in, or '' when there isn't one that still exists.

    A remembered folder that has been moved, renamed or deleted reads as no memory at all rather
    than as an error: the app should fall back and open, not refuse to start because of a
    preference.
    """
    p = str(appconfig.get(KEY, "") or "").strip()
    return p if p and is_realm(p) else ""


def remember(path) -> None:
    """Record `path` as the realm the app is in. Best-effort; never raises at the caller."""
    try:
        p = str(Path(str(path)).resolve())
    except OSError:
        return
    if not is_realm(p) or p == str(appconfig.get(KEY, "") or ""):
        return
    try:
        appconfig.save({KEY: p})
    except Exception:  # noqa — remembering is a convenience, not a precondition for serving
        swallowed(log, 'remember: failed; ignored')


def resolve(explicit: str = "") -> str:
    """The realm to open: what was asked for, else where we were, else the one we know about.

    Returns '' when there is nothing to open — the caller turns that into a sentence, because what
    to say differs between "you have never set ARMADA up" and "the folder you named is gone".
    """
    if explicit:
        return str(explicit)
    last = remembered()
    if last:
        return last
    # Nothing remembered (a fresh install, or the folder moved). If exactly one realm is
    # registered, opening it is unambiguous; with several there is no basis for a guess, so say so
    # rather than picking one and having the app come up somewhere arbitrary.
    reg = _registered()
    return reg[0] if len(reg) == 1 else ""


def every() -> list[str]:
    """Every realm ARMADA knows about, the active one first.

    What the scheduler fires. A realm's jobs are its own commitment and don't pause because you
    are looking at somewhere else, so "which realm is active" decides only the ORDER here — the
    active one goes first, because the one process that can't be duplicated (the Telegram
    listener) attaches to the head of the list, and a reply typed on a phone should land in the
    realm you are actually working in.
    """
    out = _registered()
    last = remembered()
    if last:
        out = [last] + [p for p in out if Path(p).resolve() != Path(last).resolve()]
    return out


def _registered() -> list[str]:
    """Paths from ~/.armada/realms.json that still exist as realms."""
    import json
    p = util.data_dir() / "realms.json"
    try:
        items = json.loads(p.read_text(encoding="utf-8-sig")) if p.exists() else []
    except Exception:  # noqa — a corrupt registry is not a reason to fail to start
        swallowed(log, '_registered: failed; returning a fallback')
        return []
    out = []
    for i in items:
        q = str((i or {}).get("path", "") or "").strip()
        if q and is_realm(q) and q not in out:
            out.append(q)
    return out


def no_realm_message() -> str:
    """What to tell someone when there is nothing to open."""
    reg = _registered()
    if reg:
        return ("ARMADA doesn't know which realm to open — several are registered and none is "
                "the last one you used. Name one: armada app \"<folder>\"\n  " + "\n  ".join(reg))
    return ("ARMADA has no realm to open yet. Name a realm folder: armada app \"<folder>\", "
            "or create one with: armada new \"<folder>\"")
