"""Shared helpers for the route mixins in armada/routes/.

Module-level functions used by more than one area: a realm's JSON projection, a job's JSON projection, thread-title heuristics. Plus `SharedRoutes`,
a mixin of handler methods that are themselves genuinely cross-cutting (`_slug`,
`_write_data_image`, `_refresh_system`/`_refresh_system_ep`, `_render_md`) rather than belonging
to one area.

Split out of serve.py (Phase 2, 2.3) — a pure move, no behaviour change.
"""
from __future__ import annotations
import json, logging
from pathlib import Path
from .. import util
from ..util import safe_seg
from ..util import swallowed

log = logging.getLogger("armada.serve")


def _derive_title(text: str) -> str:
    """A short thread title from the first prompt (heuristic, no model call): first meaningful line,
    stripped of markdown/quotes, trimmed to a word boundary, sentence-cased."""
    import re
    line = ""
    for ln in (text or "").splitlines():
        c = re.sub(r"^[\s>*#\-•–—]+", "", ln)      # leading list / quote / heading / bold markers
        c = c.replace("**", "").replace("`", "").strip().strip('"\'').strip()
        if c:
            line = c
            break
    if not line:
        return ""
    line = re.sub(r"\s+", " ", line)
    if len(line) > 48:
        line = line[:48].rsplit(" ", 1)[0].rstrip(",.;:!?-–—") + "…"
    else:
        line = line.rstrip(",.;:!?")
    if line and line[0].islower():
        line = line[0].upper() + line[1:]
    return line[:80]


def _llm_title(agent_dir, first_msg: str) -> str:
    """A concise topic-summary title from a cheap model (haiku), like the Claude app. Best-effort:
    returns '' on any failure so the caller can fall back to the heuristic."""
    msg = (first_msg or "").strip()
    if not msg:
        return ""
    try:
        from ..engine import get_engine, engine_for
        provider = engine_for(Path(agent_dir).parent.parent, Path(agent_dir).name)
        system = ("Write a very short title (3-6 words) that summarises the TOPIC of the user's message, "
                  "like a chat title. Be specific but brief. Reply with ONLY the title — no quotes, no "
                  "trailing punctuation, no preamble.")
        res = get_engine(provider).run(system=system, prompt=msg[:2000], model="haiku" if provider == "claude" else None,
                                 cwd=str(agent_dir), allow_tools=False, timeout=45)
        if res.ok and res.output:
            t = res.output.strip().splitlines()[0].strip().strip('"\'`').strip().rstrip(".!?,;:")
            if 0 < len(t) <= 80:
                return t
    except Exception:  # noqa
        swallowed(log, '_llm_title: failed; ignored')
    return ""


# ---- model -> JSON -------------------------------------------------------------------------
def _realm_json(realm) -> dict:
    def agent(a):
        return {
            "id": a.id, "display": a.display, "leader": a.leader,
            "role": a.theme_role, "is_coordinator": a.is_coordinator,
            "status": a.status, "bulletin": a.bulletin, "membership": a.membership,
            "runs_30d": a.runs_30d, "tokens_30d": a.tokens_30d, "cost_30d": a.cost_30d,
            "placeholder": a.placeholder,
            "skills": [{"id": s.id, "version": s.version, "scopes": s.scopes} for s in a.skills],
            "jobs": [{"id": j.id, "name": j.name, "kind": j.kind, "cadence": j.cadence,
                      "last_status": j.last_status, "last_seen": j.last_seen} for j in a.jobs],
        }
    coord = realm.coordinator
    return {
        "name": realm.name, "root": realm.root, "engine": realm.engine,
        "generated_at": realm.generated_at,
        "theme": {"collective": realm.theme_collective, "agent": realm.theme_agent,
                  "coordinator": realm.theme_coordinator},
        "telemetry": {"agents": len(realm.members), "jobs": sum(len(a.jobs) for a in realm.agents),
                      "runs_30d": sum(a.runs_30d for a in realm.agents),
                      "tokens_30d": realm.tokens_30d, "cost_30d": realm.cost_30d},
        "coordinator": agent(coord) if coord else None,
        "agents": [agent(a) for a in realm.members],
        "gaps": [{"kind": g.kind, "label": g.label} for g in realm.gaps],
    }


