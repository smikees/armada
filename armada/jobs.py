"""Agent-authored job proposals (pending owner approval).

An agent that runs with tools can PROPOSE a scheduled job for itself by writing a JSON file to
its own ``jobs/_pending/<slug>.json`` (with its Write tool — reliable on this host; only the
Claude Code bash *sandbox* is flaky here, plain file writes are fine). Proposals live in the
``_pending/`` sub-folder, which the scheduler and the realm reader never glob (both use the
non-recursive ``jobs/*.json``), so a proposal simply CANNOT fire until the owner approves it.

``approve`` validates a proposal, stamps provenance + a ``created`` date, marks it enabled, and
writes it as the canonical ``jobs/<slug>.json`` (removing the pending file). ``reject`` just
deletes the pending file. This preserves the "explicit permission required" posture: an agent
may line up work for itself, but nothing new auto-runs on the owner's machine without a click.
"""
from __future__ import annotations
import datetime, json, re
from pathlib import Path
from . import util, scheduler
import logging
from .util import swallowed
log = logging.getLogger(__name__)

PENDING = "_pending"
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_MAX_PROMPT = 20000
_MAX_CMD = 4000


def _now() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _pending_dir(realm_root, agent_id: str) -> Path:
    return Path(realm_root) / "agents" / agent_id / "jobs" / PENDING


def _read_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:  # noqa — a malformed proposal is reported by validate(), never crashes
        swallowed(log, '_read_json: failed; returning a fallback')
        return {}


def slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").strip().lower()).strip("-")
    return s[:64] or "job"


def validate(job: dict) -> tuple[bool, list[str], dict]:
    """Validate a proposal dict (no disk I/O). Returns (ok, errors, normalized_job)."""
    errs: list[str] = []
    if not isinstance(job, dict):
        return False, ["proposal is not a JSON object"], {}
    name = str(job.get("name") or "").strip()
    if not name:
        errs.append("missing 'name'")
    slug = str(job.get("id") or "").strip().lower() or slugify(name)
    if not _SLUG_RE.match(slug):
        errs.append("'id' must be lowercase kebab-case (a-z, 0-9, '-'), 1–64 chars")
    kind = str(job.get("kind") or ("command" if (job.get("run") or job.get("command")) else "agent")).lower()
    if kind not in ("agent", "command"):
        errs.append("'kind' must be 'agent' or 'command'")
    prompt = str(job.get("prompt") or "")
    run = job.get("run") or job.get("command") or ""
    if kind == "agent" and not prompt.strip():
        errs.append("an agent job needs a 'prompt'")
    if kind == "command" and not str(run).strip():
        errs.append("a command job needs a 'run' command")
    if len(prompt) > _MAX_PROMPT:
        errs.append(f"'prompt' too long (>{_MAX_PROMPT} chars)")
    if isinstance(run, str) and len(run) > _MAX_CMD:
        errs.append(f"'run' too long (>{_MAX_CMD} chars)")
    cron = str(job.get("cron") or "").strip()
    sched = str(job.get("schedule") or "").strip()
    if cron:
        if not scheduler.is_cron(cron):
            errs.append("'cron' must be a 5-field cron expression (e.g. '0 9 * * 1-5')")
    elif sched and sched.lower() not in ("manual", "none", "on-demand"):
        if not (scheduler.is_cron(sched) or scheduler.parse_schedule(sched)):
            errs.append("'schedule' not understood (try 'daily 09:00', 'mon-fri 14:30', "
                        "a 5-field cron, or 'manual')")
    norm = dict(job)
    norm["id"], norm["name"], norm["kind"] = slug, (name or slug), kind
    return (not errs), errs, norm


def iter_pending(realm_root):
    """Yield (agent_id, slug, job, path) for every pending proposal in the realm."""
    adir = Path(realm_root) / "agents"
    if not adir.is_dir():
        return
    for ad in sorted(p for p in adir.iterdir() if p.is_dir()):
        pend = ad / "jobs" / PENDING
        if not pend.is_dir():
            continue
        for jf in sorted(pend.glob("*.json")):
            job = _read_json(jf)
            if job:
                yield ad.name, jf.stem, job, jf


def list_for_agent(realm_root, agent_id: str) -> list[dict]:
    """Validated proposals owned by one agent: [{slug, job, ok, errors}]."""
    out = []
    pend = _pending_dir(realm_root, agent_id)
    if pend.is_dir():
        for jf in sorted(pend.glob("*.json")):
            job = _read_json(jf)
            if job:
                ok, errs, norm = validate(job)
                out.append({"slug": jf.stem, "job": norm, "ok": ok, "errors": errs})
    return out


def count_pending(realm_root) -> int:
    return sum(1 for _ in iter_pending(realm_root))


def _find_pending(realm_root, agent_id: str, slug: str):
    """Locate a pending file by (agent, stem) WITHOUT building a path from the raw slug —
    match against real stems on disk so an odd slug can't traverse out of the folder."""
    for aid, s, job, path in iter_pending(realm_root):
        if aid == agent_id and s == slug:
            return job, path
    return None, None


