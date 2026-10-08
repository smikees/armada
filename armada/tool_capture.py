"""Opt-in local tool-result capture, run audits and conservative retention."""
from __future__ import annotations

import datetime as dt
from fnmatch import fnmatchcase
import hashlib
import json
import logging
import os
from pathlib import Path, PureWindowsPath
import re

from . import clock, util, workspace
from .engine.raw_results import payload

log = logging.getLogger(__name__)
DEFAULT_DIR = "Finance/data/raw/{date}/{job}/"
KEYS = ("capture_tools", "capture_dir", "require_capture", "capture_keep_days")


def matches(tool, patterns):
    """Case-sensitive, whole-name shell globs, independent of the host OS."""
    return any(fnmatchcase(tool, pattern) for pattern in patterns)


def _safe_path(base, relative):
    """Reject traversal, Windows aliases and reparse points before filesystem access."""
    raw = str(relative).replace("\\", "/")
    win = PureWindowsPath(raw)
    if not raw or raw.startswith("/") or win.drive or win.root:
        raise ValueError("capture_dir must be relative to the realm workspace.")
    parts = raw.rstrip("/").split("/")
    for part in parts:
        if (part in ("", ".", "..") or part.rstrip(" .") != part
                or re.search(r'[<>:"|?*\x00-\x1f]', part)
                or re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part)):
            raise ValueError("Unsafe capture path: traversal and Windows path aliases are refused.")
    base = Path(base).resolve()
    target = base.joinpath(*parts)
    for parent in [*target.parents, target]:
        if parent == base:
            continue
        if parent.is_relative_to(base):
            if parent.is_symlink() or (hasattr(parent, "is_junction") and parent.is_junction()):
                raise ValueError("Capture paths cannot contain symlinks or junctions.")
            try:
                if getattr(parent.lstat(), "st_file_attributes", 0) & 0x400:
                    raise ValueError("Capture paths cannot contain reparse points.")
            except FileNotFoundError:
                pass
    if not target.resolve().is_relative_to(base):
        raise ValueError("Capture path escapes the realm workspace.")
    return target


def validate(job, realm_root, job_id, *, run_id="validation", date=None, workspace_root=None):
    patterns = job.get("capture_tools", [])
    if not isinstance(patterns, list) or any(not isinstance(p, str) or not p.strip() for p in patterns):
        raise ValueError("capture_tools must be a list of nonempty full-tool-name globs.")
    if len(patterns) > 100 or any(len(p) > 500 for p in patterns):
        raise ValueError("Too many or oversized capture tool patterns.")
    keep = job.get("capture_keep_days", 30)
    if type(keep) is not int or keep < 1 or keep > 36500:
        raise ValueError("capture_keep_days must be an integer from 1 to 36500.")
    if type(job.get("require_capture", False)) is not bool:
        raise ValueError("require_capture must be true or false.")
    template = job.get("capture_dir") or DEFAULT_DIR
    if not isinstance(template, str):
        raise ValueError("capture_dir must be a relative path.")
    expanded = template.replace("{job}", util.safe_seg(job_id, "job")).replace(
        "{run}", util.safe_seg(run_id, "run")).replace("{date}", date or clock.today().isoformat())
    if "{" in expanded or "}" in expanded:
        raise ValueError("capture_dir supports only {job}, {date} and {run}.")
    # Validate even when disabled, so a traversal value cannot be saved for later.
    base = str(workspace_root) if workspace_root is not None else workspace.root(realm_root)
    target = _safe_path(base or realm_root, expanded)
    if patterns and (not base or not Path(base).is_absolute() or not Path(base).is_dir()):
        raise ValueError("Set an existing absolute realm workspace before enabling capture.")
    return target


