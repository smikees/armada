"""Temporary draft jobs, with separate history, explicit models and owned cancellation."""
from __future__ import annotations

import copy
import contextlib
import datetime as dt
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import threading
import time
import uuid

from . import inspection, util

log = logging.getLogger(__name__)
KEEP_DAYS = 7
_LOCK = threading.RLock()
_ACTIVE = {}


def base(root):
    return inspection.checked_path(Path(root).resolve() / ".armada" / "dry-runs", [Path(root).resolve()])


def directory(root, agent, job, run_id):
    return inspection.checked_path(base(root) / util.safe_seg(agent, "agent") /
        util.safe_seg(job, "job") / util.safe_seg(run_id, "run"), [Path(root).resolve()])


def settings(job):
    if "inspector" in job and type(job["inspector"]) is not bool:
        raise ValueError("Inspector job must be true or false.")
    if job.get("inspector") and is_command(job):
        raise ValueError("Inspector jobs must be agent jobs, without a command.")
    days = job.get("dry_run_keep_days", KEEP_DAYS)
    if type(days) is not int or not 1 <= days <= 365:
        raise ValueError("Dry-run retention must be between 1 and 365 days.")
    command = job.get("dry_run_command") or ""
    if not isinstance(command, (str, list)) or (isinstance(command, list) and
            (not command or any(not isinstance(x, str) or not x for x in command))):
        raise ValueError("Dry-run command must be text or a non-empty argument list.")
    return days


def models(root):
    from . import models as catalog
    return [{"id": mid, "label": label} for mid, label in catalog.options(root)
            if not mid.endswith(":default")]


def is_command(job):
    return job.get("kind") == "command" or bool(job.get("run") or job.get("command"))


def _save_info(folder, info):
    path = Path(folder) / "run.json"
    with util.file_lock(path, validate_state=False):
        saved = copy.deepcopy(info)
        for key in list(saved):
            if key.startswith('_'):
                saved.pop(key)
        if info.get('pair_id'):
            for key in ('model', 'actual_model', 'effort_override', 'effective_effort', 'tokens', 'capture', 'result', 'error'):
                saved.pop(key, None)
            saved['model'] = 'Blind candidate ' + info['pair_label']
            if info.get('error'):
                saved['error'] = 'Candidate failed. Record scores to review its private diagnostics.'
        util.write_json_atomic(path, saved)


def _read_info(root, path):
    # Windows can transiently deny an open around replacement or antivirus scanning.
    path = inspection.checked_path(path, [Path(root).resolve()])
    with util.file_lock(path, validate_state=False):
        for attempt in range(8):
            try:
                return util.read_json_state(inspection.checked_path(path, [Path(root).resolve()], must_exist=True))
            except (util.StateError, PermissionError) as exc:
                cause = exc.__cause__ if isinstance(exc, util.StateError) else exc
                if not isinstance(cause, PermissionError) or attempt == 7:
                    raise
                time.sleep(.03)


