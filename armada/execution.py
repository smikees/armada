"""Own agent turns across HTTP, plain chat, jobs, inbox and Telegram.

Runner functions remain compatibility entry points and context-building helpers. This module
owns admission, activity, progress, terminal history, accounting and cleanup. Transports only
observe events; a disconnected observer cannot abandon the conversation.
"""
from dataclasses import dataclass, replace
import datetime
import logging
import os
from pathlib import Path
import re
import threading
import time

from . import util, memory, workspace, thread_metadata, verbosity
from .engine.base import RunResult, Usage
from .engine.contracts import RunRequest, ProviderCapabilities, execute_request, validate_request
from .engine.process import safe_emit
from .request_context import RunContext, ActiveRun


class _LiveTextRenderer:
    """Throttle Markdown rendering without leaving the last delta waiting for another event."""
    def __init__(self, sink, interval=.1, checkpoint=None):
        self.sink, self.interval = sink, interval
        self.checkpoint = checkpoint
        self.text = self.rendered = ''
        self.last = 0.0
        self.timer = None
        self.closed = False
        self.lock = threading.RLock()

    def _paint(self):
        if self.text == self.rendered:
            return
        if self.checkpoint:
            self.checkpoint(self.text)
        from .webui._base import _md
        safe_emit(self.sink, {'kind':'render','html':_md(self.text)})
        self.rendered, self.last = self.text, time.monotonic()

    def update(self, text):
        if not self.sink and not self.checkpoint:
            return
        with self.lock:
            if self.closed:
                return
            self.text = text
            delay = self.interval - (time.monotonic() - self.last)
            if delay <= 0:
                self._paint()
            elif self.timer is None:
                self.timer = threading.Timer(delay, self._tick)
                self.timer.daemon = True
                self.timer.start()

    def _tick(self):
        with self.lock:
            self.timer = None
            if not self.closed:
                self._paint()

    def flush(self):
        with self.lock:
            if self.timer:
                self.timer.cancel()
                self.timer = None
            if not self.closed:
                self._paint()

    def close(self):
        with self.lock:
            self.flush()
            self.closed = True
from .threads import Thread

log = logging.getLogger(__name__)
ACTIVE_RUNS = {}
RUNS_LOCK = threading.RLock()


def _report_summary(output: str) -> str:
    """Keep the deliverable in run history without showing its machine status marker."""
    lines = (output or "").strip().splitlines()
    if lines and re.fullmatch(r"ARMADA_JOB_RESULT:\s*(?:SUCCESS|FAILED)", lines[-1].strip(), re.I):
        lines.pop()
    return "\n".join(lines).strip().split("\n\n")[-1][:200]


class RunSession:
    """Exclusive in-process admission and owned activity marker, including early cancellation."""
    def __init__(self, context, registry=None, lock=None):
        self.context = context
        self.registry = ACTIVE_RUNS if registry is None else registry
        self.lock = RUNS_LOCK if lock is None else lock
        self.active = ActiveRun(context)
        self.started = False

    def __enter__(self):
        from . import realmops, updater
        with updater.admission_lock(), self.lock, realmops.lifecycle_lock(self.context.realm.root):
            if updater.installed() and updater.admission_paused():
                raise util.StateError("ARMADA is restarting to update. New tasks can start after it reopens.")
            realmops.assert_active(self.context.realm.root)
            if self.context.key in self.registry:
                raise util.StateError("This run ID is already active in this realm.")
            mark = self.context.marker
            with util.file_lock(mark):
                util.write_json_atomic(mark, {"kind": "chat", "owner_pid": os.getpid(),
                    "thread": self.context.thread, "run_id": self.context.run_id,
                    "realm_id": self.context.realm.realm_id})
            self.registry[self.context.key] = self.active
            self.started = True
        return self

    def bind(self, process):
        with self.lock:
            self.active.process = process
            if self.active.cancelled:
                process.kill()

    @staticmethod
    def cancel(key, registry=None, lock=None):
        registry = ACTIVE_RUNS if registry is None else registry
        with RUNS_LOCK if lock is None else lock:
            active = registry.get(key)
            if active is None:
                return {"ok": True, "note": "no active turn"}
            active.cancelled = True
            if active.process is not None:
                try:
                    active.process.kill()
                except Exception:
                    # A rejected kill is not a successful cancellation. Let both
                    # views retry Stop instead of remaining stuck on Stopping.
                    active.cancelled = False
                    raise
        return {"ok": True}

    def close(self):
        with self.lock:
            if not self.started or self.registry.get(self.context.key) is not self.active:
                return
            mark = self.context.marker
            try:
                mark.unlink(missing_ok=True)
            except OSError:
                log.exception("Could not remove run activity marker")
                try:
                    with util.file_lock(mark):
                        util.write_json_atomic(mark, {"kind": "chat", "status": "finished",
                            "thread": self.context.thread, "run_id": self.context.run_id,
                            "realm_id": self.context.realm.realm_id})
                except Exception:
                    log.exception("Could not mark run activity terminal")
            finally:
                self.registry.pop(self.context.key)
                self.started = False

    def __exit__(self, *args):
        self.close()


