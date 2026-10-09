"""Versioned per-run job results. Execution, audit and delivery are independent."""
from __future__ import annotations

import copy
import datetime as dt
import json
from pathlib import Path
import re

VERSION = 1
EXECUTIONS = {"completed", "failed", "stopped", "timed_out"}
AUDITS = {"clear", "findings", "incomplete", "not_applicable"}
DELIVERIES = {"sent", "failed", "unknown", "not_required"}
BLOCK = re.compile(r"<armada_job_result>\s*(.*?)\s*</armada_job_result>", re.S)
LEGACY = re.compile(r"(?im)^ARMADA_JOB_RESULT:\s*(SUCCESS|FAILED)\s*$")


def instructions(run_id: str, job: dict) -> str:
    return f"""\n\nARMADA structured job result contract v1 (current run ID: {run_id})
After your original human-readable final answer, supply exactly one final block:
<armada_job_result>
{{"schema_version":1,"run_id":"{run_id}","execution":"completed",
"audit_outcome":"not_applicable","delivery":[],"evidence":{{"outputs":[],
"findings":[],"missing_inputs":[],"operational_errors":[],"risk_gates":[],\n"observations":[],"expected_unknowns":[]}}}}
</armada_job_result>
Execution: completed, failed, stopped, timed_out. A reviewer report explaining
unresolved evidence can be completed; rule breaches are findings; missing accounting
or historical risk evidence makes that audit incomplete, not execution failed.
A required operational prerequisite (such as a fresh source read or sync) failing
before the requested work is performed means execution failed, even if an error
report was written or a failure notification was delivered. Record its missing input
and operational error; a sent notification alone never proves the job succeeded.
Audit: clear, findings, incomplete, not_applicable. Incomplete may also have findings.
Delivery: one object per required destination with destination, status (sent,
failed, unknown, not_required), receipt_path (if sent), error (if failed).
Evidence outputs: objects with absolute path and required (true for required reports).
Evidence findings, missing_inputs, operational_errors, risk_gates: lists of strings.
Findings are audit/rule breaches, not ordinary research facts or calendar entries.
Missing inputs are REQUIRED evidence unavailable for the requested work. Optional future
announcements are expected_unknowns. General facts and research notes are observations.
Optional evidence observations and expected_unknowns: lists of strings. These do not
invalidate not_applicable or clear; actual breaches and missing required inputs still do.
Keep unresolved warnings and risk gates visible. Completion never clears a risk gate.
Receipts must be JSON with schema_version:1, run_id:"{run_id}", destination,
status:"sent", sent_at (ISO timestamp), and provider message_ids or receipt_id.
An earlier receipt cannot prove delivery for this run. Preserve real provider responses;
never fabricate a receipt or copy an earlier receipt under this run ID. If the Finance
Telegram sender is used, pass --run-id {run_id} and use its per-run receipt path.
Do not resend an unchanged report merely to acquire a new receipt: report unknown
and explain any earlier delivery. Report exact operational errors separately from findings.
Required result configuration: {json.dumps(job.get('result_contract') or {}, ensure_ascii=False)}
Use this block instead of a legacy ARMADA_JOB_RESULT marker when possible.
"""


def original_answer(output: str) -> str:
    """Hide only the structured machine block; keep the agent's legacy marker verbatim."""
    return BLOCK.sub("", output or "").strip()