def start(root, agent, job_id, model="", *, requested_by="user", engine=None, effort=None,
          _admitted=False, _frozen=None, _job=None, _pair=None, _context=None):
    """Capture configuration before dispatch. No production invocation or job marker is used."""
    from . import realmops, updater
    root = Path(root).resolve()
    agent, job_id = util.safe_seg(agent, "agent"), util.safe_seg(job_id, "job")
    if not isinstance(model, str):
        raise ValueError("Choose a model ID from the available model list.")
    if effort is not None:
        from .runner import _EFFORT_LEVELS
        if not isinstance(effort, str) or effort not in (*_EFFORT_LEVELS, "auto"):
            raise ValueError("Choose a supported effort or auto.")
    # RunSession owns the process-shared update/lifecycle locks; never acquire them twice.
    with _LOCK, (contextlib.nullcontext() if _admitted else util.file_lock(base(root) / "admission", validate_state=False)):
        realmops.assert_active(root)
        if updater.installed() and updater.admission_paused():
            raise ValueError("ARMADA is restarting to update. Try after it reopens.")
        live = [p for p in base(root).glob("*/*/*/run.json") if
                (lambda r: r.get("status") in ("queued", "running") and util.pid_alive(r.get("owner_pid", 0)))(_read_info(root, p))]
        if len(live) >= 2:
            raise ValueError("Two dry runs are already active in this realm. Stop one or wait for it to finish.")
        ad = root / "agents" / agent
        inspection.checked_path(ad / "agent.json", [root], must_exist=True)
        jp = inspection.checked_path(ad / "jobs" / (job_id + ".json"), [root], must_exist=True)
        with util.file_lock(jp):
            job = copy.deepcopy(_job) if _job is not None else util.read_json_state(jp)
            job.setdefault("id", job_id)
            days = settings(job)
            if is_command(job):
                if not job.get("dry_run_command") or not inspection.command_approved(root, agent, job):
                    raise ValueError("Save an explicit draft-only dry-run command in Job settings first.")
                if model:
                    raise ValueError("Command jobs use the saved dry-run command, not a model.")
                if effort is not None:
                    raise ValueError("Command jobs do not use reasoning effort.")
            elif engine is None and model not in {row["id"] for row in models(root)}:
                raise ValueError("Select an available model for this dry run.")
        if requested_by != "user" and not inspection.enabled(root, requested_by):
            raise ValueError("Inspector access is not enabled for this agent on this machine.")
        run_id = uuid.uuid4().hex
        folder = directory(root, agent, job_id, run_id)
        (folder / "output").mkdir(parents=True, exist_ok=False)
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        info = {"schema_version": 1, "run_id": run_id, "agent": agent, "job": job_id,
                "name": job.get("name") or job_id, "mode": "dry_run", "status": "queued",
                "model": model, "requested_by": requested_by, "started": now,
                "effort_override": effort,
                "owner_pid": os.getpid(),
                "keep_days": days, "output_dir": str(folder / "output"),
                "limitations": "Saved file inputs only; live connectors, shell and publication tools are disabled."
                    if not is_command(job) else "Runs the owner-approved dry-run command; the script must honor its draft-only contract."}
        try:
            if _pair:
                info.update(pair_id=_pair[0], pair_label=_pair[1])
            if _frozen:
                info['_snapshot'] = str(_frozen)
            elif job.get('dry_run_scripts'):
                from .draft_inputs import freeze
                freeze(root, agent, job, folder / 'inputs')
                info['_snapshot'] = str(folder / 'inputs')
            from .draft_skills import stage
            script_grant = stage(root, agent, job, folder)
            # Context and job definition are captured at dispatch, never reread between candidates.
            from . import memory
            info['_agent'] = copy.deepcopy(_context[0]) if _context else util.read_json_state(ad / 'agent.json')
            info['_core'] = _context[1] if _context else memory.assemble_core(root, ad, info['_agent'])
            info['_script_grant'] = script_grant
            util.write_json_atomic(folder / "job.json", job)
            _save_info(folder, info)
        except BaseException:
            for candidate in folder.rglob('*'):
                inspection.checked_path(candidate, [folder], must_exist=True)
            shutil.rmtree(folder)
            raise
        from .execution import RunSession
        from .request_context import RunContext
        session = RunSession(RunContext.capture(root, agent, "dryrun-" + run_id, run_id=run_id))
        key = (str(root), run_id)
        try:
            session.__enter__()
            _ACTIVE[key] = session
            worker = threading.Thread(target=_execute, args=(root, folder, job, info, session, engine), daemon=True,
                                      name="armada-dry-run-" + run_id[:8])
            worker.start()
        except BaseException:
            _ACTIVE.pop(key, None)
            session.close()
            info.update(status="failed", finished=now, error="Could not start the dry run.")
            _save_info(folder, info)
            raise
        return _read_info(root, folder / 'run.json')


