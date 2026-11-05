"""Record health: strict admission, diagnostic views, and explicit owner repair.

Presentation failures never supply replacement configuration to execution. Original
bytes are retained, including when an owner replaces a damaged configuration.
"""
from __future__ import annotations

import hashlib
import datetime
import json
import math
import uuid
from pathlib import Path

from . import util


def decode(raw: str | bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError("non-finite number")

    if isinstance(raw, bytes):
        raw = raw.decode("utf-8-sig")
    value = json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def validate(data: dict, kind: str, identity: str | None = None) -> dict:
    """Validate consumed field shapes; missing optional fields retain legacy semantics."""
    if not isinstance(data, dict):
        raise util.StateError(f"Invalid {kind} record: expected an object.")
    strings = ("id", "name", "display", "leader", "role", "membership", "mandate", "soul",
               "appointed", "autonomy", "inbox_frequency", "model", "effort", "verbosity",
               "kind", "prompt", "summary", "thread", "schedule", "cron", "cwd", "created", "budget")
    for field in strings:
        nullable = field in ("model", "effort", "verbosity", "cron", "role", "summary", "cwd", "appointed")
        if field in data and not (isinstance(data[field], str) or nullable and data[field] is None):
            raise util.StateError(f"Invalid {kind} record: {field} must be text.")
    for field in ("enabled", "coordinator", "allow_tools", "is_inspector", "inspector"):
        if field in data and type(data[field]) is not bool:
            raise util.StateError(f"Invalid {kind} record: {field} must be true or false.")
    if identity is not None and data.get("id", identity) != identity:
        raise util.StateError(f"Invalid {kind} record: id must match its folder or filename ({identity}).")
    for field in ("run", "command"):
        if field in data and not (isinstance(data[field], str) or
                isinstance(data[field], list) and all(isinstance(v, str) for v in data[field])):
            raise util.StateError(f"Invalid {kind} record: {field} must be text or a list of arguments.")
    if "env" in data and not isinstance(data["env"], dict):
        raise util.StateError(f"Invalid {kind} record: env must be an object.")
    for field in ("timeout", "max_budget_usd"):
        value = data.get(field)
        if value in (None, ""):
            continue
        try:
            if isinstance(value, bool) or not math.isfinite(float(value)):
                raise ValueError()
        except (ValueError, TypeError, OverflowError):
            raise util.StateError(f"Invalid {kind} record: {field} must be a finite number.") from None
    return data


def read(path: Path, kind: str, *, max_schema="current") -> dict:
    path = Path(path)
    identity = path.parent.name if kind == "agent" else path.stem
    return validate(util.read_json_state(path, max_schema=max_schema), kind, identity)


def admit_agent(root, agent) -> dict:
    """Strict shared admission for automatic dispatch and deterministic commands."""
    from .access_policy import load
    data = read(Path(root) / "agents" / util.safe_seg(agent, "agent") / "agent.json", "agent")
    load(root, data)
    return data


def presentation(path: Path, kind: str) -> tuple[dict | None, str]:
    """A missing config is damaged too; callers must render an explicit held record."""
    try:
        data = read(path, kind, max_schema=None)
        if kind == "agent":
            from .access_policy import load
            load(Path(path).parent.parent.parent, data)
        return data, ""
    except (OSError, ValueError, RecursionError) as exc:
        return None, f"{Path(path).name}: {exc} Work is held until this record is repaired."


def history(path: Path) -> tuple[list[dict], list[str]]:
    """Display valid rows, diagnose excluded rows; never rewrite the evidence."""
    path = Path(path)
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except FileNotFoundError:
        return [], []
    except (OSError, UnicodeError):
        return [], [f"{path.name}: cannot read history; repair access or encoding."]
    rows, errors = [], []
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            row = decode(line)
            for field in ("task", "ts", "status", "kind", "summary", "run_id", "thread"):
                if field in row and not isinstance(row[field], str):
                    raise ValueError("invalid history field")
            if row.get("ts"):
                datetime.datetime.fromisoformat(row["ts"])
            for field in ("result", "retry"):
                if row.get(field) is not None and not isinstance(row[field], dict):
                    raise ValueError("invalid history object")
            tokens = row.get("tokens")
            if tokens is not None:
                if not isinstance(tokens, dict):
                    raise ValueError("invalid tokens")
                for key in ("total", "input", "output", "api_equiv_usd"):
                    value = tokens.get(key)
                    if value is not None and key != "api_equiv_usd":
                        int(value)
                    if value is not None and (isinstance(value, bool) or
                            not math.isfinite(float(value)) or float(value) < 0):
                        raise ValueError("invalid token count")
            rows.append(row)
        except (ValueError, TypeError, OverflowError, RecursionError):
            errors.append(f"{path.name}: invalid history row {number}; totals are incomplete.")
    return rows, errors


def target(root, agent, job="") -> Path:
    from .tool_capture import _safe_path
    if not isinstance(agent, str) or not isinstance(job, str):
        raise ValueError("Agent and job identifiers must be text.")
    relative = f"agents/{util.safe_seg(agent, 'agent')}/"
    relative += f"jobs/{util.safe_seg(job, 'job')}.json" if job else "agent.json"
    return _safe_path(Path(root).absolute(), relative)


def repair(root, agent, job, replacement, expected_sha256):
    """Owner-only operation: validate, compare, preserve evidence, atomically replace.

    The evidence manifest is durable before replacement. A crash can leave an unused
    backup, never an unbacked repair. The backup is not a source of run permissions.
    """
    from . import clock, access_policy
    from .capabilities import _policy_toolkit
    root = Path(root)
    path = target(root, agent, job)
    kind = "job" if job else "agent"
    if not isinstance(replacement, str) or not isinstance(expected_sha256, str):
        raise ValueError("Replacement JSON and the reviewed file fingerprint are required.")
    try:
        data = validate(decode(replacement), kind, job or agent)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise util.StateError("Replacement must be valid JSON with unique keys.") from exc
    with util.file_lock(path, validate_state=False):
        target(root, agent, job)  # Recheck links after acquiring the shared lock.
        util.assert_realm_writable(path)
        try:
            util.read_json_state(path)
        except util.UnsupportedSchemaError:
            raise
        except util.StateError:
            pass  # An explicitly reviewed repair may replace damaged bytes, not a newer schema.
        before = path.read_bytes()
        digest = hashlib.sha256(before).hexdigest()
        if digest != expected_sha256:
            raise util.StateError("The record changed since review. Reload it before repairing.")
        if not job:
            access_policy.validate(util.read_json_state(root / "realm.json"), data)
            _policy_toolkit(data, "agent", grants_only=True)
        # Use the ordinary strict loader on a staging file to validate schema too.
        from .tool_capture import _safe_path
        evidence = _safe_path(root.absolute(), f".armada/record-repairs/{uuid.uuid4().hex}/replacement.json")
        util.write_json_atomic(evidence, data)
        util.read_json_state(evidence)
        util.write_text_atomic(evidence.with_name("original.bin"), before.decode("latin-1"),
                               encoding="latin-1", newline="")
        util.write_json_atomic(evidence.with_name("repair.json"), {
            "actor": "owner", "ts": clock.now().isoformat(),
            "record": path.relative_to(root.absolute()).as_posix(), "original_sha256": digest,
            "replacement_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest()})
        # Same filesystem, fsynced by write_json_atomic; no permissive state reset.
        util._replace_retrying(evidence, path)
    return {"ok": True, "backup": evidence.with_name("original.bin").relative_to(root.absolute()).as_posix()}
