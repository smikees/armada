"""Read-only job tool checks and a daily owner notification, independent of providers."""
from __future__ import annotations

import logging
from pathlib import Path
import re
import threading
from urllib.parse import quote

from . import clock, util

log = logging.getLogger(__name__)
TOOLS_REQUIRED = ("Say whether this job needs tools: allow_tools true (files, shell, web, "
                  "connectors, inbox) or false (text only)")
WITHOUT_TOOLS = "Runs WITHOUT tools: it cannot read or write files, use connectors or send inbox messages"


class ToolConfigurationError(ValueError):
    """A saved job cannot meet its output contract with its current tools setting."""


def agent_job(job: dict) -> bool:
    return not (job.get("kind") == "command" or job.get("run") or job.get("command"))


def required_results(job: dict) -> bool:
    contract = job.get("result_contract")
    return isinstance(contract, dict) and bool(
        contract.get("required_outputs") or contract.get("required_destinations"))


def needs_tools(job: dict) -> bool:
    """Conservative review hint, never permission to grant tools or block a text-only job."""
    if not agent_job(job):
        return False
    if required_results(job):
        return True
    prompt = str(job.get("prompt") or "")
    return bool(re.search(
        r"\{workspace\}|\b[^\s<>\"']+\.(?:md|json)\b|\b(?:mcp|connectors?|telegram|inbox)\b|"
        r"\b(?:read|write|save|open|load|create|update)\b[^\n]{0,160}"
        r"(?:[a-z]:[\\/]|(?:\.{1,2}|~)?[/\\][\w.-]+[/\\])", prompt, re.I))


def warning(job: dict) -> str:
    if not agent_job(job):
        return ""
    if type(job.get("allow_tools")) is not bool:
        return TOOLS_REQUIRED + "."
    if job["allow_tools"] is False and needs_tools(job):
        return "This job appears to need tools, but tools are off. Review the prompt and required outputs before approving or running it."
    return ""


def guard(job: dict) -> None:
    """Fail before model selection, context compaction or provider execution."""
    if not agent_job(job):
        return
    if job.get("allow_tools") is not True and required_results(job):
        raise ToolConfigurationError("Job configured without tools but requires outputs. "
                                     "Edit the job's tools setting or required outputs/destinations before running it.")
    if "allow_tools" in job and type(job["allow_tools"]) is not bool:
        raise ToolConfigurationError("Job allow_tools must be true or false. Edit the job before running it.")


def findings(realm_root, only_agent: str = "") -> list[dict]:
    """Local reads only; safe on a page-render path. Never rewrite a job."""
    from .scheduler import iter_jobs
    rows = []
    for aid, jid, job in iter_jobs(Path(realm_root)):
        if job.get("enabled") is False or (only_agent and aid != only_agent):
            continue
        reason = warning(job)
        if reason:
            rows.append({"agent": aid, "job": jid, "name": str(job.get("name") or jid),
                         "reason": reason, "href": f"/job/{quote(aid, safe='')}/{quote(jid, safe='')}"})
    return rows


def lint(realm_root) -> list[dict]:
    """Notify once per job, durably deduplicated across app restarts and daily scans."""
    from . import notify
    rows = findings(realm_root)
    if not rows:
        return rows
    state_path = Path(realm_root) / ".armada" / "job-tools-lint.json"
    with util.file_lock(state_path):
        state = util.read_json_state(state_path, default=dict)
        seen = state.setdefault("notified", {})
        if not isinstance(seen, dict):
            raise ValueError("Invalid job tools notification history; preserve it for repair.")
        for row in rows:
            key = f"{row['agent']}/{row['job']}"
            if key in seen:
                continue
            notify.emit(realm_root, "approval_needed", "Job tools need review",
                        f"Job: {row['name']}\nAgent: {row['agent']}\n{row['reason']}\n"
                        "Review it in Jobs. ARMADA has not changed the job.", href=row["href"])
            seen[key] = clock.now().isoformat(timespec="seconds")
            util.write_json_atomic(state_path, state)
    return rows


def scan_all(primary=None) -> None:
    """Check every registered active realm; one inaccessible realm cannot stop the others."""
    from . import realm_registry, realmops
    roots = {Path(primary).resolve()} if primary else set()
    try:
        roots.update(Path(row["path"]).resolve() for row in realm_registry.load())
    except (OSError, ValueError):
        log.exception("Could not discover realms for the job tools check")
    for root in sorted(roots):
        try:
            if (root / "realm.json").is_file() and not realmops.archived(root):
                lint(root)
        except Exception:
            log.exception("Could not check job tools in %s", root)


def monitor(primary, stop: threading.Event) -> None:
    """Run at startup and every day, even when scheduling is disabled or the app is in the tray."""
    while not stop.is_set():
        scan_all(primary)
        if stop.wait(24 * 60 * 60):
            return
