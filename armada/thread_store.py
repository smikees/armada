"""Recoverable thread history mutations, serialized on the existing messages-file lock.

A prepared journal is the commit decision. Every participating read/write finishes it before
touching history, so a process crash between summary and log replacement cannot mix generations.
The model call is deliberately outside this module and outside the lock.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import uuid

from . import util


class CompactionConflict(util.StateError):
    """History was rewritten while a summary was being generated; retry from a fresh snapshot."""


def entries(raw: str, *, strict=True):
    """Keep original lines for rewriting; tolerant display never becomes compaction input."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    result = []
    # JSONL separates records with LF. Unicode line separators are valid INSIDE JSON strings.
    lines = raw.split("\n")
    for i, text_line in enumerate(lines):
        line = text_line + ("\n" if i < len(lines) - 1 else "")
        text = line.strip().lstrip("\ufeff")
        record = None
        if text:
            try:
                record = json.loads(text, object_pairs_hook=unique)
                if not isinstance(record, dict):
                    raise ValueError("expected a message object")
            except ValueError as exc:
                if strict:
                    raise util.StateError("Invalid messages.jsonl; preserve the log and repair it before changing history.") from exc
                record = None
        result.append((line, record))
    return result


@dataclass(frozen=True)
class HistorySnapshot:
    messages: str
    summary: str
    revision: str


class HistoryStore:
    def __init__(self, directory):
        self.dir = Path(directory)
        self.msgs = self.dir / "messages.jsonl"
        self.summary = self.dir / "summary.md"
        self.revision = self.dir / ".history-revision"
        self.journal = self.dir / ".history-transaction.json"

    @staticmethod
    def _read(path):
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""
        except UnicodeError as exc:
            raise util.StateError(f"Invalid encoding in {path.name}; preserve it before repairing history.") from exc

    def _current(self):
        return HistorySnapshot(self._read(self.msgs), self._read(self.summary), self._read(self.revision))

    @staticmethod
    def _checksum(payload):
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

    def _recover(self):
        """Roll forward only recognized before/after states, while the messages lock is held."""
        if not self.journal.exists():
            return
        util.assert_realm_writable(self.journal, allow_invalid_realm=True)
        txn = util.read_json_state(self.journal, max_schema=1)
        payload = {key: txn.get(key) for key in ("operation", "before", "after")}
        try:
            if txn.get("schema_version") != 1 or payload["operation"] not in ("compact", "truncate"):
                raise ValueError("unknown journal")
            if self._checksum(payload) != txn.get("checksum"):
                raise ValueError("checksum mismatch")
            for state in (payload["before"], payload["after"]):
                if not isinstance(state, dict) or set(state) != {"messages", "summary", "revision"}:
                    raise ValueError("invalid state")
                if any(not isinstance(v, str) for v in state.values()):
                    raise ValueError("invalid field")
                entries(state["messages"])
            before, after = HistorySnapshot(**payload["before"]), HistorySnapshot(**payload["after"])
            if not after.revision or after.revision == before.revision:
                raise ValueError("invalid revision")
        except (TypeError, ValueError) as exc:
            raise util.StateError("Invalid thread transaction; preserve .history-transaction.json for recovery.") from exc
        current = self._current()
        # Validate ALL files before replacing ANY of them. Unknown external edits must survive.
        for key in ("summary", "messages", "revision"):
            if getattr(current, key) not in (getattr(before, key), getattr(after, key)):
                raise util.StateError("Thread files changed outside the transaction; preserve all files and the journal for recovery.")
        for key, path in (("summary", self.summary), ("messages", self.msgs), ("revision", self.revision)):
            if getattr(current, key) != getattr(after, key):
                util.write_text_atomic(path, getattr(after, key))
        self.journal.unlink()

    def read(self):
        """Read one coherent summary/log generation, recovering an interrupted commit first."""
        if not self.dir.exists():
            return HistorySnapshot("", "", "")
        # A supported thread without a pending transaction is inspectable in a newer realm.
        with util.file_lock(self.msgs, validate_state=False):
            self._recover()
            return self._current()

    def append(self, records):
        chunk = "".join(json.dumps(m, ensure_ascii=False) + "\n" for m in records)
        with util.file_lock(self.msgs):
            self._recover()
            current = self._current()
            entries(current.messages)
            if current.messages and not current.messages.endswith(("\r", "\n")):
                chunk = "\n" + chunk
            with self.msgs.open("a", encoding="utf-8", newline="") as stream:
                stream.write(chunk)
                stream.flush()
                os.fsync(stream.fileno())

    def _commit(self, before, messages, summary, operation):
        # Match text-mode reads on every host; provider summaries may arrive with CRLF.
        messages = messages.replace("\r\n", "\n").replace("\r", "\n")
        summary = summary.replace("\r\n", "\n").replace("\r", "\n")
        after = HistorySnapshot(messages, summary, uuid.uuid4().hex)
        payload = {"operation": operation, "before": asdict(before), "after": asdict(after)}
        # No history file changes until the complete old/new state is durably prepared.
        util.write_json_atomic(self.journal, {"schema_version": 1, **payload, "checksum": self._checksum(payload)})
        self._recover()

    def compact(self, snapshot, kept, summary):
        """Commit only an unchanged prefix/revision; append-only tail growth is always retained."""
        with util.file_lock(self.msgs):
            self._recover()
            current = self._current()
            if (current.revision != snapshot.revision or current.summary != snapshot.summary
                    or not current.messages.startswith(snapshot.messages)):
                raise CompactionConflict("Conversation changed during compaction. No stale summary was committed; retry with the current history.")
            entries(current.messages)
            self._commit(current, kept + current.messages[len(snapshot.messages):], summary, "compact")

    def truncate(self, keep):
        """Owner-requested truncation shares the compaction lock and advances its revision."""
        with util.file_lock(self.msgs):
            self._recover()
            current = self._current()
            lines = [line for line, record in entries(current.messages) if record is not None]
            keep = min(max(0, keep), len(lines))
            if keep < len(lines):
                self._commit(current, "".join(lines[:keep]), current.summary, "truncate")
            return keep
