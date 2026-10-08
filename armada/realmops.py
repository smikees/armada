"""Realm lifecycle — archive, export, delete.

A realm is potentially years of an agent team's memory, threads and artefacts, so these three
operations are deliberately very different in how much they destroy:

* **Archive** switches off every job and persistently holds dispatch before the realm leaves the
  list. Its resources and history stay in place and it can be added back later.
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
import hashlib
import tempfile
import logging
from .util import swallowed
log = logging.getLogger(__name__)


def lifecycle_lock(realm_root):
    """Serialize lifecycle changes with run admission, including the separate scheduler.

    The lock is outside the realm so Windows can recycle its whole folder while locked.
    """
    from . import util
    key = hashlib.sha256(os.path.normcase(str(Path(realm_root).resolve())).encode()).hexdigest()
    return util.file_lock(Path(tempfile.gettempdir()) / "armada-realm-lifecycle" / key,
                          timeout=2, validate_state=False)


def archived(realm_root) -> bool:
    from . import util
    return bool(util.read_json_state(Path(realm_root) / "realm.json", default=dict).get("archived"))


def assert_active(realm_root):
    from . import util
    if not (Path(realm_root) / "realm.json").is_file():
        raise util.StateError("This realm no longer exists.")
    if archived(realm_root):
        raise util.StateError("This realm is archived. Add it back before running tasks.")


def busy(realm_root) -> bool:
    """Activity owned by another Armada process also prevents archive/deletion."""
    from . import util
    root = Path(realm_root)
    records = [util.read_json_state(p, default=dict)
               for p in root.glob("agents/*/runs/.running/*.json")]
    state = util.read_json_state(root / "system_jobs.json", default=dict)
    if any(not rec.get("owner_pid") or util.pid_alive(rec["owner_pid"]) for rec in records):
        return True
    for jid, entry in state.items():
        attempt = entry.get("attempt", {}) if isinstance(entry, dict) else {}
        if attempt.get("state") != "claimed":
            continue
        if attempt.get("owner_pid"):
            if util.pid_alive(attempt["owner_pid"]):
                return True
        else:
            # Legacy claims have no PID and survive crashes. Their OS execution lock,
            # rather than an old claim alone, establishes whether work is still live.
            try:
                with util.file_lock(root / ".scheduler" / "system" / f"{jid}.json",
                                    timeout=0, validate_state=False):
                    pass
            except util.FileLockTimeout:
                return True
    return False


def archive(realm_root) -> dict:
    """Disable definitions and all system jobs; never change another realm's machine settings."""
    from . import util, sysjobs
    root = Path(realm_root).resolve()
    try:
        with lifecycle_lock(root):
            if not (root / "realm.json").is_file():
                return {"ok": False, "error": "That realm folder no longer exists."}
            if busy(root):
                return {"ok": False, "error": "Wait for this realm's current tasks to finish before archiving it."}
            # Persist the dispatch guard first. A partial write failure remains safely held.
            util.mutate_json(root / "realm.json", lambda cfg: cfg.update(archived=True))
            for path in root.glob("agents/*/jobs/*.json"):
                util.mutate_json(path, lambda job: job.update(enabled=False))
            legacy = root / "cabinet" / "schedule.json"
            if legacy.is_file():
                def disable_legacy(cfg):
                    for key in ("jobs", "tasks"):
                        for job in cfg.get(key, []):
                            job["enabled"] = False
                util.mutate_json(legacy, disable_legacy)
            def disable_system(st):
                for job in sysjobs.JOBS:
                    st.setdefault(job["id"], {})["enabled"] = False
            util.mutate_json(root / "system_jobs.json", disable_system,
                             default=dict, validate=sysjobs._validate_state)
        return {"ok": True}
    except (OSError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}


def restore(realm_root):
    """Explicit re-adoption releases the archive guard; job switches stay off."""
    from . import util
    with lifecycle_lock(realm_root):
        util.mutate_json(Path(realm_root) / "realm.json", lambda cfg: cfg.pop("archived", None))

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
    try:
        with lifecycle_lock(realm_root):
            from . import scheduler_state
            # Do not wait for or interrupt real work; only release an idle daemon lease.
            if busy(realm_root):
                return {"ok": False, "error": "Wait for this realm's current tasks to finish before deleting it."}
            with scheduler_state.pause_for_lifecycle(realm_root):
                return _delete_locked(realm_root, current_realm, permanent)
    except (OSError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}


def _delete_locked(realm_root, current_realm, permanent):
    src = Path(realm_root).resolve()
    if not src.is_dir():
        return {"ok": False, "error": "That realm folder no longer exists."}
    if current_realm is not None and _same(src, current_realm):
        return {"ok": False, "error": "That's the realm you're using. Switch to another one first."}
    if src == Path(src.anchor) or not (src / "realm.json").is_file():
        return {"ok": False, "error": "Refusing to delete a folder without a realm.json."}
    if busy(src):
        return {"ok": False, "error": "Wait for this realm's current tasks to finish before deleting it."}
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