def approve(realm_root, agent_id: str, slug: str) -> dict:
    agent_id = util.safe_seg(agent_id, "agent")
    job, src = _find_pending(realm_root, agent_id, str(slug))
    if not src:
        return {"ok": False, "error": "proposal not found"}
    ok, errs, norm = validate(job)
    if not ok:
        return {"ok": False, "error": "; ".join(errs)}
    jid = util.safe_seg(norm["id"], "job")            # validate() guarantees a safe kebab id
    dst = Path(realm_root) / "agents" / agent_id / "jobs" / f"{jid}.json"
    if dst.exists():
        return {"ok": False, "error": f"a job '{jid}' already exists — reject or rename the proposal"}
    norm["enabled"] = True
    norm["proposed_by"] = agent_id
    norm.setdefault("proposed_at", _now())
    norm["approved_at"] = _now()
    norm.setdefault("created", datetime.date.today().isoformat())
    util.write_json_atomic(dst, norm)
    try:
        src.unlink()
    except OSError:
        pass
    log_event(realm_root, agent_id, jid, norm.get("name", jid), "approved")
    return {"ok": True, "id": jid, "path": f"agents/{agent_id}/jobs/{jid}.json"}


def reject(realm_root, agent_id: str, slug: str) -> dict:
    agent_id = util.safe_seg(agent_id, "agent")
    job, src = _find_pending(realm_root, agent_id, str(slug))
    if src:
        # record the rejection in the ledger so the agent can be told this proposal was turned down
        # (the file is deleted, so without this there'd be no trace).
        log_event(realm_root, agent_id, (job or {}).get("id", src.stem),
                  (job or {}).get("name", src.stem), "rejected")
        try:
            src.unlink()
        except OSError as e:
            return {"ok": False, "error": str(e)}
    return {"ok": True}


# --- proposal ledger: a durable record of every proposal event (proposed / approved / rejected),
# so an agent has full visibility into what happened to the jobs it proposed. Agents write pending
# files directly with their Write tool, so 'proposed' events are back-filled by sync_proposals()
# after each turn; approve()/reject() log their own events. ---
LEDGER = "_ledger.jsonl"


def ledger_events(realm_root, agent_id: str) -> list[dict]:
    return _read_jsonl(Path(realm_root) / "agents" / agent_id / "jobs" / LEDGER)


def log_event(realm_root, agent_id: str, jid: str, name: str, event: str) -> None:
    p = Path(realm_root) / "agents" / agent_id / "jobs" / LEDGER
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        hist = _read_jsonl(p)[-299:] + [{"ts": _now(), "id": jid, "name": name, "event": event}]
        p.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in hist) + "\n", encoding="utf-8")
    except OSError:
        pass


def sync_proposals(realm_root, agent_id: str) -> None:
    """Record a 'proposed' ledger event for any _pending file that isn't already open in the ledger.
    Called after an agent turn (the agent wrote the file directly, so we detect it here)."""
    pd = Path(realm_root) / "agents" / agent_id / "jobs" / PENDING
    if not pd.is_dir():
        return
    last = {}
    for e in ledger_events(realm_root, agent_id):
        last[e.get("id")] = e.get("event")
    for jf in sorted(pd.glob("*.json")):
        j = _read_json(jf)
        jid = (j or {}).get("id", jf.stem)
        if jid and last.get(jid) != "proposed":
            log_event(realm_root, agent_id, jid, (j or {}).get("name", jid), "proposed")
            last[jid] = "proposed"


def _read_jsonl(p: Path) -> list[dict]:
    out = []
    if p.exists():
        for ln in p.read_text(encoding="utf-8-sig").splitlines():
            ln = ln.strip()
            if ln:
                try:
                    out.append(json.loads(ln))
                except Exception:  # noqa
                    swallowed(log, '_read_jsonl: failed; ignored')
    return out


def status_for_agent(realm_root, agent_id: str) -> dict:
    """Full-visibility snapshot of one agent's job proposals, derived from the durable ledger:
      pending  — proposals currently in _pending (ground truth on disk),
      approved — proposals the owner approved (now live jobs),
      rejected — proposals the owner rejected,
      history  — the chronological event trail (newest first), so nothing is lost."""
    ad = Path(realm_root) / "agents" / agent_id
    jd = ad / "jobs"
    pend = []
    pd = jd / PENDING
    if pd.is_dir():
        for jf in sorted(pd.glob("*.json")):
            j = _read_json(jf)
            if j:
                pend.append({"id": j.get("id", jf.stem), "name": j.get("name", jf.stem)})
    pend_ids = {p["id"] for p in pend}

    events = list(ledger_events(realm_root, agent_id))
    # fold in the legacy _rejected.jsonl (pre-ledger rejections) so old history isn't lost
    for r in _read_jsonl(jd / "_rejected.jsonl"):
        events.append({"ts": r.get("ts", ""), "id": r.get("id"), "name": r.get("name"), "event": "rejected"})
    events.sort(key=lambda e: str(e.get("ts", "")))

    names, latest = {}, {}
    for e in events:
        i = e.get("id")
        if not i:
            continue
        names[i] = e.get("name", i)
        latest[i] = e.get("event")
    for p in pend:                       # a file physically present is pending, whatever the log says
        latest[p["id"]] = "proposed"
        names.setdefault(p["id"], p["name"])

    approved = [{"id": i, "name": names.get(i, i)} for i, ev in latest.items() if ev == "approved"]
    rejected = [{"id": i, "name": names.get(i, i)} for i, ev in latest.items() if ev == "rejected"][-10:]
    # newest-first event trail (deduped consecutive noise kept simple)
    history = [{"id": e.get("id"), "name": names.get(e.get("id"), e.get("id")),
                "event": ("pending" if e.get("id") in pend_ids and e.get("event") == "proposed" else e.get("event")),
                "ts": str(e.get("ts", ""))[:16].replace("T", " ")}
               for e in reversed(events)][:12]
    return {"pending": pend, "approved": approved, "rejected": rejected, "history": history}
