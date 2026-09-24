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
        self._json(200, _job_detail(self.realm, q.get("agent", ""), q.get("job", "")))

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
            jc = json.loads(p.read_text(encoding="utf-8-sig"))
            on = bool(body.get("enabled"))
            if on:
                jc.pop("enabled", None)      # absent means on; don't litter every file with true
            else:
                jc["enabled"] = False
            util.write_json_atomic(p, jc)
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
        try:
            jc = json.loads(p.read_text(encoding="utf-8-sig"))
        except Exception as e:  # noqa
            swallowed(log, '_save_job: failed; error returned to the caller')
            return {"ok": False, "error": f"read: {e}"}
        for k in ("prompt", "summary", "kind", "thread", "on_failure", "budget"):
            if k in body:
                jc[k] = body[k]
        for k in ("model", "effort"):
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
        try:
            util.write_json_atomic(p, jc)
            return {"ok": True, "path": f"agents/{agent}/jobs/{job}.json"}
        except Exception as e:  # noqa
            swallowed(log, '_save_job: failed; error returned to the caller')
            return {"ok": False, "error": f"write: {e}"}

    def _run(self, body: dict) -> dict:
        from ..runner import run_job
        agent, job = body.get("agent"), body.get("job")
        engine = body.get("engine", "mock")
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
            return {"ok": report.get("status") == "ok", "status": report.get("status"),
                    "report": report, "output": buf.getvalue()}
        except SystemExit as e:
            return {"ok": False, "output": buf.getvalue() + f"\n[stopped] {e}"}
        except Exception as e:  # noqa
            swallowed(log, '_run: failed; error returned to the caller')
            return {"ok": False, "output": buf.getvalue() + f"\n[error] {type(e).__name__}: {e}"}