@dataclass(frozen=True)
class TurnRequest:
    context: RunContext
    message: str
    engine: object = "auto"
    allow_tools: bool = False
    task: str | None = None
    job: dict | None = None
    images: tuple = ()
    files: tuple = ()


class TurnCoordinator:
    def __init__(self, request: TurnRequest, *, on_event=None, on_proc=None, session=None):
        self.request, self.on_event, self.on_proc = request, on_event, on_proc
        self.session = session or RunSession(request.context)
        if self.session.context != request.context:
            raise ValueError("Run session context does not match the turn.")

    def run(self):
        from . import runner as r
        req, context = self.request, self.request.context
        root, aid, thread = Path(context.realm.root), context.agent, context.thread
        agent_dir = root / "agents" / aid
        th = Thread(agent_dir, thread)
        turn = cap = eng = raw_capture = None
        partial = []
        activity_events = []
        last_checkpoint = 0.0
        current_activity = 'Thinking…'
        def checkpoint(text):
            if turn:
                th.save_progress(turn, text, current_activity, activity_events)
        live_text = _LiveTextRenderer(self.on_event, checkpoint=checkpoint)
        compacted = False
        started = time.monotonic()
        attachments = []
        message = req.message
        result = RunResult(ok=False, error="Turn did not finish.")
        job_result = None
        execution_started = time.time()
        from .job_history import JOB_PREFIX
        scheduled_job = bool(req.task) and thread.startswith(JOB_PREFIX)
        grant = None
        result_job, result_checks = req.job or {}, []
        if not self.session.started:
            self.session.__enter__()

        def _event(ev):
            nonlocal last_checkpoint, current_activity
            if raw_capture is not None:
                raw_capture.on_event(ev)
            # Raw payloads stay in the job transcript, never the UI event stream or prompt history.
            ev = {k: v for k, v in ev.items() if k != "raw_result"}
            if cap is not None:
                cap.on_event(ev)
            kind = ev.get("kind")
            if kind == "text" and ev.get("text"):
                partial.append(ev["text"])
            elif kind in ("thinking", "tool"):
                activity_events.append({k: ev[k] for k in ("kind", "text", "name", "input", "id") if k in ev})
                del activity_events[:-80]
            elif kind == "tool_result":
                for item in reversed(activity_events):
                    if item.get("kind") == "tool" and item.get("id") == ev.get("id"):
                        item["result"] = str(ev.get("content") or "")[:4000]
                        item["is_error"] = bool(ev.get("is_error"))
                        break
            activity = ("Continuing…" if kind == "text" else
                        {"Bash": "Running a command…", "WebSearch": "Searching the web…",
                         "Edit": "Updating a file…", "Read": "Reading a file…"}.get(ev.get("name"), "Using a tool…")
                        if kind == "tool" else "Thinking…")
            now = time.monotonic()
            current_activity = activity
            if turn and kind in ("text", "tool", "thinking", "tool_result") and (kind != "text" or now - last_checkpoint >= .15):
                th.save_progress(turn, "".join(partial), activity, activity_events)
                last_checkpoint = now
            safe_emit(self.on_event, {**ev, "activity": activity})
            if kind == "text":
                live_text.update("".join(partial))
            else:
                live_text.flush()

        def event(ev):
            # Keep timed paints and persisted activity snapshots in the same event order.
            with live_text.lock:
                _event(ev)

        def process(handle):
            self.session.bind(handle)
            if self.on_proc and self.on_proc != self.session.bind:
                self.on_proc(handle)

        try:
            try:
                eng, agent = r._prepare_agent_run(root, aid, req.engine, req.allow_tools or bool(req.images), req.job)
                if not agent:
                    raise ValueError(f"no agent '{aid}'")
                job = req.job or {}
                if req.task and job.get("capture_tools"):
                    from .tool_capture import ToolCapture
                    raw_capture = ToolCapture(root, job, req.task, context.run_id, eng.name,
                        getattr(eng, "capabilities", ProviderCapabilities()).raw_tool_results, aid)
                if scheduled_job:
                    from . import job_access, job_results
                    grant = job_access.grant_for(root, aid, req.job) if req.job else job_access.Grant()
                    result_checks = job_access.expanded_checks(root, grant.checks)
                    result_job = job_results.requirements(job, result_checks)
                run_agent = {**agent, **{k: job[k] for k in ("effort", "verbosity") if job.get(k)}}
                output_level = verbosity.normalise(run_agent.get("verbosity")) or verbosity.realm_level(root)
                use_tools = req.allow_tools or bool(agent.get("allow_tools")) or bool(req.images)
                model = r._cli_model(job["model"], root) if job.get("model") else r._resolve_model(root, agent)
                request = RunRequest("", "", model=r._engine_model(eng, model) or None,
                    cwd=str(agent_dir), allow_tools=use_tools, effort=r._resolve_effort(root, run_agent),
                    verbosity=output_level if eng.name in ("codex", "gemini") else None,
                    timeout=(r._resolve_timeout(root, job) or r._DEFAULT_RUN_TIMEOUT),
                    fallback_model=r._resolve_fallback_model(root, agent) or None,
                    max_budget_usd=r._resolve_max_budget(root, agent),
                    disallowed_tools=tuple(r._tool_grants(root, aid, eng, use_tools)))
                validate_request(eng.name, getattr(eng, "capabilities", ProviderCapabilities()), request)
                if req.task:
                    message = workspace.expand(req.message, root)
                if raw_capture is not None:
                    raw_dir = str(raw_capture.directory or "")
                    message = message.replace("{raw_dir}", raw_dir)
                    if raw_dir:
                        request = replace(request, env={"ARMADA_RAW_DIR": raw_dir})
                        message += ("\n\nARMADA saves matching tool results during this run in " + raw_dir
                            + ". Read manifest.jsonl for file names and filter entries by run_id "
                            + context.run_id + ". Scripts inherit ARMADA_RAW_DIR. Wait/retry briefly if the "
                            "immediately preceding result has not yet appeared. Do not retype captured results.")
                saved = r._save_images(agent_dir, thread, list(req.images))
                attachments = [{"kind": "image", "name": s["name"], "file": s["file"]} for s in saved]
                attachments += [{"kind": "file", "name": str(fn)} for fn in req.files if str(fn).strip()]
                core = memory.assemble_core(root, agent_dir, run_agent)
                if use_tools:
                    core = r._tool_preamble(root, agent_dir) + "\n" + core
                compacted = th.compact_if_needed(eng, threshold_chars=r._compact_threshold(root, agent, req.job))
                convo = th.render()
                msg = message
                if scheduled_job:
                    msg += job_results.instructions(context.run_id, result_job)
                if saved:
                    paths = "; ".join(s["path"] for s in saved)
                    msg += f"\n\n[The owner attached images at: {paths}. Use your Read tool to view them.]"
                prompt = (convo + ("\n\n---\nRequest: " if req.task else "\n\n---\nOwner: ") + msg) if convo else msg
                turn = th.begin_turn(message, attachments=attachments or None)
                cap = r._TurnCapture(root, agent_dir, use_tools, thread=th, provider=eng.name)
                # Refresh grants after context construction to enforce revocations made meanwhile.
                request = replace(request, system=core, prompt=prompt,
                                  disallowed_tools=tuple(r._tool_grants(root, aid, eng, use_tools)))
                if self.session.active.cancelled:
                    result = RunResult(ok=False, cancelled=True, error="Run stopped by the owner.")
                else:
                    execution_started = time.time()
                    result = execute_request(eng, request, on_event=event, on_proc=process)
                    if not isinstance(result, RunResult):
                        raise ValueError("Engine returned no valid RunResult.")
                    if result.ok and (result.error or result.cancelled):
                        result.ok = False
                        result.error = result.error or "Run stopped by the owner."
                    live_text.close()
            except Exception as exc:
                live_text.close()
                log.exception("Agent turn failed for %s", aid)
                result = RunResult(ok=False, error=str(exc), output="".join(partial))
                safe_emit(self.on_event, {"kind": "error", "error": str(exc)})
            finally:
                if cap is not None:
                    try:
                        cap.finish()
                    except Exception as exc:
                        log.exception("Turn capture cleanup failed")
                        result.ok = False
                        result.error = result.error or f"Turn cleanup failed: {exc}"
            if raw_capture is not None:
                raw_capture.finish()
            if turn is None:
                turn = th.begin_turn(message, attachments=attachments or None)
            status = r._result_status(result)
            text = (result.output or "Completed without a text reply.") if result.ok else r._failed_output(result, "".join(partial))
            if scheduled_job:
                from . import job_results
                runtime_execution = ("timed_out" if result.timed_out else "stopped" if result.cancelled
                                     else "completed" if result.ok else "failed")
                raw_answer = result.output or "".join(partial)
                job_result = job_results.evaluate(raw_answer, run_id=context.run_id, job=result_job,
                    root=root, started=execution_started, runtime_execution=runtime_execution,
                    runtime_error=result.error, roots=grant.roots if grant else (), checks=result_checks)
                connector_errors = [f"Connector {row['server']}: {row['error']}" for row in result.raw.get("connector_runtime", [])
                                    if row.get("state") != "ready"]
                job_result["app_errors"].extend(connector_errors)
                if result.raw.get("startup_failure"):
                    job_result["startup_failure"] = result.raw["startup_failure"]
                if raw_capture is not None:
                    raw_capture.audit(job_result)
                status = job_results.status(job_result)
                text = job_results.original_answer(raw_answer) or (
                    "Completed without a text reply." if result.ok else "No final answer was produced.")
            if raw_capture is not None and raw_capture.errors and not scheduled_job:
                status = "error" if raw_capture.required else ("warn" if result.ok else status)
            th.complete_turn(turn, text, status=status,
                             outputs=cap.outputs or None if cap else None,
                             caps=cap.caps or None if cap else None)
            for sync in (lambda: r._sync_proposals(root, aid), lambda: r._sync_cap_requests(root, aid, thread)):
                try:
                    sync()
                except Exception:
                    log.exception("Post-turn synchronization failed")
            report = {"ts": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
                "agent": aid, "task": req.task or f"chat:{thread}", "thread": thread,
                "kind": "job" if req.task else "chat", "engine": getattr(eng, "name", "unknown"),
                "model": result.model, "status": status, "compacted": compacted,
                "summary": (_report_summary(result.output) if result.ok else (result.error or "")[:200]),
                "tokens": result.usage.as_dict(), "duration_s": round(time.monotonic() - started, 2),
                "memory_boundary": cap.memory_report if cap else None,
                "realm_id": context.realm.realm_id, "run_id": context.run_id}
            if raw_capture is not None:
                report["capture"] = raw_capture.report()
            if req.job and req.job.get("_retry_series"):
                report["retry"] = req.job["_retry_series"]
            if result.raw.get("runtime_readiness"):
                report["runtime_readiness"] = result.raw["runtime_readiness"]
            if result.raw.get("connector_runtime"):
                report["connector_runtime"] = result.raw["connector_runtime"]
            if job_result is not None:
                report["result"] = job_result
                report["app_errors"] = job_result["app_errors"]
                report["summary"] = (job_results.label(job_result) +
                    (": " + job_results.reason(job_result) if job_results.reason(job_result) else ""))[:700]
            if req.task:
                from .job_history import save_transcript
                transcript = {"content": text, "events": activity_events,
                              "outputs": cap.outputs if cap else []}
                if raw_capture is not None:
                    transcript["tool_results"] = raw_capture.records
                if scheduled_job:
                    transcript.update(raw_final_answer=raw_answer, app_errors=job_result["app_errors"])
                try:
                    report["output_file"] = save_transcript(agent_dir, context.run_id, transcript)
                except OSError:
                    log.exception("Could not save the job transcript; retaining it in the report")
                    report.update(output=text, activity=activity_events, outputs=transcript["outputs"])
                    if raw_capture is not None:
                        report["tool_results"] = raw_capture.records
                report.update(turn=turn, effort=request.effort if 'request' in locals() else None,
                              verbosity=output_level if 'output_level' in locals() else None)
            if cap and cap.stray:
                report["outside_root"] = cap.stray[:20]
                log.warning("Turn %s wrote outside the app root: %s", context.run_id, cap.stray[:5])
            try:
                r._write_report(agent_dir, aid, report)
                from .job_history import JOB_PREFIX
                if not thread.startswith(JOB_PREFIX):
                    thread_metadata.set_unread(agent_dir, thread)
            except Exception:
                log.exception("Could not record turn accounting or unread state")
            if req.task:
                r._say(f"ARMADA run · {aid}/{req.task} · {status} · tokens={result.usage.total}")
                return report
            return {"ok": result.ok, "output": result.output or result.error, "tokens": result.usage.as_dict(),
                    "model": result.model, "status": status, "error": result.error}
        finally:
            live_text.close()
            self.session.close()