class ToolCapture:
    """Synchronous writes at result arrival; failures are audit data, never observer exceptions."""
    def __init__(self, root, job, job_id, run_id, provider, supported, agent, *, workspace_root=None, index_root=None):
        self.root, self.job = Path(root), job
        self.workspace_root = workspace_root
        self.job_id, self.run_id, self.agent = job_id, run_id, agent
        self.patterns = job.get("capture_tools") or []
        self.required = job.get("require_capture") is True
        self.errors, self.records, self.pending, self.done = [], [], {}, set()
        self.ignored = set()
        self.directory = None
        self.base = None
        self.matched = 0
        self.provider = provider
        self.date = clock.today().isoformat()
        self.index = Path(index_root or self.root) / "capture-index" / (util.safe_seg(run_id, "run") + ".json")
        try:
            self.directory = validate(job, root, job_id, run_id=run_id, date=self.date, workspace_root=workspace_root)
            self.base = Path(workspace_root if workspace_root is not None else workspace.root(root)).resolve()
            if not supported:
                raise ValueError(f"Tool capture is unsupported for {provider}.")
            self._checked()
            self.directory.mkdir(parents=True, exist_ok=True)
            self._checked()
            with util.file_lock(self.index):
                util.write_json_atomic(self.index, {"run_id": run_id, "agent": agent,
                    "directory": str(self.directory.relative_to(self.base)),
                    "workspace": str(self.base), "keep_days": job.get("capture_keep_days", 30),
                    "started": clock.now().isoformat(), "owner_pid": os.getpid()})
        except Exception as exc:
            log.exception("Tool capture initialization failed")
            self.fail(str(exc))
            self.directory = None

    def fail(self, reason):
        reason = str(reason)
        if reason not in self.errors:
            self.errors.append(reason)
            log.warning("Tool capture incomplete for %s: %s", self.run_id, reason)

    def _checked(self):
        current = validate(self.job, self.root, self.job_id, run_id=self.run_id, date=self.date, workspace_root=self.workspace_root)
        base = self.workspace_root if self.workspace_root is not None else workspace.root(self.root)
        if current != self.directory or Path(base).resolve() != self.base:
            raise ValueError("Capture workspace changed during the run.")
        for name in ("manifest.jsonl",):
            _safe_path(self.base, (self.directory / name).relative_to(self.base).as_posix())

    def on_event(self, event):
        try:
            self._event(event)
        except Exception as exc:
            log.exception("Tool result capture failed")
            self.fail(f"{event.get('id') or 'tool result'}: {exc}")

    def _event(self, event):
        kind, tid = event.get("kind"), event.get("id")
        name = event.get("name", "")
        if kind == "tool" and tid not in self.done:
            if matches(name, self.patterns):
                self.pending.setdefault(tid, {"tool": name, "arguments": event.get("input", {}),
                                             "started": clock.now().isoformat()})
            else:
                self.ignored.add(tid)
        if kind != "tool_result" or tid in self.done or tid in self.ignored:
            return
        call = self.pending.pop(tid, None)
        if call is None and name and matches(name, self.patterns):
            call = {"tool": name, "arguments": event.get("input", {}), "started": None}
        if call is None:
            if not name and event.get("raw_result"):
                self.fail(f"{tid}: result has no corresponding tool name; capture matching could not be checked.")
            return
        self.done.add(tid)
        self.matched += 1
        finished = clock.now().isoformat()
        text, encoding = payload(event.get("raw_result") or {})
        data = text.encode("utf-8")
        sha = hashlib.sha256(data).hexdigest()
        # The complete received payload is kept in the transcript independently of the file.
        record = {**call, "id": tid, "payload": text, "encoding": encoding,
                  "sha256": sha, "byte_size": len(data)}
        self.records.append(record)
        if self.directory is None:
            raise ValueError("Capture directory unavailable.")
        self._checked()
        manifest = self.directory / "manifest.jsonl"
        with util.file_lock(manifest, validate_state=False):
            self._checked()
            previous = manifest.read_text(encoding="utf-8") if manifest.exists() else ""
            rows = [json.loads(line) for line in previous.splitlines() if line]
            seq = max([row["seq"] for row in rows] + [0]) + 1
            # Include uncommitted payloads after a crash; never overwrite them.
            for file in self.directory.glob("*.json"):
                prefix = file.name.partition("-")[0]
                if prefix.isdigit():
                    seq = max(seq, int(prefix) + 1)
            slug = re.sub(r"[^A-Za-z0-9_-]", "_", call["tool"])[:120] or "tool"
            filename = f"{seq:06d}-{slug}.json"
            path = _safe_path(self.base, (self.directory / filename).relative_to(self.base).as_posix())
            util.write_text_atomic(path, text, newline="")
            self._checked()
            row = {**call, "seq": seq, "finished": finished, "run_id": self.run_id,
                   "job_id": self.job_id, "agent_id": self.agent, "is_error": bool(event.get("is_error")),
                   "byte_size": len(data), "sha256": sha, "file": filename, "encoding": encoding}
            if previous and not previous.endswith("\n"):
                previous += "\n"
            try:
                util.write_text_atomic(manifest, previous + json.dumps(row, ensure_ascii=False) + "\n", newline="")
            except Exception:
                # This payload was never advertised to readers. Avoid leaving a misleading orphan.
                # If cleanup itself fails, retain the original write failure for the audit.
                log.exception("Capture manifest commit failed")
                try:
                    self._checked()
                    if hashlib.sha256(path.read_bytes()).hexdigest() == sha:
                        path.unlink()
                except OSError:
                    log.exception("Could not remove uncommitted capture payload")
                raise
            record.update(file=filename, seq=seq, saved=True)

    def finish(self):
        for call in self.pending.values():
            self.matched += 1
            self.fail(f"{call['tool']}: matching call ended without an exposed result.")
        self.pending.clear()
        if self.index.exists():
            try:
                util.mutate_json(self.index, lambda data: data.update(finished=clock.now().isoformat()))
            except Exception as exc:
                log.exception("Capture retention index could not be finished")
                self.fail(f"Capture retention index: {exc}")

    def report(self):
        return {"status": "incomplete" if self.errors else "complete",
                "count": sum(bool(r.get("saved")) for r in self.records), "matched": self.matched,
                "errors": list(self.errors), "require_capture": self.required,
                "directory": str(self.directory) if self.directory else "",
                "manifest": str(self.directory / "manifest.jsonl") if self.directory else ""}

    def audit(self, result):
        info = self.report()
        result["capture"] = info
        if self.errors:
            result["audit_outcome"] = "incomplete"
            result["app_errors"].extend("Capture incomplete: " + e for e in self.errors)
            if self.required:
                result["execution"] = "failed"


