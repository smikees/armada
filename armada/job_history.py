"""Job transcripts live separately from owner conversations; old logs stay intact."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .util import safe_seg

JOB_PREFIX = "job-run--"


def save_transcript(agent_dir, run_id: str, content: dict) -> str:
    """Keep large transcripts out of the small accounting log used by every dashboard."""
    from .util import write_json_atomic
    name = safe_seg(run_id, "run") + ".json"
    write_json_atomic(Path(agent_dir) / "runs" / "output" / name, content)
    return name


def thread_name(job_id: str) -> str:
    return JOB_PREFIX + safe_seg(job_id, "job")


def reports(agent_dir, job_id: str | None = None) -> list[dict]:
    ad = Path(agent_dir)
    path = ad / "runs" / f"{ad.name}.jsonl"
    result = []
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except FileNotFoundError:
        return result
    for line in lines:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if isinstance(ev, dict) and (job_id is None or ev.get("task") == job_id):
            result.append(apply_annotation(ad, ev))
    return result


def apply_annotation(agent_dir, event: dict) -> dict:
    """Overlay a correction in views; the original accounting/transcript stays immutable."""
    run_id = event.get("run_id")
    if not run_id:
        return event
    try:
        name = safe_seg(str(run_id), "run") + ".json"
        path = Path(agent_dir) / "runs" / "annotations" / name
        if not path.exists():
            return event
        annotation = json.loads(path.read_text(encoding="utf-8"))
        result = annotation["result"]
        if (annotation.get("schema_version") != 1 or annotation.get("run_id") != run_id
                or result.get("run_id") != run_id or result.get("schema_version") != 1):
            return event
        from . import job_results
        return {**event, "original_status": event.get("status"),
                "original_summary": event.get("summary"), "annotation": annotation,
                "result": result, "status": job_results.status(result), "summary": job_results.label(result)}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return event


def annotate(agent_dir, run_id: str, result: dict, reason: str, *, supporting_evidence: dict) -> Path:
    """Add a dated correction to an existing run, never editing its original report."""
    from . import job_results, util
    import datetime
    # Validate the shape; historical evidence is explicitly correlated by the caller
    # rather than pretending an old receipt satisfies the new per-run contract.
    job_results._parse("<armada_job_result>" + json.dumps(result) + "</armada_job_result>", run_id)
    matches = [ev for ev in reports(agent_dir) if ev.get("run_id") == run_id]
    if len(matches) != 1 or not reason or not supporting_evidence:
        raise ValueError("An annotation needs one existing run, a reason and supporting evidence.")
    path = Path(agent_dir) / "runs" / "annotations" / (safe_seg(run_id, "run") + ".json")
    with util.file_lock(path):
        if path.exists():
            raise ValueError("This run already has an annotation; preserve its history.")
        util.write_json_atomic(path, {"schema_version": 1, "run_id": run_id,
            "annotated_at": datetime.datetime.now().astimezone().isoformat(),
            "reason": reason, "result": result, "supporting_evidence": supporting_evidence})
    return path


def legacy_turns(agent_dir, thread: str, messages: list[dict]) -> set[int]:
    """Match completed old job turns by report timestamp; never rewrite the chat log.

    Retain original indexes for edit/restart actions. Ambiguous matches are left alone.
    """
    ad = Path(agent_dir)
    path = ad / "runs" / f"{ad.name}.jsonl"
    try:
        stat = path.stat()
    except FileNotFoundError:
        return set()
    hidden = set()
    for ev in _legacy_reports(str(ad), stat.st_mtime_ns, stat.st_size):
        if (ev.get("thread") or "main") != thread or not ev.get("ts"):
            continue
        matches = [i for i, m in enumerate(messages) if m.get("role") == "assistant"
                   and m.get("ts") == ev.get("ts")]
        if len(matches) != 1:
            continue
        i = matches[0]
        hidden.add(i)
        turn = messages[i].get("turn")
        if turn:
            hidden.update(n for n, m in enumerate(messages) if m.get("turn") == turn)
        elif i and messages[i - 1].get("role") == "user" and messages[i - 1].get("ts") == ev.get("ts"):
            hidden.add(i - 1)
    return hidden


@lru_cache(maxsize=64)
def _legacy_reports(agent_dir, mtime, size):
    return tuple({k: ev.get(k) for k in ("thread", "ts")} for ev in reports(agent_dir)
                 if ev.get("kind") == "job" and not str(ev.get("thread", "main")).startswith(JOB_PREFIX)
                 and not str(ev.get("task", "")).startswith("inbox:") and ev.get("task") != "adhoc")


def transcript(agent_dir, ev: dict) -> dict:
    """Read a durable run snapshot, falling back to its original thread for old runs."""
    if ev.get("output_file"):
        name = safe_seg(str(ev["output_file"]).removesuffix(".json"), "output") + ".json"
        try:
            data = json.loads((Path(agent_dir) / "runs" / "output" / name).read_text(encoding="utf-8"))
            if isinstance(data, dict):
                # Old coordinator code appended the app error to the agent's final
                # answer. A correction separates that exact suffix in the view only.
                why = ev.get("original_summary") if ev.get("annotation") else None
                if why and str(data.get("content") or "").endswith("\n\n" + why):
                    data = {**data, "content": data["content"][:-(len(why) + 2)],
                            "app_errors": [why], "raw_final_answer": data["content"]}
                return data
        except (OSError, ValueError):
            pass
    if "output" in ev:
        return {"content": ev["output"], "events": ev.get("activity", []),
                "outputs": ev.get("outputs", []), "tool_results": ev.get("tool_results", [])}
    from .threads import Thread
    try:
        thread = safe_seg(ev.get("thread") or "main", "thread")
    except ValueError:
        return {"content": ev.get("summary") or "Full output is unavailable for this older run."}
    messages = Thread(agent_dir, thread)._messages()
    matches = [m for m in messages if m.get("role") == "assistant"
               and m.get("ts") == ev.get("ts")]
    return matches[0] if len(matches) == 1 else {
        "content": ev.get("summary") or "Full output is unavailable for this older run."}