def _execute(root, folder, job, info, session, engine):
    from . import job_results, memory, runner, workspace
    from .engine import get_engine
    from .engine.contracts import RunRequest, execute_request
    from .engine.selection import model_provider
    from .engine.base import RunResult
    events, result = [], RunResult(ok=False, error="Dry run did not finish.")
    t0 = time.time()
    capture = None
    closed = threading.Event()
    def watch_stop():
        from .execution import RunSession
        while not closed.wait(.2):
            if (folder / "stop.json").exists():
                try:
                    RunSession.cancel(session.context.key)
                except Exception:
                    log.exception("Could not stop dry-run process")
    watcher = threading.Thread(target=watch_stop, daemon=True)
    watcher.start()
    try:
        info["status"] = "running"
        _save_info(folder, info)
        if session.active.cancelled:
            result = RunResult(ok=False, cancelled=True, error="Dry run stopped.")
        elif is_command(job):
            if job.get("capture_tools"):
                from .tool_capture import ToolCapture
                capture_job = {**job, "capture_dir": str(folder.relative_to(root) / "raw")}
                capture = ToolCapture(root, capture_job, info["job"], info["run_id"], "command", False,
                                      info["agent"], workspace_root=root, index_root=folder)
            result = _command(root, folder, job, info, session)
            if capture is not None:
                info["result"] = job_results.evaluate(result.output, run_id=info["run_id"],
                    job={"result_contract": {}, "require_outcome_marker": False}, root=root, started=t0,
                    runtime_execution="stopped" if result.cancelled else "timed_out" if result.timed_out else
                        "completed" if result.ok else "failed", runtime_error=result.error,
                    roots=(str(folder / "output"),), checks=[])
        else:
            from .managed_tools import ManagedTools
            eng = engine or get_engine(model_provider(info["model"]))
            agent = info['_agent']
            chosen = {**agent, "model": info["model"]}
            # A test uses precisely the selected model, with no production fallback or retry.
            core = info['_core']
            if info.get('pair_id'):
                core += ('\nThis is a blind A/B model comparison. Never name your model, provider or reasoning effort '
                         'in drafts, final answers, script arguments or artifact metadata.')
            core += ("\n\nDRY RUN: produce draft artifacts only. Production instructions to publish, send, "
                     "or edit existing files are replaced by creating drafts in ARMADA_DRY_RUN_DIR. "
                     "Use the ARMADA managed tools to read existing inputs and write drafts. "
                     "Read saved raw connector results if present; do not invent fresh connector reads. "
                     "Shell and live connectors are unavailable. Explain missing inputs or skipped steps. "
                     "No production deliveries or receipts are required. Do not change the saved job/model.\n"
                     f"Draft output folder: {folder / 'output'}\nRun ID: {info['run_id']}")
            test_job = copy.deepcopy(job)
            test_job["result_contract"] = {"required_outputs": [], "required_destinations": []}
            prompt = workspace.expand(job.get("prompt", ""), root)
            prompt = prompt.replace("{dry_run_dir}", str(folder / "output"))
            prompt += job_results.instructions(info["run_id"], test_job)
            env = {"ARMADA_DRY_RUN": "1", "ARMADA_DRY_RUN_DIR": str(folder / "output"),
                   "ARMADA_RUN_ID": info["run_id"]}
            snapshot = Path(info['_snapshot']) if info.get('_snapshot') else None
            if snapshot:
                core += ('\nInputs are frozen. read_input accepts original approved paths and reads their frozen copies. '
                         'Approved scripts use ARMADA_INPUT_DIR and ARMADA_INPUT_MANIFEST for staged paths.')
            with ManagedTools(root, info["agent"], output=folder / "output", job=job, snapshot=snapshot,
                    script_grant=info.get('_script_grant'), cancelled=lambda: session.active.cancelled) as tools:
                eng = tools.configure(eng)
                if job.get("capture_tools"):
                    from .tool_capture import ToolCapture
                    # Capture lives in this temporary tree, never in the production capture directory.
                    capture_job = {**job, "capture_dir": str(folder.relative_to(root) / "raw")}
                    capture = ToolCapture(root, capture_job, info["job"], info["run_id"], eng.name,
                                          getattr(eng.capabilities, "raw_tool_results", False), info["agent"],
                                          workspace_root=root, index_root=folder)
                    if capture.directory is not None:
                        env["ARMADA_RAW_DIR"] = str(capture.directory)
                        prompt = prompt.replace("{raw_dir}", str(capture.directory))
                from . import verbosity
                level = verbosity.normalise(job.get("verbosity")) or verbosity.agent_level(root, info["agent"])
                request = RunRequest(core, prompt, model=runner._engine_model(eng, info["model"]) or None,
                    cwd=str(folder / "output"), allow_tools=True, timeout=runner._resolve_timeout(root, job) or 600,
                    effort=(None if info.get("effort_override") == "auto" else info["effort_override"])
                        if info.get("effort_override") is not None else
                        runner._resolve_effort(root, {**chosen, **({"effort": job["effort"]} if job.get("effort") else {})}) or None,
                    max_budget_usd=runner._resolve_max_budget(root, chosen), verbosity=level, env=env)
                info['effective_effort'] = request.effort or 'auto'
                def event(ev):
                    if capture is not None:
                        capture.on_event(ev)
                    if len(events) < 1000:
                        events.append(ev)
                result = execute_request(eng, request, on_event=event, on_proc=session.bind)
            info["result"] = job_results.evaluate(result.output, run_id=info["run_id"], job=test_job,
                root=root, started=t0, runtime_execution="stopped" if result.cancelled else
                    "timed_out" if result.timed_out else "completed" if result.ok else "failed",
                runtime_error=result.error, roots=(str(folder / "output"),), checks=[])
    except Exception as exc:
        log.exception("Dry run failed")
        result = RunResult(ok=False, error=str(exc))
    finally:
        try:
            if capture is not None:
                capture.finish()
                if info.get("result"):
                    capture.audit(info["result"])
                info["capture"] = capture.report()
            info.update(status="stopped" if result.cancelled or session.active.cancelled else
                "timed_out" if result.timed_out else "completed" if result.ok else "failed",
                finished=dt.datetime.now(dt.timezone.utc).isoformat(), duration_s=round(time.time()-t0, 2),
                error=result.error, actual_model=result.model, tokens=result.usage.as_dict())
            if info.get("result") and info["status"] == "completed":
                outcome = job_results.status(info["result"])
                if outcome == "error":
                    info["status"] = "failed"
                elif outcome == "warn":
                    info["status"] = "warning"
            text = job_results.original_answer(result.output)
            util.write_text_atomic(folder / "output" / "final-answer.md", text + "\n")
            transcript = {"content": text, "raw_final_answer": result.output, "events": events, "error": result.error}
            if info.get('pair_id'):
                from . import dry_run_pairs
                dry_run_pairs.private_result(root, info, transcript)
                dry_run_pairs.anonymize_outputs(root, info, folder / 'output')
                info['blind_ready'] = True
                transcript = {'content': dry_run_pairs.anonymize(root, info, text)}
                info['files'] = output_files(folder)
            util.write_json_atomic(folder / "transcript.json", transcript)
            info["files"] = output_files(folder)
            _save_info(folder, info)
            runner._write_report(root / "agents" / info["agent"], info["agent"], {
                "ts": info["finished"], "agent": info["agent"], "task": "dryrun:" + info["job"],
                "kind": "dry_run", "run_id": info["run_id"], "model": ('Blind candidate ' + info['pair_label']) if info.get('pair_id') else result.model or info["model"],
                "tokens": result.usage.as_dict(), "status": {"completed": "ok", "warning": "warn",
                    "failed": "error", "timed_out": "error"}.get(info["status"], info["status"]),
                "summary": "Dry run Â· " + info["name"]})
        except Exception:
            log.exception("Could not persist dry-run result")
            try:
                info.update(status="failed", error="Could not save the dry-run output. Check ARMADA logs and retry.",
                            finished=dt.datetime.now(dt.timezone.utc).isoformat())
                _save_info(folder, info)
            except Exception:
                log.exception("Could not save dry-run persistence failure")
        finally:
            closed.set()
            watcher.join(timeout=1)
            session.close()
            with _LOCK:
                _ACTIVE.pop((str(root), info["run_id"]), None)


