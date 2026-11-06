"""Verified portable realm copies. A live copy is never a point-in-time snapshot.

See docs/dev/REALM_EXPORTS.md for exclusions, resource limits and recovery semantics.
The manifest detects damage, not a malicious author who can replace it and its hashes.
"""
from __future__ import annotations

import datetime as dt
from contextlib import contextmanager
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import tempfile
import uuid
import zipfile

from . import __version__, util

MANIFEST = ".armada-export.json"
MAX_ENTRIES = 20000
MAX_MANIFEST = 8 * 1024 * 1024
MAX_FILE = 4 * 1024**3
MAX_TOTAL = 20 * 1024**3
CHUNK = 1024 * 1024
CONSISTENCY = "live-copy-not-a-snapshot"
log = logging.getLogger(__name__)
SKIP_DIRS = {"__pycache__", ".git", ".venv", "node_modules", ".running"}
SECRET_NAMES = {".mcp.json", ".env", "credentials.json", ".credentials.json", "secrets.json", "telegram.json"}
SECRET_SUFFIXES = (".env", ".pem", ".key", ".pfx", ".p12")


def is_secret(name):
    n = name.lower()
    return n in SECRET_NAMES or n.endswith(SECRET_SUFFIXES) or n.startswith(".env.")


def _parts(name):
    if not isinstance(name, str) or len(name) > 1024 or "\\" in name:
        raise ValueError("Unsafe archive path.")
    parts = name.split("/")
    for p in parts:
        if (p in ("", ".", "..") or p.rstrip(" .") != p
                or re.search(r'[<>:"|?*\x00-\x1f\x7f]', p)
                or re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?", p)):
            raise ValueError("Unsafe archive path: traversal or Windows filename alias.")
    return parts


def _linked(st):
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, "st_file_attributes", 0) & 0x400)


def _plain_path(path):
    """Reject linked ancestors as well as the final component, before resolving."""
    path = Path(os.path.abspath(path))
    for p in reversed((path, *path.parents)):
        if _linked(p.lstat()):
            raise ValueError("Linked files, folders and reparse points are excluded.")
    return path


def _signature(st):
    # Windows path-stat and descriptor-stat disagree on legacy st_ctime semantics.
    # Identity, length and modification time are comparable on both APIs.
    return st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns


def _inventory(src):
    files, directories, omitted = {}, [], []
    count = 0

    def walk(folder):
        nonlocal count
        try:
            _plain_path(folder)
            with os.scandir(folder) as it:
                entries = []
                for entry in it:
                    count += 1
                    if count > MAX_ENTRIES:
                        raise ExportWriteError("Realm exceeds the export entry limit (20,000).")
                    entries.append(entry)
                entries.sort(key=lambda e: e.name)
        except (OSError, ValueError):
            omitted.append({"path": folder.relative_to(src).as_posix(), "reason": "unreadable-directory"})
            return
        for entry in entries:
            path = Path(entry.path)
            rel = path.relative_to(src).as_posix()
            if rel.casefold() == MANIFEST.casefold():
                raise ValueError(f"The realm already contains reserved export metadata: {MANIFEST}")
            try:
                _parts(rel)
                # Windows DirEntry.stat omits file IDs; use lstat so the captured
                # descriptor can be compared with the same file identity.
                st = path.lstat()
                if _linked(st):
                    reason = "linked-path"
                elif stat.S_ISDIR(st.st_mode):
                    if entry.name.lower() in SKIP_DIRS:
                        reason = "cache-or-runtime"
                    else:
                        directories.append(rel)
                        walk(path)
                        continue
                elif is_secret(entry.name):
                    reason = "credential-name"
                elif (entry.name.startswith(".tmp-")
                      or (entry.name.startswith(".") and entry.name.endswith(".lock"))
                      or rel == "scheduler.lock.json"):
                    reason = "cache-or-runtime"
                elif not stat.S_ISREG(st.st_mode):
                    reason = "special-file"
                else:
                    files[rel] = _signature(st)
                    continue
            except (OSError, ValueError):
                reason = "unreadable-or-unsafe-path"
            omitted.append({"path": rel, "reason": reason})
    walk(src)
    return files, directories, omitted


