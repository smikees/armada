"""Realm lifecycle — archive, export, delete.

A realm is potentially years of an agent team's memory, threads and artefacts, so these three
operations are deliberately very different in how much they destroy:

* **Archive** touches no files at all. It only drops the realm from ARMADA's list, so the folder
  stays exactly where it is and can be added back later. This is the one to reach for.
* **Export** writes a .zip of the whole folder next to it — the thing you want when moving to
  another machine. Read-only with respect to the realm.
* **Delete** removes the folder. On Windows it goes to the Recycle Bin rather than being shredded,
  because that's what "delete" means to someone using the app, and because a mistake here is
  otherwise unrecoverable. If the Recycle Bin isn't available we say so instead of quietly
  escalating to a permanent wipe.

Deletion also refuses to touch the realm ARMADA is currently serving: switch away first. That
avoids the app pulling the floor out from under itself mid-request.
"""
from __future__ import annotations
import datetime as _dt
import os
import shutil
import zipfile
from pathlib import Path
import logging
from .util import swallowed
log = logging.getLogger(__name__)

# Folders never worth carrying to another machine: caches and transient run markers.
_SKIP_DIRS = {"__pycache__", ".git", ".venv", "node_modules"}
# Files that carry credentials rather than realm content (THREAT_MODEL T9). An export is a thing you
# hand to someone or store somewhere; an MCP server's API key or a .env shouldn't ride along by
# accident. They're listed in the result so the owner is told, not surprised.
_SECRET_NAMES = {".mcp.json", ".env", "credentials.json", ".credentials.json", "secrets.json",
                 "telegram.json"}
_SECRET_SUFFIXES = (".env", ".pem", ".key", ".pfx", ".p12")


def _is_secret(name: str) -> bool:
    n = name.lower()
    return n in _SECRET_NAMES or n.endswith(_SECRET_SUFFIXES) or n.startswith(".env.")


def _same(a, b) -> bool:
    try:
        return Path(a).resolve() == Path(b).resolve()
    except Exception:  # noqa
        log.debug('_same: failed; returning a fallback', exc_info=True)
        return False


def export(realm_root, dest_dir=None) -> dict:
    """Zip the realm folder. Returns {ok, path, files, bytes} plus {skipped, skipped_n} if any
    file could not be read — see below for why that is reported rather than swallowed."""
    src = Path(realm_root).resolve()
    if not src.is_dir():
        return {"ok": False, "error": "That realm folder no longer exists."}
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M")
    out = Path(dest_dir).resolve() if dest_dir else src.parent
    try:
        out.mkdir(parents=True, exist_ok=True)
    except Exception as e:  # noqa
        swallowed(log, 'export: failed; error returned to the caller')
        return {"ok": False, "error": f"Can't write to {out}: {e}"}
    zpath = out / f"{src.name}-{stamp}.zip"
    n = 0
    skipped: list[str] = []
    secrets: list[str] = []
    try:
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for root, dirs, files in os.walk(src):
                dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
                for f in files:
                    p = Path(root) / f
                    if p == zpath:              # never zip the archive into itself
                        continue
                    if _is_secret(f):
                        try:
                            secrets.append(p.relative_to(src).as_posix())
                        except ValueError:
                            secrets.append(f)
                        continue
                    try:
                        z.write(p, p.relative_to(src.parent))
                        n += 1
                    except Exception:  # noqa — a locked file shouldn't abort the whole export
                        # …but it must not vanish silently either. This is a backup of years of an
                        # agent team's memory, and a backup that quietly omits files is discovered
                        # at restore time — the one moment nothing can be done about it. A thread
                        # being written by the scheduler is exactly the kind of file that locks.
                        swallowed(log, 'export: failed; falling back')
                        try:
                            skipped.append(p.relative_to(src).as_posix())
                        except ValueError:
                            skipped.append(p.name)
        res = {"ok": True, "path": str(zpath), "files": n, "bytes": zpath.stat().st_size}
        if secrets:
            res["secrets_left_out"] = secrets[:50]
        if skipped:
            res["skipped_n"] = len(skipped)
            res["skipped"] = skipped[:50]       # enough to identify the problem, not a whole tree
        return res
    except Exception as e:  # noqa
        swallowed(log, 'export: failed; error returned to the caller')
        return {"ok": False, "error": str(e)[:200]}


def _recycle(path: Path) -> dict:
    """Send a folder to the Recycle Bin via the Windows shell. Recoverable by design."""
    if os.name != "nt":
        return {"ok": False, "error": "no-recycle-bin"}
    try:
        import ctypes
        from ctypes import wintypes

        class SHFILEOPSTRUCTW(ctypes.Structure):
            _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT),
                        ("pFrom", wintypes.LPCWSTR), ("pTo", wintypes.LPCWSTR),
                        ("fFlags", ctypes.c_uint16), ("fAnyOperationsAborted", wintypes.BOOL),
                        ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]
        FO_DELETE, FOF_ALLOWUNDO, FOF_NOCONFIRMATION, FOF_SILENT = 3, 0x0040, 0x0010, 0x0004
        op = SHFILEOPSTRUCTW()
        op.wFunc = FO_DELETE
        op.pFrom = str(path) + "\0\0"          # double-NUL terminated list
        op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT
        rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
        if rc != 0 or op.fAnyOperationsAborted:
            return {"ok": False, "error": f"shell delete failed (code {rc})"}
        return {"ok": True}
    except Exception as e:  # noqa
        swallowed(log, '_recycle: failed; error returned to the caller')
        return {"ok": False, "error": str(e)[:160]}


def delete(realm_root, current_realm=None, permanent: bool = False) -> dict:
    """Delete a realm's folder. Recycle Bin by default; `permanent` only on explicit instruction."""
    src = Path(realm_root).resolve()
    if not src.is_dir():
        return {"ok": False, "error": "That realm folder no longer exists."}
    if current_realm is not None and _same(src, current_realm):
        return {"ok": False, "error": "That's the realm you're using. Switch to another one first."}
    if not permanent:
        r = _recycle(src)
        if r.get("ok"):
            return {"ok": True, "recycled": True, "path": str(src)}
        if r.get("error") != "no-recycle-bin":
            # Don't silently escalate to an unrecoverable wipe because the safe path failed.
            return {"ok": False, "error": f"Couldn't move it to the Recycle Bin: {r.get('error')}"}
    try:
        shutil.rmtree(src)
        return {"ok": True, "recycled": False, "path": str(src)}
    except Exception as e:  # noqa
        swallowed(log, 'delete: failed; error returned to the caller')
        return {"ok": False, "error": str(e)[:200]}