def _command(root, folder, job, info, session):
    """Only the user's explicit, fingerprinted draft command may execute."""
    import shlex
    from .engine.base import RunResult
    from .engine.process import supervise_command
    command = job["dry_run_command"]
    command = list(command) if isinstance(command, list) else shlex.split(command, posix=os.name != "nt")
    if os.name == "nt":
        command = [arg[1:-1] if len(arg) > 1 and arg[0] == arg[-1] == '"' else arg for arg in command]
    replacements = {"{workspace}": str(root), "{dry_run_dir}": str(folder / "output"), "{run}": info["run_id"]}
    # Workspace means the actual configured read-input workspace, not a clone.
    from . import workspace
    replacements["{workspace}"] = workspace.root(root) or str(root)
    for index, arg in enumerate(command):
        for token, value in replacements.items():
            arg = arg.replace(token, value)
        command[index] = arg
    env = {**os.environ, **{str(k): str(v) for k, v in (job.get("env") or {}).items()},
           "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "ARMADA_DRY_RUN": "1",
           "ARMADA_DRY_RUN_DIR": str(folder / "output"), "ARMADA_RUN_ID": info["run_id"]}
    child = supervise_command(command, cwd=str(folder / "output"), timeout=int(job.get("timeout", 300)),
                              env=env, on_proc=session.bind)
    error = child.error or (child.stderr if child.returncode else "")
    return RunResult(ok=child.returncode == 0 and not error, output=child.stdout, error=error,
                     cancelled=child.cancelled, timed_out=child.timed_out)


