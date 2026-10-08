"""Jobs: new/save/enable/delete a job, job detail, job calendar, run.

Split out of serve.py (Phase 2, 2.3) — a pure move, no behaviour change; the route table
stays in serve.py, only the handler bodies moved.
"""
from __future__ import annotations
import http.server, io, json, logging, os, subprocess, sys, threading, time, urllib.parse, contextlib
from pathlib import Path
from .. import activerealm, reader, render, scheduler, util, brand
from ..util import safe_seg
from . import _shared
from ._shared import _job_detail
from ..util import swallowed

log = logging.getLogger("armada.serve")


class JobRoutes:
    def _get_new_job(self):
        from .. import webui
        self._send(200, webui.render_new_job(reader.read(self.realm), self.realm, self._query().get("agent", ""),
                                             dark=self._dark()))

    def _get_job(self, path):
        from .. import webui
        parts = [p for p in path.split("/") if p]       # ['job', '<agent>', '<job>']
        try:
            self._send(200, webui.render_job(reader.read(self.realm), self.realm,
                                             parts[1] if len(parts) > 1 else "",
                                             parts[2] if len(parts) > 2 else "", dark=self._dark()))
        except SystemExit as e:
            self._err_page(e)

    def _get_job_calendar(self):
        q = self._query()
        self._json(200, self._job_calendar(q.get("from", ""), q.get("to", ""), q.get("scope", "")))

    def _get_job_detail(self):
        q = self._query()
        result = _job_detail(self.realm, q.get("agent", ""), q.get("job", ""), q.get("run", ""))
        context = getattr(self, "request_context", None)
        if context:
            from ..request_context import bind_content_html
            result["html"] = bind_content_html(result["html"], context)
        self._json(200, result)

    def _new_job(self, body: dict) -> dict:
        agent, name = body.get("agent"), (body.get("name") or "").strip()
        if not name:
            return {"ok": False, "error": "name required"}
        adir = Path(self.realm) / "agents" / safe_seg(agent, "agent")
        if not adir.is_dir():
            return {"ok": False, "error": f"no agent {agent}"}
        jid = self._slug(name)
        jf = adir / "jobs" / f"{safe_seg(jid, 'job')}.json"
        if jf.exists():
            return {"ok": False, "error": f"job '{jid}' already exists"}
        import datetime as _dt
        kind = body.get("kind", "agent")
        job = {"id": jid, "name": name, "kind": kind, "allow_tools": True, "thread": body.get("thread", "main"),
               "created": _dt.date.today().isoformat()}
        text = body.get("prompt", "")
        job["run" if kind == "command" else "prompt"] = text
        cron = (body.get("cron") or "").strip()
        job["cron"] = cron if cron else None
        if not cron:
            job["schedule"] = "manual"; job.pop("cron", None)
        try:
            (adir / "jobs").mkdir(exist_ok=True)
            with util.file_lock(jf):
                if jf.exists():
                    return {"ok": False, "error": f"job '{jid}' already exists"}
                util.write_json_atomic(jf, job)
            return {"ok": True, "id": jid}
        except Exception as e:  # noqa
            swallowed(log, '_new_job: failed; error returned to the caller')
            return {"ok": False, "error": str(e)}

    def _job_calendar(self, dfrom: str, dto: str, scope: str = "") -> dict:
        from .. import webui
        import datetime
        try:
            a = datetime.date.fromisoformat(dfrom)
            b = datetime.date.fromisoformat(dto)
        except Exception:  # noqa
            log.debug('_job_calendar: failed; using a default', exc_info=True)
            today = datetime.date.today()
            a, b = today.replace(day=1), today
        if b < a:
            a, b = b, a
        if (b - a).days > 45:
            b = a + datetime.timedelta(days=45)
        try:
            if scope == "system":
                return {"ok": True, "events": webui._sysjobcal_events(self.realm, a, b)}
            realm = reader.read(self.realm)
            return {"ok": True, "events": webui._jobcal_events(realm, self.realm, a, b)}
        except Exception as e:  # noqa
            swallowed(log, '_job_calendar: failed; error returned to the caller')
            return {"ok": False, "error": str(e), "events": []}

    def _job_enable(self, body: dict) -> dict:
        """Switch a job on or off. Off means the scheduler skips it; 'Run now' still works."""
        agent, job = body.get("agent"), body.get("job")
        p = Path(self.realm) / "agents" / safe_seg(agent, "agent") / "jobs" / f"{safe_seg(job, 'job')}.json"
        if not p.exists():
            return {"ok": False, "error": f"no job {job}"}
        try:
            on = bool(body.get("enabled"))
            def change(jc):
                if on:
                    jc.pop("enabled", None)
                else:
                    jc["enabled"] = False
            util.mutate_json(p, change)
            return {"ok": True, "enabled": on}
        except Exception as e:  # noqa
            swallowed(log, '_job_enable: failed; error returned to the caller')
            return {"ok": False, "error": str(e)[:140]}

    def _delete_job(self, body: dict) -> dict:
        """Delete a job file. The run history in agents/<id>/runs stays — it is a record of what
        actually happened, and removing it because the job was retired would falsify the telemetry."""
        agent, job = body.get("agent"), body.get("job")
        p = Path(self.realm) / "agents" / safe_seg(agent, "agent") / "jobs" / f"{safe_seg(job, 'job')}.json"
        if not p.exists():
            return {"ok": False, "error": f"no job {job}"}
        try:
            with util.file_lock(p):
                util.read_json_state(p)
                p.unlink()
            return {"ok": True, "deleted": f"agents/{agent}/jobs/{job}.json"}
        except Exception as e:  # noqa
            swallowed(log, '_delete_job: failed; error returned to the caller')
            return {"ok": False, "error": str(e)[:140]}

    def _save_job(self, body: dict) -> dict:
        agent, job = body.get("agent"), body.get("job")
        p = Path(self.realm) / "agents" / safe_seg(agent, "agent") / "jobs" / f"{safe_seg(job, 'job')}.json"
        if not p.exists():
            return {"ok": False, "error": f"no job {job}"}
        def change(jc):
            if "retries" in body:
                from ..job_retries import validate
                jc["retries"] = validate(body["retries"])
                jc.pop("on_failure", None)
            for k in ("prompt", "summary", "kind", "thread", "budget"):
                if k in body:
                    jc[k] = body[k]
            if "name" in body:
                jc["name"] = str(body["name"]).strip() or jc.get("name", job)
            for k in ("model", "effort", "verbosity"):
                if k not in body:
                    continue
                if body.get(k):
                    jc[k] = body[k]
                else:
                    jc.pop(k, None)
            if body.get("allowed_skills") is not None:
                jc["allowed_skills"] = body["allowed_skills"]
            cron = (body.get("cron") or "").strip()
            if cron:
                jc["cron"] = cron
                jc.pop("schedule", None)
            else:
                jc["schedule"] = "manual"
                jc.pop("cron", None)
            from ..tool_capture import KEYS, validate
            for key in KEYS:
                if key in body:
                    jc[key] = body[key]
            validate(jc, self.realm, job)
            from .. import dry_runs
            for key in ("dry_run_command", "dry_run_keep_days"):
                if key in body:
                    jc[key] = body[key]
            dry_runs.settings(jc)
        try:
            saved = util.mutate_json(p, change)
            if "dry_run_command" in body:
                from .. import inspection
                saved.setdefault("id", job)
                inspection.approve_command(self.realm, agent, saved)
            return {"ok": True, "path": f"agents/{agent}/jobs/{job}.json"}
        except Exception as e:  # noqa
            swallowed(log, '_save_job: failed; error returned to the caller')
            return {"ok": False, "error": f"write: {e}"}

    def _start_dry_run(self, body):
        from .. import dry_runs
        try:
            run = dry_runs.start(self.realm, body.get("agent"), body.get("job"), body.get("model", ""))
            return {"ok": True, "run": run}
        except (OSError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def _stop_dry_run(self, body):
        from .. import dry_runs
        try:
            return dry_runs.stop(self.realm, body.get("agent"), body.get("job"), body.get("run_id"))
        except (OSError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

    def _get_dry_runs(self):
        from .. import dry_runs
        from ..webui.dryruns import result_html
        q = self._query()
        try:
            runs = dry_runs.listing(self.realm, q.get("agent"), q.get("job"))
            selected = q.get("run_id") or (runs[0]["run_id"] if runs else "")
            run = dry_runs.read(self.realm, q.get("agent"), q.get("job"), selected) if selected else None
            self._json(200, {"ok": True, "runs": runs, "run": run,
                "models": dry_runs.models(self.realm),
                "html": result_html(self.realm, run) if run else "No dry runs yet. Choose a model to create a draft."})
        except (OSError, ValueError) as exc:
            self._json(400, {"ok": False, "error": str(exc)})

    def _run(self, body: dict) -> dict:
        from ..runner import run_job
        agent, job = body.get("agent"), body.get("job")
        engine = body.get("engine", "auto")
        if not agent or not job:
            return {"ok": False, "output": "missing agent/job"}
        # A switched-off job does not run, by hand or otherwise. The button is disabled in the UI,
        # but a page open since before the switch was flipped can still post this — and the file on
        # disk is what decides, not what the page last drew.
        jf = Path(self.realm) / "agents" / safe_seg(agent, "agent") / "jobs" / f"{safe_seg(job, 'job')}.json"
        try:
            if jf.exists() and json.loads(jf.read_text(encoding="utf-8-sig")).get("enabled") is False:
                return {"ok": False, "output": "This job is switched off. Switch it on to run it."}
        except (OSError, json.JSONDecodeError):
            pass                              # unreadable job: let run_job report the real problem
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                report = run_job(self.realm, agent, job, engine=engine)
            from ..job_history import transcript
            output = transcript(Path(self.realm) / "agents" / agent, report).get("content")
            return {"ok": report.get("status") == "ok", "status": report.get("status"),
                    "report": report, "output": output or buf.getvalue()}
        except SystemExit as e:
            return {"ok": False, "output": buf.getvalue() + f"\n[stopped] {e}"}
        except Exception as e:  # noqa
            swallowed(log, '_run: failed; error returned to the caller')
            return {"ok": False, "output": buf.getvalue() + f"\n[error] {type(e).__name__}: {e}"}