def _parse(output: str, run_id: str) -> dict | None:
    blocks = BLOCK.findall(output or "")
    if not blocks:
        if "<armada_job_result>" in output or "</armada_job_result>" in output:
            raise ValueError("Structured result block is not closed correctly.")
        return None
    if len(blocks) != 1 or len(blocks[0]) > 65536:
        raise ValueError("Expected one structured result block of at most 64 KiB.")
    trailing = BLOCK.split(output)[-1].strip()
    if trailing and not LEGACY.fullmatch(trailing):
        raise ValueError("Structured result must be the final result block.")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate result field: {key}")
            result[key] = value
        return result
    data = json.loads(blocks[0], object_pairs_hook=unique)
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != VERSION:
        raise ValueError("Unsupported job result schema_version; expected 1.")
    if data.get("run_id") != run_id:
        raise ValueError("Structured result belongs to a different run ID.")
    if data.get("execution") not in EXECUTIONS or data.get("audit_outcome") not in AUDITS:
        raise ValueError("Invalid execution or audit outcome.")
    deliveries, evidence = data.get("delivery"), data.get("evidence")
    if not isinstance(deliveries, list) or not isinstance(evidence, dict):
        raise ValueError("Result needs delivery list and evidence object.")
    seen = set()
    for item in deliveries:
        if not isinstance(item, dict) or not isinstance(item.get("destination"), str) or not item["destination"]:
            raise ValueError("Delivery needs a non-empty destination.")
        if item["destination"] in seen or item.get("status") not in DELIVERIES:
            raise ValueError("Duplicate destination or invalid delivery status.")
        for field in ("receipt_path", "error"):
            if field in item and not isinstance(item[field], str):
                raise ValueError(f"Delivery {field} must be a string.")
        seen.add(item["destination"])
    for key in ("findings", "missing_inputs", "operational_errors", "risk_gates"):
        if not isinstance(evidence.get(key), list) or any(not isinstance(x, str) for x in evidence[key]):
            raise ValueError(f"Evidence {key} must be a list of strings.")
    for key in ("observations", "expected_unknowns"):
        if key in evidence and (not isinstance(evidence[key], list) or
                                any(not isinstance(x, str) for x in evidence[key])):
            raise ValueError(f"Evidence {key} must be a list of strings.")
    if not isinstance(evidence.get("outputs"), list):
        raise ValueError("Evidence outputs must be a list.")
    for item in evidence["outputs"]:
        if (not isinstance(item, dict) or not isinstance(item.get("path"), str)
                or type(item.get("required")) is not bool):
            raise ValueError("Each output needs path and required boolean.")
    if data["audit_outcome"] == "findings" and not evidence["findings"]:
        raise ValueError("Audit findings require recorded findings.")
    return data


def _path(value, roots) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise ValueError(f"Evidence path must be absolute: {value}")
    path = path.resolve()
    if not any(path.is_relative_to(Path(root).resolve()) for root in roots):
        raise ValueError(f"Evidence path is outside this run's approved folders: {path}")
    return path


def check_aspect(check: dict) -> tuple[str, str]:
    """Approved checks may declare their aspect; old Telegram/publication checks retain it."""
    path = str(check.get("path") or "").replace("\\", "/").lower()
    if check.get("aspect") == "delivery" or "telegram-receipt" in path:
        return "delivery", check.get("destination") or "telegram"
    if check.get("kind", "").startswith("http_"):
        return "delivery", check.get("destination") or "website"
    return "execution", ""


def requirements(job: dict, checks) -> dict:
    """Add sealed machine-approved outputs/destinations without changing saved job prompts/grants."""
    spec = copy.deepcopy(job.get("result_contract") or {})
    if not isinstance(spec, dict):
        raise ValueError("Invalid job result_contract configuration.")
    outputs, destinations = spec.setdefault("required_outputs", []), spec.setdefault("required_destinations", [])
    if not isinstance(outputs, list) or not isinstance(destinations, list):
        raise ValueError("Required outputs and destinations must be lists.")
    for check in checks:
        aspect, destination = check_aspect(check)
        if aspect == "delivery":
            if destination not in destinations:
                destinations.append(destination)
        elif check.get("path") and check["path"] not in outputs:
            outputs.append(check["path"])
    return {**job, "result_contract": spec}


