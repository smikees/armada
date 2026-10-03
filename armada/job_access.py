"""Machine-local, owner-approved access and completion checks for external jobs.

Realm files are writable by agents. A job therefore cannot grant itself additional
folders or network access by adding fields to its own JSON. Grants live in the app's
machine config outside the agent sandbox and are bound to the approved job prompt.
"""
from __future__ import annotations

import hashlib
import datetime as dt
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import appconfig, scheduler

_KEY = "job_access"


@dataclass(frozen=True)
class Grant:
    roots: tuple[str, ...] = ()
    network: bool = False
    checks: tuple[dict, ...] = ()


def identity(realm_root, agent_id: str, job_id: str) -> str:
    """Stable key for a job on this machine, independent of path casing on Windows."""
    root = str(Path(realm_root).resolve()).casefold()
    return f"{root}|{agent_id}|{job_id}"


def fingerprint(job: dict) -> str:
    """Changing a prompt or tool mode revokes its access until the owner re-approves it."""
    sealed = {k: job.get(k) for k in ("id", "kind", "prompt", "allow_tools")}
    data = json.dumps(sealed, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def grant_for(realm_root, agent_id: str, job: dict | None) -> Grant:
    if not job or not isinstance(job, dict) or not job.get("id"):
        return Grant()
    job_id = str(job["id"])
    entries = appconfig.get(_KEY, {})
    entry = entries.get(identity(realm_root, agent_id, job_id)) if isinstance(entries, dict) else None
    if entry is None:
        return Grant()
    if not isinstance(entry, dict) or entry.get("fingerprint") != fingerprint(job):
        raise ValueError(f"Approved access for {job_id} no longer matches its job instructions. Re-approve it before running.")
    # A caller cannot claim another job's grant by passing its id in a synthetic dict.
    job_path = Path(realm_root) / "agents" / agent_id / "jobs" / f"{job_id}.json"
    try:
        disk_job = json.loads(job_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Cannot verify the approved job {job_id} on disk.") from exc
    if fingerprint(disk_job) != entry["fingerprint"]:
        raise ValueError(f"Approved access for {job_id} no longer matches the saved job.")
    roots = []
    for value in entry.get("roots", []):
        if not isinstance(value, str) or not value or not Path(value).is_absolute():
            raise ValueError(f"Invalid approved folder for {job_id}.")
        root = Path(value).resolve()
        if not root.is_dir():
            raise ValueError(f"Approved folder for {job_id} is unavailable: {root}")
        roots.append(str(root))
    checks = entry.get("checks", [])
    if not isinstance(checks, list) or any(not isinstance(c, dict) for c in checks):
        raise ValueError(f"Invalid completion checks for {job_id}.")
    return Grant(tuple(dict.fromkeys(roots)), entry.get("network") is True, tuple(checks))


def expanded_checks(realm_root, checks) -> list[dict]:
    """Snapshot dated output requirements for a run in the realm's timezone."""
    cfg = json.loads((Path(realm_root) / "realm.json").read_text(encoding="utf-8-sig"))
    now = scheduler.now_in(cfg)
    today_date = now.date()
    today = today_date.isoformat()
    previous_month_date = today_date.replace(day=1) - dt.timedelta(days=1)
    current_quarter_month = (today_date.month - 1) // 3 * 3 + 1
    previous_quarter_date = today_date.replace(month=current_quarter_month, day=1) - dt.timedelta(days=1)
    values = {"{today}": today,
              "{previous_month}": previous_month_date.strftime("%Y-%m"),
              "{previous_quarter}": f"{previous_quarter_date.year}-Q{(previous_quarter_date.month - 1) // 3 + 1}"}
    def expand(value):
        result = str(value)
        for key, replacement in values.items():
            result = result.replace(key, replacement)
        return result
    return [{**check, **{key: expand(check[key]) for key in ("path", "url") if key in check}}
            for check in checks]


def verify(realm_root, grant: Grant, started_wall: float) -> str:
    """Return an actionable failure, or empty text when every approved check passes."""
    if not grant.checks:
        return ""
    cfg = json.loads((Path(realm_root) / "realm.json").read_text(encoding="utf-8-sig"))
    now = scheduler.now_in(cfg)
    today_date, today = now.date(), now.date().isoformat()
    for check in expanded_checks(realm_root, grant.checks):
        kind = check.get("kind")
        try:
            if kind in ("fresh_file", "file_today", "json_today"):
                path = Path(check["path"])
                if not path.is_file():
                    return f"Expected output was not created: {path}"
                if kind in ("fresh_file", "file_today"):
                    modified = path.stat().st_mtime
                    if kind == "fresh_file" and modified < started_wall - 1:
                        return f"Expected output was not updated by this run: {path}"
                    if kind == "file_today" and dt.datetime.fromtimestamp(
                            modified, tz=now.tzinfo).date() != today_date:
                        return f"Expected output was not updated today: {path}"
                    if path.stat().st_size < int(check.get("min_bytes", 1)):
                        return f"Expected output is empty or incomplete: {path}"
                else:
                    data = json.loads(path.read_text(encoding="utf-8-sig"))
                    if data.get(check["field"]) != today:
                        return f"{path} does not report {today} in {check['field']}."
            elif kind in ("http_json_today", "http_status"):
                url = check["url"]
                if not url.startswith("https://"):
                    return f"Completion check must use HTTPS: {url}"
                parsed = urllib.parse.urlsplit(url)
                query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
                query.append(("armada_check", str(int(time.time()))))
                url = urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(query)))
                request = urllib.request.Request(url, headers={"Cache-Control": "no-cache, no-store", "Pragma": "no-cache"})
                with urllib.request.urlopen(request, timeout=12) as response:
                    if response.status != 200:
                        return f"Live verification returned HTTP {response.status}: {url}"
                    if kind == "http_json_today":
                        data = json.load(response)
                        if data.get(check["field"]) != today:
                            return f"The live {check['field']} is not {today}: {url}"
            else:
                return f"Unknown completion check: {kind}"
        except (OSError, ValueError, KeyError, TypeError, urllib.error.URLError) as exc:
            return f"Completion check {kind} failed: {exc}"
    return ""


def reported_failure(job: dict, output: str) -> str:
    """Opt-in result contract for agent jobs whose model turn is not the deliverable."""
    if job.get("require_outcome_marker") is not True:
        return ""
    markers = re.findall(r"(?im)^ARMADA_JOB_RESULT:\s*(SUCCESS|FAILED)\s*$", output or "")
    if not markers:
        return "The agent did not confirm the job deliverable. Check the job thread."
    if markers[-1].upper() != "SUCCESS":
        explanation = re.split(r"(?im)^ARMADA_JOB_RESULT:", output or "")[0].strip()
        return explanation.split("\n\n")[-1] if explanation else "The agent explicitly reported FAILED without an explanation."
    return ""