def _capture(src, rel, signature, spool):
    """Read bounded chunks; source read failures alone are recoverable omissions."""
    path = _plain_path(src / rel)
    digest, size = hashlib.sha256(), 0
    if signature[2] > MAX_FILE:
        raise ValueError("File exceeds the export size limit.")
    with path.open("rb") as stream:
        if _signature(os.fstat(stream.fileno())) != signature:
            raise ValueError("File changed before copying.")
        while True:
            chunk = stream.read(CHUNK)
            if not chunk:
                break
            size += len(chunk)
            if size > signature[2]:
                raise ValueError("File grew while copying.")
            # A spool/destination write error is fatal, not an unreadable source.
            try:
                spool.write(chunk)
            except OSError as exc:
                raise ExportWriteError("Not enough space or permission to stage the export.") from exc
            digest.update(chunk)
        if (_signature(os.fstat(stream.fileno())) != signature
                or _signature(_plain_path(path).stat()) != signature or size != signature[2]):
            raise ValueError("File changed while copying.")
    spool.seek(0)
    return {"path": rel, "size": size, "sha256": digest.hexdigest()}


class ExportWriteError(RuntimeError):
    """Writing the backup failed; never downgrade to a partial success."""


def export(realm_root, dest_dir=None):
    staged = None
    try:
        src = _plain_path(realm_root)
        if not src.is_dir():
            raise ValueError("That realm folder no longer exists.")
        _parts(src.name)
        out = Path(dest_dir).absolute() if dest_dir else src.parent
        if out.resolve().is_relative_to(src):
            raise ValueError("Choose an export folder outside the realm so backups cannot include themselves.")
        out.mkdir(parents=True, exist_ok=True)
        out = _plain_path(out)
        if out.is_relative_to(src):
            raise ValueError("Choose an export folder outside the realm so backups cannot include themselves.")
        started = dt.datetime.now(dt.timezone.utc).isoformat()
        files, directories, omitted = _inventory(src)
        export_id = uuid.uuid4().hex
        destination = out / f"{src.name}-{dt.datetime.now():%Y%m%d-%H%M%S}-{export_id}.zip"
        fd, name = tempfile.mkstemp(dir=out, prefix=".armada-export-", suffix=".partial")
        staged = Path(name)
        records, total = [], 0
        with os.fdopen(fd, "w+b") as output:
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
                for rel, signature in files.items():
                    with tempfile.TemporaryFile(dir=out) as spool:
                        try:
                            record = _capture(src, rel, signature, spool)
                        except (OSError, ValueError):
                            omitted.append({"path": rel, "reason": "unreadable-or-changed-file"})
                            continue
                        total += record["size"]
                        if total > MAX_TOTAL:
                            raise ValueError("Realm exceeds the export size limit (20 GiB).")
                        with archive.open(src.name + "/" + rel, "w", force_zip64=True) as target:
                            shutil.copyfileobj(spool, target, CHUNK)
                        records.append(record)
                after, after_dirs, after_omitted = _inventory(src)
                changes = sorted(k for k in files.keys() | after.keys() if files.get(k) != after.get(k))
                changes += sorted(set(directories) ^ set(after_dirs))
                # Omissions may change too. Retain both inventories in linear time.
                seen_omissions = {(o["path"], o["reason"]) for o in omitted}
                omitted.extend(o for o in after_omitted if (o["path"], o["reason"]) not in seen_omissions)
                incomplete = bool(changes or any(o["reason"] not in ("credential-name", "cache-or-runtime") for o in omitted))
                manifest = {"format": 1, "armada_version": __version__, "root": src.name,
                            "id": export_id, "started": started, "finished": dt.datetime.now(dt.timezone.utc).isoformat(),
                            "consistency": CONSISTENCY, "complete": not incomplete,
                            "files": records, "directories": directories, "omitted": omitted, "changed": changes}
                raw = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
                if len(raw) > MAX_MANIFEST:
                    raise ValueError("Export manifest exceeds the size limit.")
                archive.writestr(src.name + "/" + MANIFEST, raw)
            output.flush()
            os.fsync(output.fileno())
        checked = verify(staged)
        if not checked["ok"]:
            raise ValueError("Export verification failed: " + checked["error"])
        size = staged.stat().st_size
        util.publish_new_file(staged, destination)
        result = {"ok": True, "path": str(destination), "files": len(records), "bytes": size,
                  "verified": True, "complete": not incomplete, "consistency": CONSISTENCY,
                  "changed_n": len(changes), "changed": changes[:50]}
        skipped = [o["path"] for o in omitted if o["reason"] not in ("credential-name", "cache-or-runtime")]
        secrets = [o["path"] for o in omitted if o["reason"] == "credential-name"]
        if skipped:
            result.update(skipped_n=len(skipped), skipped=skipped[:50])
        if secrets:
            result.update(secrets_left_out=secrets[:50], secrets_left_out_n=len(secrets))
        return result
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as exc:
        return {"ok": False, "error": str(exc)[:300]}
    finally:
        if staged is not None:
            try:
                staged.unlink(missing_ok=True)
            except OSError:
                log.warning("Export staging cleanup failed: %s", staged, exc_info=True)