def evaluate(output: str, *, run_id: str, job: dict, root: Path, started: float,
             runtime_execution: str = "completed", runtime_error: str = "", roots=(), checks=()) -> dict:
    """Validate claims against this run. Contract defects warn; runtime errors stay operational."""
    errors = []
    markers = LEGACY.findall(output or "")
    marker = markers[-1].upper() if markers else None
    try:
        data = _parse(output or "", run_id)
    except (ValueError, TypeError, KeyError) as exc:
        data = None
        errors.append(f"Invalid structured job result: {exc}")
    if data is None:
        explanation = LEGACY.split(output or "")[0].strip()
        data = {"schema_version": VERSION, "run_id": run_id,
                "execution": "failed" if marker == "FAILED" else "completed",
                "audit_outcome": "incomplete", "delivery": [],
                "evidence": {"outputs": [], "findings": [], "missing_inputs": [],
                             "operational_errors": [], "risk_gates": []},
                "detail_level": "legacy" if marker else "unstructured",
                "legacy_result": marker, "legacy_explanation": explanation}
        if not marker and job.get("require_outcome_marker"):
            errors.append("No valid structured result or legacy outcome marker was provided.")
    else:
        data = copy.deepcopy(data)
        # Admission evidence belongs to the engine, never the model's final block.
        data.pop("startup_failure", None)
        data["detail_level"] = "structured"
        data["legacy_result"] = marker
        if data["audit_outcome"] in ("clear", "not_applicable") and any(
                data["evidence"][k] for k in ("findings", "missing_inputs", "risk_gates")):
            data["declared_audit_outcome"] = data["audit_outcome"]
            data["audit_outcome"] = "incomplete"
            errors.append("The audit claim contradicts recorded findings, missing inputs or unresolved risk gates.")
    spec = job.get("result_contract") or {}
    if not isinstance(spec, dict):
        spec = {}
        errors.append("Invalid required result configuration.")
    allowed = (str(root), *roots)
    required = spec.get("required_outputs", [])
    destinations = spec.get("required_destinations", [])
    if (not isinstance(required, list) or any(not isinstance(x, str) for x in required)
            or not isinstance(destinations, list) or any(not isinstance(x, str) for x in destinations)):
        errors.append("Required outputs and destinations must be lists of strings.")
        required, destinations = [], []
    for value in required:
        found = next((x for x in data["evidence"]["outputs"] if x["path"] == value), None)
        if found:
            found["required"] = True
        else:
            data["evidence"]["outputs"].append({"path": value, "required": True})
    output_failure = False
    for item in data["evidence"]["outputs"]:
        try:
            path = _path(item["path"], allowed)
            stat = path.stat()
            if not path.is_file() or not stat.st_size:
                raise ValueError(f"Required report is empty or not a file: {path}")
            if item["required"] and stat.st_mtime < started - 1:
                raise ValueError(f"Required report was not produced by this run: {path}")
            item["validated"] = True
            item["bytes"] = stat.st_size
        except (OSError, ValueError, TypeError) as exc:
            item["validated"] = False
            reason = f"Report not produced/validated: {item['path']}: {exc}"
            errors.append(reason)
            output_failure |= item["required"]
    existing = {x["destination"] for x in data["delivery"]}
    for destination in destinations:
        if destination not in existing:
            data["delivery"].append({"destination": destination, "status": "unknown"})
    for delivery in data["delivery"]:
        if delivery["destination"] in destinations and delivery["status"] == "not_required":
            delivery["status"] = "unknown"
            delivery["error"] = "This destination is required by the job."
        if delivery["status"] != "sent":
            continue
        try:
            path = _path(delivery.get("receipt_path", ""), allowed)
            if path.stat().st_size > 65536:
                raise ValueError("Delivery receipt is too large.")
            receipt = json.loads(path.read_text(encoding="utf-8-sig"))
            if (type(receipt.get("schema_version")) is not int or receipt.get("schema_version") != VERSION or receipt.get("run_id") != run_id
                    or receipt.get("destination") != delivery["destination"] or receipt.get("status") != "sent"):
                raise ValueError("Receipt does not match this run and destination.")
            if receipt.get("job_id") and receipt["job_id"] != job.get("id"):
                raise ValueError("Receipt belongs to another job.")
            sent = dt.datetime.fromisoformat(receipt["sent_at"])
            if not sent.tzinfo or not started - 1 <= sent.timestamp() <= dt.datetime.now().timestamp() + 1:
                raise ValueError("Receipt timestamp is outside this run.")
            ids = receipt.get("message_ids")
            provider_id = receipt.get("receipt_id")
            if not (isinstance(ids, list) and ids and all(type(x) is int and x > 0 for x in ids)) and not (isinstance(provider_id, str) and provider_id.strip()):
                raise ValueError("Receipt has no provider delivery identifiers.")
            delivery["receipt"] = receipt  # snapshot: later overwrites cannot change historical proof
            delivery["validated"] = True
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            delivery.update(status="unknown", validated=False, error=f"Delivery unverified: {exc}")
            errors.append(delivery["error"])
    if output_failure:
        data["execution"] = "failed"
    # Preserve all approved check errors independently; a failed delivery does not
    # turn a successfully written report into a failed execution.
    from . import job_access
    for check in checks:
        reason = job_access.verify(root, job_access.Grant(checks=(check,)), started)
        if not reason:
            continue
        aspect, destination = check_aspect(check)
        errors.append(reason)
        if aspect == "delivery":
            entry = next((d for d in data["delivery"] if d["destination"] == destination), None)
            if entry is None:
                entry = {"destination": destination}
                data["delivery"].append(entry)
            entry.update(status="failed", error=reason)
        else:
            data["execution"] = "failed"
    if runtime_execution != "completed":
        data["execution"] = runtime_execution
    data["app_errors"] = ([runtime_error] if runtime_error else []) + errors
    data["validation_errors"] = errors
    data["evidence"]["delivery_receipts"] = [d["receipt"] for d in data["delivery"] if d.get("validated") and d.get("receipt")]
    if not marker and data["detail_level"] == "unstructured" and not job.get("require_outcome_marker") and not checks:
        # Old non-audit jobs have no audit claim; "not applicable" is not a pass.
        data["audit_outcome"] = "not_applicable"
    return data


