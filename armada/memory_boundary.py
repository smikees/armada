"""Non-destructive memory boundary: provider denials where available, observation everywhere.

A before/after fingerprint cannot identify a writer. Never use it to restore or delete data.
Observations contain paths and change kinds, not copies of private memory contents.
"""
from __future__ import annotations

import datetime as dt
import glob
import hashlib
import logging
import os
from pathlib import Path
import uuid

from . import util

log = logging.getLogger(__name__)
_FILE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
_MAX_FILES = 4000
_MAX_BYTES = 64 * 1024 * 1024
_MAX_DETAILS = 100


def protected_roots(realm_root, agent_dir) -> tuple[Path, ...]:
    """Include missing memory directories, so creating one doesn't evade the launch policy."""
    root, own = Path(os.path.abspath(realm_root)), Path(os.path.abspath(agent_dir))
    roots = [root / "memory"]
    agents = root / "agents"
    try:
        entries = sorted(agents.iterdir())
    except FileNotFoundError:
        entries = []
    roots += [p / "memory" for p in entries if p.is_dir() and p != own]
    return tuple(roots)


def claude_denials(realm_root, agent_dir) -> list[str]:
    """Absolute Edit rules cover Claude's built-in file editors, not arbitrary shell/MCP code."""
    rules = set()
    for root in protected_roots(realm_root, agent_dir):
        for path in (root.absolute(), root.resolve()):
            value = path.as_posix()
            if value.startswith("//"):
                raise util.StateError("Claude memory restrictions require a local or mapped-drive path, not UNC.")
            if any(c in value for c in ("\n", "\r", "\0")):
                raise util.StateError("Memory paths contain unsupported control characters.")
            # Claude normalizes D:\\path to /d/path; its absolute rule anchor is //.
            if len(value) > 1 and value[1] == ":":
                value = "/" + value[0].lower() + value[2:]
            value = "/" + value
            value = glob.escape(value.rstrip("/"))
            rules.update((f"Edit({value})", f"Edit({value}/**)"))
    return sorted(rules)


