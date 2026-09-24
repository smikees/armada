"""Shared helpers for the route mixins in armada/routes/.

Module-level functions used by more than one area: the realm registry at ~/.armada/realms.json,
a realm's JSON projection, a job's JSON projection, thread-title heuristics. Plus `SharedRoutes`,
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
        from ..engine.claude import ClaudeEngine
        system = ("Write a very short title (3-6 words) that summarises the TOPIC of the user's message, "
                  "like a chat title. Be specific but brief. Reply with ONLY the title — no quotes, no "
                  "trailing punctuation, no preamble.")
        res = ClaudeEngine().run(system=system, prompt=msg[:2000], model="haiku",
                                 cwd=str(agent_dir), allow_tools=False, timeout=45)
        if res.ok and res.output:
            t = res.output.strip().splitlines()[0].strip().strip('"\'`').strip().rstrip(".!?,;:")
            if 0 < len(t) <= 80:
                return t
    except Exception:  # noqa
        swallowed(log, '_llm_title: failed; ignored')
    return ""


def _reg_path() -> Path:
    return util.data_dir() / "realms.json"


def _reg_load() -> list[dict]:
    p = _reg_path()
    try:
        return json.loads(p.read_text(encoding="utf-8-sig")) if p.exists() else []
    except Exception:  # noqa
        swallowed(log, '_reg_load: failed; returning a fallback')
        return []


def _reg_save(items: list[dict]) -> None:
    p = _reg_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    util.write_json_atomic(p, items)


def _reg_rename(path: str, name: str) -> None:
    """Keep the registry's copy of a realm's name in step with realm.json.

    Two stores hold it: realm.json, which the realm itself carries anywhere it goes, and
    ~/.armada/realms.json, which is what the switcher and the realm menu actually read. Writing
    one without the other is how a realm ends up with two names on the same screen.
    """
    try:
        target = str(Path(path).resolve())
    except OSError:
        return
    items = _reg_load()
    hit = False
    for i in items:
        try:
            if str(Path(i.get("path", "")).resolve()) == target:
                i["name"], hit = name, True
        except OSError:
            continue
    if hit:
        _reg_save(items)


def _reg_ensure(path: str, name: str) -> None:
    path = str(Path(path).resolve())
    items = _reg_load()
    if not any(i.get("path") == path for i in items):
        items.append({"name": name, "path": path})
        _reg_save(items)


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


def _job_detail(realm_root, agent_id, job_id) -> dict:
    p = Path(realm_root) / "agents" / safe_seg(agent_id, "agent") / "jobs" / f"{job_id}.json"
    jc = json.loads(p.read_text(encoding="utf-8-sig")) if p.exists() else {}
    # recent run-reports for this job
    rf = Path(realm_root) / "agents" / safe_seg(agent_id, "agent") / "runs" / f"{agent_id}.jsonl"
    runs = []
    if rf.exists():
        for ln in rf.read_text(encoding="utf-8-sig").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                ev = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if ev.get("task") == job_id:
                runs.append({"ts": ev.get("ts"), "status": ev.get("status"),
                             "summary": ev.get("summary", ""), "tokens": ev.get("tokens")})
    return {"id": jc.get("id", job_id), "name": jc.get("name", job_id),
            "kind": jc.get("kind") or ("command" if (jc.get("run") or jc.get("command")) else "agent"),
            "cadence": jc.get("schedule") or jc.get("cron") or "manual",
            "allow_tools": bool(jc.get("allow_tools")),
            "run": jc.get("run") or jc.get("command") or "",
            "prompt": jc.get("prompt", ""),
            "runs": runs[-8:][::-1]}


class SharedRoutes:
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