def prune(realm_root):
    """Prune only registered, expired run payloads; never recursively delete a folder."""
    root, removed, errors = Path(realm_root), 0, []
    base = workspace.root(root)
    if not base:
        return {"removed": 0, "errors": []}
    base = Path(base).resolve()
    for index in (root / "capture-index").glob("*.json"):
        try:
            with util.file_lock(index):
                entry = util.read_json_state(index)
                age = clock.now() - dt.datetime.fromisoformat(entry.get("finished") or entry["started"])
                if age.total_seconds() < entry["keep_days"] * 86400:
                    continue
                # A live owner may still be writing a long-running job.
                if not entry.get("finished") and util.pid_alive(entry.get("owner_pid", 0)):
                    continue
                if Path(entry["workspace"]).resolve() != base:
                    raise ValueError("Recorded workspace changed; retention skipped.")
                directory = _safe_path(base, entry["directory"])
                manifest = _safe_path(base, (directory / "manifest.jsonl").relative_to(base).as_posix())
                with util.file_lock(manifest, validate_state=False):
                    if not manifest.exists():
                        index.unlink()
                        continue
                    lines = manifest.read_text(encoding="utf-8").splitlines(keepends=True)
                    keep = []
                    for line in lines:
                        row = json.loads(line)
                        if row.get("run_id") != entry["run_id"]:
                            keep.append(line)
                            continue
                        filename = row["file"]
                        if not re.fullmatch(r"[0-9]+-[A-Za-z0-9_-]+\.json", filename):
                            raise ValueError("Unsafe capture filename; retention skipped.")
                        target = _safe_path(base, (directory / filename).relative_to(base).as_posix())
                        if target.exists():
                            if hashlib.sha256(target.read_bytes()).hexdigest() != row["sha256"]:
                                raise ValueError("Captured file changed; retention skipped.")
                            target.unlink()
                            removed += 1
                    util.write_text_atomic(manifest, "".join(keep), newline="")
                index.unlink()
        except Exception as exc:
            log.warning("Capture retention skipped %s: %s", index, exc)
            errors.append(str(exc))
    return {"removed": removed, "errors": errors}