class MemoryAudit:
    """Bounded, read-only observations over a turn; completion never writes guarded memories."""

    def __init__(self, realm_root, agent_dir, provider="unknown"):
        self.root = Path(os.path.abspath(realm_root))
        self.agent_dir = Path(os.path.abspath(agent_dir))
        self.provider = provider
        self.id = uuid.uuid4().hex
        self.started = dt.datetime.now(dt.timezone.utc).isoformat()
        self.attempts = set()
        self.report = None
        self._recorded = False
        self.roots = ()
        self.before, self.issues = self._scan()

    def _label(self, path):
        try:
            return Path(path).absolute().relative_to(self.root).as_posix()
        except ValueError:
            return str(path)

    def protects(self, path):
        """Recognize logical and resolved targets, including a newly appointed agent's memory."""
        p = Path(path)
        if not p.is_absolute():
            p = self.agent_dir / p
        p = Path(os.path.abspath(p))
        for candidate, root in ((p, self.root), (p.resolve(), self.root.resolve())):
            try:
                parts = candidate.relative_to(root).parts
            except ValueError:
                continue
            # Path comparison follows the host's case rules (Windows names are case-insensitive).
            if parts and Path(parts[0]) == Path("memory"):
                return True
            if (len(parts) >= 3 and Path(parts[0]) == Path("agents")
                    and Path(parts[1]) != Path(self.agent_dir.name) and Path(parts[2]) == Path("memory")):
                return True
        resolved = p.resolve()
        return any(resolved == r.resolve() or r.resolve() in resolved.parents for r in self.roots)

    def observe(self, event):
        """A tool event is evidence of an attempt, not proof that the provider performed a write."""
        if not isinstance(event, dict) or event.get("kind") != "tool" or event.get("name") not in _FILE_TOOLS:
            return
        inp = event.get("input")
        if not isinstance(inp, dict):
            return
        path = inp.get("file_path") or inp.get("notebook_path") or inp.get("path")
        if isinstance(path, str) and path and self.protects(path):
            p = Path(path)
            if not p.is_absolute():
                p = self.agent_dir / p
            if len(self.attempts) < _MAX_DETAILS:
                self.attempts.add(self._label(Path(os.path.abspath(p))))

    def _scan(self):
        files, issues = {}, []
        total = visited = 0
        try:
            # Re-enumerate at completion: other agents/memory folders can appear during a run.
            self.roots = protected_roots(self.root, self.agent_dir)
        except OSError:
            return files, ["Could not enumerate protected memory directories."]
        pending = list(self.roots)
        while pending:
            path = pending.pop()
            label = self._label(path)
            try:
                info = path.lstat()
                visited += 1
                if visited > _MAX_FILES or total >= _MAX_BYTES:
                    issues.append("Memory audit size limit reached; observation is incomplete.")
                    break
                # Do not traverse symlinks/junctions or capture content outside the observed tree.
                # Report their presence as a coverage limitation rather than inventing a clean scan.
                if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
                    files[label] = "link:" + os.readlink(path)
                    issues.append(f"Linked memory path was not traversed: {label}")
                elif path.is_dir():
                    pending.extend(sorted(path.iterdir()))
                elif path.is_file():
                    if total + info.st_size > _MAX_BYTES:
                        issues.append("Memory audit size limit reached; observation is incomplete.")
                        break
                    digest = hashlib.sha256()
                    with path.open("rb") as stream:
                        while chunk := stream.read(65536):
                            total += len(chunk)
                            if total > _MAX_BYTES:
                                raise OSError("audit size limit")
                            digest.update(chunk)
                    files[label] = digest.hexdigest()
            except FileNotFoundError:
                continue
            except OSError:
                issues.append(f"Could not inspect memory path: {label}")
        return files, issues[:_MAX_DETAILS]

    def finish(self):
        """Return idempotent observations; unknown writers are never labelled as this agent."""
        if self.report is not None:
            return self.report
        after, issues = self._scan()
        changes = []
        for path in sorted(self.before.keys() | after.keys()):
            if self.before.get(path) != after.get(path):
                # A partial scan cannot distinguish a new/deleted file from an unreadable one.
                if (self.issues or issues) and (path not in self.before or path not in after):
                    continue
                changes.append({"path": path, "change": "added" if path not in self.before else
                                "removed" if path not in after else "modified", "writer": "unknown"})
        self.report = {
            "schema_version": 1, "audit_id": self.id, "agent": self.agent_dir.name,
            "provider": self.provider, "started": self.started,
            "finished": dt.datetime.now(dt.timezone.utc).isoformat(),
            "protection": "file-tool-denials-requested-and-audit" if self.provider == "claude" else "audit-only",
            "limitation": "Shell, MCP and other processes are not contained by this memory boundary."
                if self.provider == "claude" else "This adapter does not enforce per-memory write isolation.",
            "changes": changes[:_MAX_DETAILS], "change_count": len(changes),
            "write_attempts": sorted(self.attempts),
            "scan_issues": sorted(set(self.issues + issues))[:_MAX_DETAILS],
        }
        return self.report

    def record(self, thread=None):
        """Keep evidence even if the engine raises/cancels before it can produce a run report."""
        report = self.finish()
        if self._recorded:
            return report
        self._recorded = True
        if not (report["changes"] or report["write_attempts"] or report["scan_issues"]):
            return report
        message = (f"{report['change_count']} protected memory path(s) changed during this run; "
                   "the writer is unknown and may be another agent, the owner or system upkeep. "
                   "Armada preserved the current files.")
        if report["write_attempts"]:
            message += f" The provider reported {len(report['write_attempts'])} write attempt(s) to protected memory; execution is not confirmed."
        if report["scan_issues"]:
            message += " Memory observation was incomplete; see the audit details."
        log.warning("Memory observation for %s: %s", self.agent_dir.name, message)
        path = self.agent_dir / "runs" / "memory-audits" / f"{self.id}.json"
        try:
            if not self.agent_dir.is_dir():
                return report
            with util.file_lock(path):
                util.write_json_atomic(path, report)
        except OSError:
            util.swallowed(log, "Could not persist memory audit")
            message += " The audit file could not be saved."
        if thread is not None:
            try:
                thread.append_event("memory_boundary", title="Memory boundary observation", subtitle=message,
                                    status="warning", meta=report)
            except OSError:
                util.swallowed(log, "Could not persist memory observation in thread")
        return report