def _job_detail(realm_root, agent_id, job_id, selected_run="") -> dict:
    from .. import job_history
    from ..threads import Thread
    from ..webui.threadsview import _turn, _working_turn, _progress_steps
    from ..webui._base import E
    agent_id, job_id = safe_seg(agent_id, "agent"), safe_seg(job_id, "job")
    ad = Path(realm_root) / "agents" / agent_id
    p = ad / "jobs" / f"{job_id}.json"
    jc = json.loads(p.read_text(encoding="utf-8-sig")) if p.exists() else {}
    all_runs = job_history.reports(ad, job_id)
    runs = all_runs[-8:][::-1]
    ac = json.loads((ad / "agent.json").read_text(encoding="utf-8-sig"))
    display = ac.get("display") or ac.get("name") or agent_id
    avatar = f'<img src="/avatar/{E(agent_id)}" width="28" height="28" style="border-radius:50%;object-fit:cover" alt="">'
    th = Thread(ad, job_history.thread_name(job_id))
    pending = th.open_turn()
    # Use the same validated live markers as the list (stale files aren't a running job).
    from ..webui.agentbits import _running_jobs
    running = job_id in _running_jobs(realm_root, agent_id)
    chosen = next((ev for ev in all_runs if str(ev.get("run_id") or ev.get("ts")) == selected_run), None)
    html = '<div style="color:var(--text-muted)">No runs yet.</div>'
    if not selected_run and running:
        html = _working_turn(avatar, display, th.progress(pending["turn"]) if pending else None)
    elif chosen or runs:
        ev = chosen or runs[0]
        content = job_history.transcript(ad, ev)
        from ..webui.jobresults import result_html
        html = _progress_steps(content.get("events")) + _turn(
            "assistant", content.get("content", ""), ev.get("ts", ""), 0, False,
            agent_id, ev.get("thread", "main"), display, False,
            av=avatar, seg=content.get("segments"), actions=False)
        from .. import status
        from ..webui.schedfmt import _fmt_ts
        raw_status = ev.get("status", "")
        label = {status.SUCCESS: "Succeeded", status.FAILED: "Failed", status.WARN: "Warning"}.get(
            status.normalize(raw_status), str(raw_status).title())
        if ev.get("result"):
            from ..job_results import label as result_label
            label = result_label(ev["result"])
        html = (f'<div style="margin-bottom:10px;color:var(--text-dim)">'
                f'<span style="color:{status.color(raw_status)}">{E(label)}</span>'
                f' · {E(_fmt_ts(ev.get("ts", "")))}</div>' + result_html(ev, content) + html)
    entries = [{k: ev.get(k) for k in ("ts", "status", "summary", "tokens", "result", "capture")} |
               {"id": str(ev.get("run_id") or ev.get("ts"))} for ev in runs]
    from .. import scheduler
    from ..webui.realmpages import _job_history_rows, _job_week_html
    from ..webui.agentbits import _job_health7, _job_created_ts, _week_filter_bucket
    rc = json.loads((Path(realm_root) / "realm.json").read_text(encoding="utf-8-sig"))
    now = scheduler.now_in(rc)
    week = _job_health7(all_runs, jc.get("cron") or jc.get("schedule") or "manual", now,
                       running, since=_job_created_ts(realm_root, agent_id, job_id, jc), latest_today=True)
    from ..webui.schedfmt import _job_next_dt
    next_run = _job_next_dt(jc.get("cron") or jc.get("schedule"), now.replace(tzinfo=None))
    from .. import datefmt
    next_label = ("off" if jc.get("enabled") is False else "running now" if running else
                  datefmt.moment(next_run) if next_run else "on demand")
    return {"id": jc.get("id", job_id), "name": jc.get("name", job_id),
            "kind": jc.get("kind") or ("command" if (jc.get("run") or jc.get("command")) else "agent"),
            "cadence": jc.get("schedule") or jc.get("cron") or "manual",
            "allow_tools": bool(jc.get("allow_tools")),
            "run": jc.get("run") or jc.get("command") or "",
            "prompt": jc.get("prompt", ""),
            "runs": entries, "html": html, "running": running,
            "history_html": _job_history_rows(agent_id, all_runs),
            "week_html": _job_week_html(week), "jstatus": _week_filter_bucket(week),
            "next_label": next_label}


class SharedRoutes:
    def _send_user_image(self, path: Path) -> None:
        from ..origins import IMAGE_CSP
        self._send(200, path.read_bytes(), self._CT.get(path.suffix.lower(), "image/png"),
                   csp=IMAGE_CSP)

    def _refresh_system_ep(self, body: dict) -> dict:
        from .. import memory as _memory
        try:
            r = _memory.refresh_system_memory(self.realm, trigger="manual")
            return {"ok": True, "changed": r["changed"]}
        except Exception as e:  # noqa
            log.exception("manual system refresh failed")
            return {"ok": False, "error": str(e)}

    @staticmethod
    def _slug(s: str) -> str:
        import re
        return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-") or "item"

    def _refresh_system(self, trigger: str) -> None:
        """Regenerate the read-only System memory after a change that affects realm basics.
        Best-effort — never let it break the triggering action."""
        try:
            from .. import memory as _memory
            _memory.refresh_system_memory(self.realm, trigger=trigger)
        except Exception:  # noqa
            log.exception("system memory refresh failed (%s)", trigger)

    @staticmethod
    def _write_data_image(base_no_ext: Path, dataurl: str) -> dict:
        import base64, re
        m = re.match(r"data:image/(png|jpe?g|webp|gif|svg\+xml);base64,(.+)$", dataurl or "", re.S)
        if not m:
            return {"ok": False, "error": "expected a base64 image data URL"}
        ext = {"jpeg": "jpg", "svg+xml": "svg"}.get(m.group(1), m.group(1))
        raw = base64.b64decode(m.group(2))
        if len(raw) > 5_000_000:
            return {"ok": False, "error": "image too large (max 5MB)"}
        for old in base_no_ext.parent.glob(base_no_ext.name + ".*"):
            old.unlink()
        base_no_ext.with_suffix("." + ext).write_bytes(raw)
        return {"ok": True, "ext": ext}

    def _render_md(self, body: dict) -> dict:
        """Render markdown to HTML. Writes nothing, reads nothing — it exists so the browser can
        preview unsaved text without a second markdown renderer of its own. Two renderers is how a
        preview starts quietly disagreeing with the page; this way the preview IS the page's."""
        from ..webui._base import _md as _render
        text = str(body.get("text") or "")
        if len(text) > 200_000:
            return {"ok": False, "error": "too long to render"}
        return {"ok": True, "html": _render(text.strip())}