def status(result: dict) -> str:
    if result["execution"] == "failed":
        return "error"
    if result["execution"] in ("stopped", "timed_out"):
        return "stopped" if result["execution"] == "stopped" else "error"
    if (result["audit_outcome"] in ("findings", "incomplete") or result.get("app_errors")
            or result["evidence"].get("risk_gates")
            or result["evidence"].get("operational_errors")
            or any(d["status"] in ("failed", "unknown") for d in result["delivery"])):
        return "warn"
    return "ok"


def label(result: dict) -> str:
    if result.get("startup_failure"):
        return "Not started — provider environment unavailable"
    parts = [result["execution"].replace("_", " ").capitalize()]
    if result["audit_outcome"] != "not_applicable":
        parts.append("audit " + result["audit_outcome"])
    if result['execution'] == 'completed' and result.get('evidence', {}).get('operational_errors'):
        parts.append('operational warnings')
    if result["execution"] == "failed" and any("Report not produced/validated:" in x for x in result.get("app_errors", [])):
        parts = ["Failed", "report not produced"]
    deliveries = [d["status"] for d in result["delivery"] if d["status"] != "not_required"]
    if "failed" in deliveries:
        parts.append("delivery failed")
    elif "unknown" in deliveries:
        parts.append("delivery unverified")
    elif deliveries:
        parts.append("delivered")
    return " — ".join(parts)


def reason(result):
    """Operational failure precedes secondary contract-validation diagnostics."""
    if result.get("startup_failure"):
        return result["startup_failure"]["reason"]
    if result.get('execution') in ('failed', 'timed_out', 'stopped'):
        errors = result.get('evidence', {}).get('operational_errors', [])
        if errors:
            return errors[0]
    errors = result.get('app_errors', [])
    if errors:
        return errors[0]
    operational = result.get('evidence', {}).get('operational_errors', [])
    if operational:
        return operational[0]
    return result.get('legacy_explanation', '')[-500:] if result.get('legacy_result') == 'FAILED' else ''