def _json(raw):
    from .records import decode
    return decode(raw)


@contextmanager
def _open_archive(path):
    """Bound the central directory *before* ZipFile allocates its entry objects.

    Accept ordinary single-volume ZIP and ZIP64. Exported archives have no executable
    prefix; unsupported layouts are refused rather than guessed at during recovery.
    """
    with open(path, "rb") as stream:
        stream.seek(0, 2)
        length = stream.tell()
        if length > MAX_TOTAL * 1.01 + MAX_MANIFEST:
            raise ValueError("Archive exceeds the compressed size limit.")
        tail_start = max(0, length - 65557)
        stream.seek(tail_start)
        tail = stream.read(65557)
        index = tail.rfind(b"PK\x05\x06")
        if index < 0 or len(tail) - index < 22:
            raise ValueError("Archive is incomplete: missing ZIP end record.")
        _, disk, cd_disk, on_disk, count, size, offset, comment = struct.unpack_from("<4s4H2LH", tail, index)
        boundary = tail_start + index
        if disk or cd_disk or count != on_disk or index + 22 + comment != len(tail):
            raise ValueError("Unsupported multi-volume or malformed ZIP layout.")
        locator = b""
        if boundary >= 20:
            stream.seek(boundary - 20)
            locator, disk, position, volumes = struct.unpack("<4sLQL", stream.read(20))
        if locator == b"PK\x06\x07":
            if disk or volumes != 1 or position > boundary - 76:
                raise ValueError("Unsupported ZIP64 layout.")
            stream.seek(position)
            raw = stream.read(56)
            if len(raw) != 56:
                raise ValueError("Incomplete ZIP64 end record.")
            magic, record_size, _, _, disk, cd_disk, on_disk, count, size, offset = struct.unpack("<4sQ2H2L4Q", raw)
            if (magic != b"PK\x06\x06" or disk or cd_disk or on_disk != count
                    or record_size < 44 or position + record_size + 12 != boundary - 20):
                raise ValueError("Invalid ZIP64 end record.")
            boundary = position
        elif count == 0xffff or size == 0xffffffff or offset == 0xffffffff:
            raise ValueError("Missing ZIP64 locator.")
        if count > MAX_ENTRIES + 1 or size > 16 * 1024**2 or offset + size != boundary:
            raise ValueError("Archive directory exceeds limits or has an unsupported layout.")
        stream.seek(0)
        with zipfile.ZipFile(stream) as archive:
            yield archive