def output_files(folder):
    out, root = [], Path(folder) / "output"
    for candidate in sorted(root.rglob("*")):
        path = inspection.checked_path(candidate, [root], must_exist=True)
        if path.is_file():
            with path.open("rb") as handle:
                digest = hashlib.file_digest(handle, "sha256").hexdigest()
            out.append({"path": str(path), "name": str(path.relative_to(root)), "bytes": path.stat().st_size,
                        "sha256": digest})
    return out


def listing(root, agent, job):
    parent = directory(root, agent, job, "placeholder").parent
    runs = []
    for p in parent.glob("*/run.json"):
        try:
            runs.append(read(root, agent, job, p.parent.name))
        except (OSError, ValueError):
            continue
    return sorted(runs, key=lambda r: r["started"], reverse=True)[:30]


def read(root, agent, job, run_id):
    folder = directory(root, agent, job, run_id)
    info = _read_info(root, folder / "run.json")
    if (info.get("agent"), info.get("job"), info.get("run_id")) != (agent, job, run_id):
        raise ValueError("Dry-run identity does not match this job.")
    with _LOCK:
        active = _ACTIVE.get((str(Path(root).resolve()), run_id))
    from .request_context import RunContext
    marker = RunContext.capture(root, agent, "dryrun-" + run_id, run_id=run_id).marker
    owned = util.read_json_state(marker, default=dict) if marker.exists() else {}
    live = owned.get("run_id") == run_id and owned.get("owner_pid") == info.get("owner_pid") and util.pid_alive(info.get("owner_pid", 0))
    if info["status"] in ("queued", "running") and not active and not live:
        info.update(status="interrupted", error="ARMADA closed before this dry run finished.")
    return info


def stop(root, agent, job, run_id):
    info = read(root, agent, job, run_id)
    if info["status"] not in ("queued", "running"):
        return {"ok": True, "note": "Dry run already finished."}
    util.write_json_atomic(directory(root, agent, job, run_id) / "stop.json", {"requested": dt.datetime.now(dt.timezone.utc).isoformat()})
    with _LOCK:
        session = _ACTIVE.get((str(Path(root).resolve()), run_id))
        if session is None:
            return {"ok": True, "note": "Stop requested."}
        from .execution import RunSession
        return RunSession.cancel(session.context.key)


def prune(root, *, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    removed, errors = 0, []
    for metadata in base(root).glob("*/*/*/run.json"):
        try:
            folder = inspection.checked_path(metadata.parent, [Path(root).resolve()], must_exist=True)
            info = read(root, folder.parent.parent.name, folder.parent.name, folder.name)
            if info.get('pair_id'):
                continue  # Pair retention owns both candidates and their shared snapshot.
            if info["status"] in ("queued", "running"):
                continue
            finished = dt.datetime.fromisoformat(info.get("finished") or info["started"])
            if finished.tzinfo is None:
                finished = finished.replace(tzinfo=dt.timezone.utc)
            if now - finished < dt.timedelta(days=info.get("keep_days", KEEP_DAYS)):
                continue
            # Validate the whole tree before recursive removal; never follow a reparse point.
            for p in folder.rglob("*"):
                inspection.checked_path(p, [folder], must_exist=True)
            shutil.rmtree(folder)
            removed += 1
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
    from .dry_run_pairs import prune as prune_pairs
    pairs = prune_pairs(root, now=now)
    return {"removed": removed + pairs['removed'], "errors": errors + pairs['errors']}
