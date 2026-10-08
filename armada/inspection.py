"""Owner-approved inspector authority and registered, read-only artifact access."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import appconfig, util


def identity(root, agent):
    return str(Path(root).resolve()).casefold() + "|" + util.safe_seg(agent, "agent")


def _set(key, entry, value):
    p = appconfig._path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with util.file_lock(p):
        cfg = appconfig._read()
        entries = cfg.setdefault(key, {})
        if value is None:
            entries.pop(entry, None)
        else:
            entries[entry] = value
        util.write_json_atomic(p, cfg)


def approve(root, agent, enabled):
    if type(enabled) is not bool:
        raise ValueError("Is inspector must be true or false.")
    _set("inspectors", identity(root, agent), True if enabled else None)


def enabled(root, agent):
    p = Path(root) / "agents" / util.safe_seg(agent, "agent") / "agent.json"
    return (util.read_json_state(p).get("is_inspector") is True
            and appconfig.get("inspectors", {}).get(identity(root, agent)) is True)


def command_fingerprint(job):
    fields = {k: job.get(k) for k in ("id", "kind", "run", "command", "cwd", "env", "dry_run_command")}
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


def approve_command(root, agent, job):
    entry = identity(root, agent) + "|" + util.safe_seg(job["id"], "job")
    _set("dry_run_commands", entry, command_fingerprint(job) if job.get("dry_run_command") else None)


def command_approved(root, agent, job):
    entry = identity(root, agent) + "|" + util.safe_seg(job["id"], "job")
    return appconfig.get("dry_run_commands", {}).get(entry) == command_fingerprint(job)


def artifacts(root):
    """Only recorded output artifacts inside their producer's authorized file roots."""
    from . import job_access, job_history, workspace
    from .threads import Thread
    root = Path(root).resolve()
    roots = [root, Path(workspace.root(root)).resolve()] if workspace.root(root) else [root]
    found = {}
    for ad in sorted((root / "agents").iterdir()):
        if not ad.is_dir() or ad.is_symlink() or getattr(ad, "is_junction", lambda: False)():
            continue
        allowed = list(roots)
        for jp in (ad / "jobs").glob("*.json"):
            try:
                allowed.extend(job_access.grant_for(root, ad.name, util.read_json_state(jp)).roots)
            except (OSError, ValueError):
                continue
        candidates = []
        for thread in Thread.list_threads(ad):
            for message in Thread(ad, thread)._messages():
                if message.get("role") == "assistant":
                    candidates.extend(message.get("outputs") or [])
        for report in job_history.reports(ad):
            candidates.extend((report.get("result") or {}).get("evidence", {}).get("outputs", []))
            capture = report.get("capture") or {}
            if capture.get("manifest"):
                candidates.append({"path": capture["manifest"]})
                try:
                    manifest = checked_path(capture["manifest"], allowed, must_exist=True)
                    for line in manifest.read_text(encoding="utf-8").splitlines():
                        row = json.loads(line)
                        file = util.safe_seg(row["file"].removesuffix(".json"), "capture") + ".json"
                        candidates.append({"path": str(manifest.parent / file)})
                except (OSError, ValueError, KeyError):
                    pass
        for item in candidates:
            try:
                path = Path(item.get("path") or "")
                if not path.is_absolute():
                    continue
                path = checked_path(path, allowed, must_exist=True)
                if not path.is_file():
                    continue
                key = hashlib.sha256((ad.name + "|" + str(path)).encode()).hexdigest()[:24]
                found[key] = {"id": key, "agent": ad.name, "name": path.name,
                              "path": str(path), "bytes": path.stat().st_size}
            except (OSError, ValueError):
                continue
    return list(found.values())


def checked_path(path, roots, *, must_exist=False):
    """Reject escapes and reparse points, including links whose target remains inside a root."""
    from .tool_capture import _safe_path
    path = Path(path).absolute()
    bases = [Path(r).resolve() for r in roots]
    base = next((r for r in bases if path.is_relative_to(r)), None)
    if base is None:
        raise ValueError("Path is outside this operation's allowed folders.")
    current = base
    if base.is_symlink() or getattr(base, "is_junction", lambda: False)():
        raise ValueError("Linked folders are not allowed.")
    for part in path.relative_to(base).parts:
        if part in ("..", "."):
            raise ValueError("Path traversal is not allowed.")
        current /= part
        if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
            raise ValueError("Linked files or folders are not allowed.")
    if path != base:
        _safe_path(base, path.relative_to(base).as_posix())
    resolved = path.resolve(strict=must_exist)
    if not resolved.is_relative_to(base):
        raise ValueError("Path leaves its allowed folder.")
    return resolved