def _verified(archive, extract_to=None):
    entries = archive.infolist()
    if len(entries) > MAX_ENTRIES + 1:
        raise ValueError("Archive has too many entries.")
    names, aliases, total = {}, set(), 0
    for info in entries:
        _parts(info.filename)
        alias = info.filename.casefold()
        mode = info.external_attr >> 16
        if (alias in aliases or info.filename != info.orig_filename or info.is_dir() or info.flag_bits & 1
                or stat.S_IFMT(mode) not in (0, stat.S_IFREG)
                or info.file_size > MAX_FILE):
            raise ValueError("Archive contains duplicate, linked, encrypted or unsupported entries.")
        aliases.add(alias)
        names[info.filename] = info
        total += info.file_size
    if total > MAX_TOTAL + MAX_MANIFEST:
        raise ValueError("Archive exceeds the extraction size limit.")
    manifests = [n for n in names if n.endswith("/" + MANIFEST) and n.count("/") == 1]
    if len(manifests) != 1 or names[manifests[0]].file_size > MAX_MANIFEST:
        raise ValueError("A supported export manifest is required; legacy ZIPs cannot be verified.")
    manifest_name = manifests[0]
    manifest = _json(archive.read(manifest_name))
    if not isinstance(manifest, dict) or type(manifest.get("format")) is not int or manifest["format"] != 1:
        raise ValueError("Unsupported export manifest format.")
    root = manifest.get("root")
    if not isinstance(root, str) or len(_parts(root)) != 1 or manifest_name != root + "/" + MANIFEST:
        raise ValueError("Invalid manifest realm folder.")
    if manifest.get("consistency") != CONSISTENCY or type(manifest.get("complete")) is not bool:
        raise ValueError("Invalid export consistency metadata.")
    for key in ("files", "directories", "omitted", "changed"):
        if not isinstance(manifest.get(key), list) or len(manifest[key]) > MAX_ENTRIES * 2:
            raise ValueError("Invalid manifest lists.")
    expected, paths = {manifest_name}, {}
    def add_path(path, kind):
        parts = _parts(path)
        for index in range(1, len(parts)):
            parent = "/".join(parts[:index])
            prior = paths.setdefault(parent.casefold(), (parent, "directory"))
            if prior != (parent, "directory"):
                raise ValueError("Archive path aliases or file/directory collision.")
        previous = paths.get(path.casefold())
        if previous and (previous != (path, kind) or kind == "file"):
            raise ValueError("Archive path aliases or duplicates.")
        paths[path.casefold()] = (path, kind)
    for directory in manifest["directories"]:
        add_path(directory, "directory")
    for item in manifest["omitted"]:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or item.get("reason") not in (
                "credential-name", "cache-or-runtime", "linked-path", "special-file", "unreadable-directory",
                "unreadable-or-unsafe-path", "unreadable-or-changed-file"):
            raise ValueError("Invalid omission metadata.")
    if any(not isinstance(p, str) for p in manifest["changed"]):
        raise ValueError("Invalid change metadata.")
    incomplete = bool(manifest["changed"] or any(o["reason"] not in ("credential-name", "cache-or-runtime") for o in manifest["omitted"]))
    if manifest["complete"] == incomplete:
        raise ValueError("Manifest completeness contradicts its omissions or changes.")
    for row in manifest["files"]:
        if (not isinstance(row, dict) or type(row.get("size")) is not int or row["size"] < 0
                or not isinstance(row.get("sha256"), str) or not re.fullmatch("[0-9a-f]{64}", row["sha256"])):
            raise ValueError("Invalid manifest file record.")
        rel = row.get("path")
        add_path(rel, "file")
        name = root + "/" + rel
        if name == manifest_name or name not in names or names[name].file_size != row["size"]:
            raise ValueError("Archive members do not match the manifest.")
        expected.add(name)
    if expected != set(names):
        raise ValueError("Archive contains unlisted files.")
    if extract_to:
        for directory in manifest["directories"]:
            (extract_to / directory).mkdir(parents=True, exist_ok=True)
    for row in manifest["files"]:
        digest, size = hashlib.sha256(), 0
        output = None
        try:
            if extract_to:
                target = extract_to / row["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                output = target.open("xb")
            with archive.open(root + "/" + row["path"]) as stream:
                while chunk := stream.read(CHUNK):
                    size += len(chunk)
                    if size > row["size"]:
                        raise ValueError("Archive expands beyond its declared size.")
                    digest.update(chunk)
                    if output:
                        output.write(chunk)
            if size != row["size"] or digest.hexdigest() != row["sha256"]:
                raise ValueError("File checksum mismatch: " + row["path"])
            if output:
                output.flush()
                os.fsync(output.fileno())
        finally:
            if output:
                output.close()
    return manifest


def verify(archive_path):
    """Check every byte against the manifest; this is integrity, not author authentication."""
    try:
        with _open_archive(archive_path) as archive:
            manifest = _verified(archive)
        return {"ok": True, "verified": True, "complete": manifest["complete"],
                "files": len(manifest["files"]), "manifest": manifest}
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as exc:
        return {"ok": False, "error": str(exc)[:300]}


def _hold_restored(root):
    """Pause definitions without resetting any execution claims/history or access policy."""
    def update(path, change, optional=False):
        if optional and not path.exists():
            return
        data = _json(path.read_bytes())
        if not isinstance(data, dict):
            raise ValueError("Restore cannot safely pause damaged settings: " + path.name)
        change(data)
        util.write_json_atomic(path, data)
    update(root / "realm.json", lambda d: d.update(archived=True))
    for path in root.glob("agents/*/jobs/*.json"):
        update(path, lambda d: d.update(enabled=False))
    def disable_system(data):
        from . import sysjobs
        for job in sysjobs.JOBS:
            data.setdefault(job["id"], {})
        for entry in data.values():
            if not isinstance(entry, dict):
                raise ValueError("Restore cannot safely pause damaged system jobs.")
            entry["enabled"] = False
    if not (root / "system_jobs.json").exists():
        util.write_json_atomic(root / "system_jobs.json", {})
    update(root / "system_jobs.json", disable_system)
    def disable_legacy(data):
        for key in ("jobs", "tasks"):
            jobs = data.get(key, [])
            if not isinstance(jobs, list):
                raise ValueError("Restore cannot safely pause damaged legacy jobs.")
            for job in jobs:
                if not isinstance(job, dict):
                    raise ValueError("Restore cannot safely pause damaged legacy jobs.")
                job["enabled"] = False
    update(root / "cabinet" / "schedule.json", disable_legacy, optional=True)


def restore_copy(archive_path, destination, *, allow_incomplete=False):
    """Windows recovery to a new directory; never register, launch, or merge a realm."""
    staged = None
    try:
        if os.name != "nt":
            raise ValueError("Atomic realm recovery is currently supported on Windows only.")
        target = Path(os.path.abspath(destination))
        _parts(target.name)
        parent = _plain_path(target.parent)
        if os.path.lexists(target):
            raise ValueError("Recovery needs a new folder; the destination already exists.")
        # The archive stays open across validation and extraction. Hashes are checked
        # again while copying, so replacement/mutation cannot introduce unchecked bytes.
        with _open_archive(archive_path) as archive:
            manifest = _verified(archive)
            if not manifest["complete"] and not allow_incomplete:
                raise ValueError("This export is incomplete. Review its manifest; use --allow-incomplete only to recover available files.")
            staged = Path(tempfile.mkdtemp(dir=parent, prefix=".armada-restore-"))
            _verified(archive, staged)
        _hold_restored(staged)
        # Keep evidence outside the restored realm (in the original ZIP). Adding the
        # reserved manifest to the realm would prevent its next export.
        _plain_path(parent)
        os.rename(staged, target)  # Windows refuses *any* existing destination.
        staged = None
        return {"ok": True, "path": str(target), "complete": manifest["complete"], "paused": True,
                "message": "Recovered to a new, paused folder. Review it before adding it to ARMADA and enabling jobs."}
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as exc:
        return {"ok": False, "error": str(exc)[:300]}
    finally:
        if staged is not None:
            shutil.rmtree(staged)
