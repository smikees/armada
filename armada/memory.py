"""Layered memory + always-on core assembly (SPEC §5).

The core is what ARMADA injects into EVERY run for an agent, from files, never compacted:
  realm objectives + realm tenets + realm memory (known to all)
  + the agent's mandate + soul + tenets + its OWN private memory (scoped to it).

Realm memory loads for every agent; agent memory loads only for that agent — "everyone
knows the owner's name; only Travel knows he prefers hotels." Thread history is separate
(threads.py) and IS subject to compaction; the core here is always re-assembled fresh.
"""
from __future__ import annotations
import re, os, json, datetime
from pathlib import Path
import logging
from .util import swallowed
log = logging.getLogger(__name__)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8-sig") if p.exists() else ""


def _mission_framing(text: str) -> str:
    """The realm's North Star FRAMING only — title, mandate/guardrails, and the meta-objective — with
    the per-goal enumeration stripped out. Every agent shares the framing, but each agent's actual
    goals are injected SCOPED to it (goals_for_agent), so no one carries all nine. We cut at the first
    section heading that isn't 'Meta' (where the goal listing begins); if the doc isn't structured that
    way, it's kept whole."""
    lines = text.splitlines()
    cut = None
    for i, ln in enumerate(lines):
        m = re.match(r"^\s*#{2,4}\s+(.+)", ln)
        if m and m.group(1).strip().lower() != "meta":
            cut = i
            break
    out = "\n".join(lines[:cut]) if cut is not None else text
    return out.rstrip().rstrip("-").rstrip()          # drop a dangling '---' separator


def _frontmatter(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"')
    return meta, m.group(2)


def _memories(mem_dir: Path) -> list[tuple[str, str]]:
    out = []
    if mem_dir.is_dir():
        for f in sorted(mem_dir.glob("*.md")):
            meta, body = _frontmatter(_read(f))
            body = body.strip()
            if body:
                out.append((meta.get("title", f.stem), body))
    return out


def _core_sections(realm_root, agent_dir, agent: dict) -> list[tuple[str, str]]:
    """The always-on core, as ordered (bucket, text) sections. `bucket` groups sections for the
    'Loaded context' breakdown: 'mission' (objectives/tenets/mandate/soul), 'realm_memory',
    'goals', 'agent_memory'. This is the SINGLE source of truth — assemble_core() joins these
    into the prompt and core_breakdown() sizes them, so the UI can't drift from what's injected."""
    realm_root, agent_dir = Path(realm_root), Path(agent_dir)
    S: list[tuple[str, str]] = []

    obj, ten = _read(realm_root / "objectives.md"), _read(realm_root / "tenets.md")
    if obj.strip():
        # framing only (meta-objective + guardrails) — the per-goal list is injected scoped per agent
        S.append(("mission", "# Realm mission\n" + _mission_framing(obj).strip()))
    if ten.strip():
        S.append(("mission", "# Realm tenets (guardrails — always apply)\n" + ten.strip()))
    # System memory (the managed digest) gets its own prominent section; the owner's own realm
    # memories follow as bullets. Both are loaded for every agent.
    mem_dir = realm_root / "memory"
    sys_body, others = "", []
    if mem_dir.is_dir():
        for f in sorted(mem_dir.glob("*.md")):
            meta, body = _frontmatter(_read(f))
            body = body.strip()
            if not body:
                continue
            if f.name == SYSTEM_MEMORY_FILE or (meta.get("kind", "").strip().lower() in ("system", "core")):
                sys_body = body
            else:
                others.append((meta.get("title", f.stem), body))
    if sys_body:
        S.append(("realm_memory", "# System memory — realm basics (managed; every agent has this)\n" + sys_body))
    if others:
        S.append(("realm_memory", "# Realm memory (known to every agent)\n"
                  + "\n".join(f"- **{t}** — {b}" for t, b in others)))

    # Goals this agent advances — loaded into every thread for the mapped agents
    # (the coordinator is mapped to all). Lazy import to avoid a goals<->memory cycle.
    _goals, is_coord = None, bool(agent.get("coordinator"))
    try:
        from . import goals as _goals
        gs = _goals.goals_for_agent(realm_root, Path(agent_dir).name, is_coord=is_coord)
    except Exception:  # never let goals loading break a run
        swallowed(log, '_core_sections: failed; using a default')
        gs = []
    if gs:
        lines = []
        for g in gs:
            tags = " · ".join(x for x in (g.get("effective_status", "") or g.get("status", ""), (("ETA " + g["target_label"]) if g.get("target_label") else "")) if x)
            head = f"- **{g['title']}**" + (f" [{tags}]" if tags else "")
            body = (g.get("body") or "").strip()
            lines.append(head + (f" — {body}" if body else ""))
        S.append(("goals", "# Goals you advance (realm objectives mapped to you)\n" + "\n".join(lines)))
    # (The high-level map of ALL realm goals now lives in System memory, shared by every agent, so it
    # isn't duplicated here — each agent still carries its OWN goals in full above.)

    mandate = _read(agent_dir / agent.get("mandate", "mandate.md"))
    if mandate.strip():
        S.append(("mission", "# Your mandate (who you are, what you do)\n" + mandate.strip()))
    soul = _read(agent_dir / agent.get("soul", "soul.md"))
    if soul.strip():
        S.append(("mission", "# Your voice & traits\n" + soul.strip()))
    aten = _read(agent_dir / "tenets.md")
    if aten.strip():
        S.append(("mission", "# Your tenets\n" + aten.strip()))
    # How much to write back. Sits with voice and tenets because that's what it is — a statement
    # about how this agent talks, not about what it knows. Always present: an agent nobody has
    # configured should still be told what's expected rather than left to guess.
    try:
        from . import verbosity as _verbosity
        S.append(("mission", _verbosity.prompt_block(
            _verbosity.normalise(agent.get("verbosity")) or _verbosity.realm_level(realm_root))))
    except Exception:  # noqa — never let a preference break a run
        swallowed(log, '_core_sections: failed; ignored')
    amem = _memories(agent_dir / "memory")
    if amem:
        S.append(("agent_memory", "# Your private memory (only you know this)\n"
                  + "\n".join(f"- **{t}** — {b}" for t, b in amem)))
    return S


def assemble_core(realm_root, agent_dir, agent: dict) -> str:
    return "\n\n".join(text for _, text in _core_sections(realm_root, agent_dir, agent))


def core_breakdown(realm_root, agent_dir, agent: dict) -> dict:
    """Char counts per context bucket (mission / goals / realm_memory / agent_memory), measured
    on the exact section text that assemble_core() puts into the prompt."""
    out = {"mission": 0, "goals": 0, "realm_memory": 0, "agent_memory": 0}
    for bucket, text in _core_sections(realm_root, agent_dir, agent):
        out[bucket] = out.get(bucket, 0) + len(text)
    return out


def core_stats(realm_root, agent_dir, agent: dict) -> dict:
    return {"realm_memories": len(_memories(Path(realm_root) / "memory")),
            "agent_memories": len(_memories(Path(agent_dir) / "memory"))}


# --- default "core" memory: owner + environment, seeded at setup ---------------------------
_CORE_FIELDS = ["Owner", "Timezone", "Gender", "Birthdate", "Operating system", "Machine", "CPU", "Memory", "GPU", "App"]


def build_core_memory(owner: str = "", env: dict | None = None) -> str:
    """The realm's default core memory: baseline facts every agent should know about the owner
    and the machine ARMADA runs on. Marked `kind: core` so the UI flags it as auto-generated."""
    env = dict(env or {})
    if owner:
        env.setdefault("Owner", owner)
    lines = [f"- {k}: {env[k]}" for k in _CORE_FIELDS if env.get(k)]
    if not lines:
        lines = ["- (Owner and environment are filled in during setup — edit this to add them.)"]
    return ("---\ntitle: Owner & environment\nkind: core\n---\n"
            "Baseline facts every agent should know about the owner and the machine ARMADA runs "
            "on. The owner fields (name, timezone, gender, birthdate) are managed from "
            "Settings → User settings; you can add your own lines below.\n\n" + "\n".join(lines) + "\n")


def seed_core_memory(realm_root, owner: str = "", env: dict | None = None,
                     overwrite: bool = False) -> "Path":
    """Write memory/core-context.md if missing (or overwrite=True). Returns the path."""
    from .util import write_text_atomic
    p = Path(realm_root) / "memory" / "core-context.md"
    if p.exists() and not overwrite:
        return p
    write_text_atomic(p, build_core_memory(owner, env))
    return p


def merge_core_fields(realm_root, fields: dict):
    """Update only the given '- Label: value' bullets in memory/core-context.md, preserving the
    machine facts and any lines the user added by hand (an empty value removes that bullet). This
    is what Settings → User settings calls, so saving there never clobbers manual edits. If the
    file doesn't exist yet, seed a fresh one from `fields`."""
    from .util import write_text_atomic
    p = Path(realm_root) / "memory" / "core-context.md"
    if not p.exists():
        return seed_core_memory(realm_root, owner=str(fields.get("Owner") or ""), env=fields, overwrite=True)
    order = {label: i for i, label in enumerate(_CORE_FIELDS)}

    def field_of(line):
        s = line.lstrip("-•* \t")
        for label in order:
            if s.startswith(label + ":"):
                return label
        return None

    text = p.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    for label, value in fields.items():
        value = str(value).strip() if value is not None else ""
        idx = next((i for i, ln in enumerate(lines) if field_of(ln) == label), None)
        if value:
            new = f"- {label}: {value}"
            if idx is not None:
                lines[idx] = new
            else:  # insert in canonical order (before the first later-ordered field, else after the last bullet)
                my = order.get(label, 999)
                pos = next((i for i, ln in enumerate(lines)
                            if (f := field_of(ln)) is not None and order[f] > my), None)
                if pos is None:
                    last = max((i for i, ln in enumerate(lines) if ln.lstrip().startswith(("- ", "• ", "* "))), default=None)
                    pos = (last + 1) if last is not None else len(lines)
                lines.insert(pos, new)
        elif idx is not None:
            del lines[idx]
    write_text_atomic(p, "\n".join(lines) + "\n")
    return p


def default_env() -> dict:
    """Best-effort environment facts from the standard library (portable; no extra deps)."""
    import platform
    import time as _time
    tz = ""
    try:
        tz = (_time.tzname[_time.localtime().tm_isdst and 1 or 0] or "").strip()
    except Exception:  # noqa
        log.debug('default_env: failed; ignored', exc_info=True)
    osname = f"{platform.system()} {platform.release()}".strip()
    ver = platform.version()
    if ver and ver not in osname:
        osname = f"{osname} ({ver})"
    env = {"Operating system": osname, "Machine": platform.node(),
           "CPU": platform.processor() or f"{__import__('os').cpu_count()} cores"}
    if tz:
        env["Timezone"] = tz
    return env


# --- System memory: a read-only, app-maintained digest of the realm's basics ---------------------
# Loaded into every agent's context (as a realm memory). Regenerated deterministically from the live
# sources — realm.json, agent.json files, the goals module, and a machine probe — so it can't drift
# and never needs hand-editing. Prior versions are snapshotted for debugging.

SYSTEM_MEMORY_FILE = "core-context.md"
_SYS_VERSIONS_DIR = ".system-versions"


def probe_environment() -> dict:
    """Best-effort machine facts (stdlib only, never raises). RAM via a native call; GPU is left to
    carry-forward from the prior digest (no portable probe), so it isn't lost."""
    env = default_env()                              # Operating system, Machine, CPU, Timezone
    try:
        if os.name == "nt":
            import ctypes

            class _MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = _MS(); m.dwLength = ctypes.sizeof(_MS)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                env["Memory"] = f"{round(m.ullTotalPhys / (1024 ** 3))} GB RAM"
        else:
            env["Memory"] = f"{round(os.sysconf('SC_PHYS_PAGES') * os.sysconf('SC_PAGE_SIZE') / (1024 ** 3))} GB RAM"
    except Exception:  # noqa
        log.debug('probe_environment: failed; ignored', exc_info=True)
    env["App"] = "ARMADA (local, http://127.0.0.1:8756)"
    return env


def _parse_bullets(text: str) -> dict:
    """{Key: value} for every '- Key: value' bullet in text (used to carry forward env facts we
    can't re-probe this run, e.g. GPU)."""
    out = {}
    for ln in (text or "").splitlines():
        s = ln.lstrip("-•* \t")
        if ":" in s:
            k, v = s.split(":", 1)
            k, v = k.strip(), v.strip()
            if k and v:
                out[k] = v
    return out


def _load_json_safe(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:  # noqa
        swallowed(log, '_load_json_safe: failed; returning a fallback')
        return {}


def _roster(realm_root: Path) -> list[tuple[str, str, str, bool]]:
    """(display, role, one-liner, is_coordinator) per agent, coordinator first."""
    out = []
    ad = Path(realm_root) / "agents"
    if ad.is_dir():
        for d in sorted(p for p in ad.iterdir() if p.is_dir()):
            c = _load_json_safe(d / "agent.json")
            if not c:
                continue
            one = (c.get("leader") or c.get("bulletin") or "").strip().split("\n")[0][:90]
            out.append((c.get("display") or d.name, c.get("theme_role") or c.get("role") or "",
                        one, bool(c.get("coordinator"))))
    out.sort(key=lambda t: (not t[3], t[0]))         # coordinator first, then by name
    return out


def _goals_glance(realm_root: Path) -> list[str]:
    try:
        from . import goals as _goals
        gs = _goals.list_goals(realm_root)
    except Exception:  # noqa
        swallowed(log, '_goals_glance: failed; returning a fallback')
        return []
    lines = []
    for g in gs:
        owners = ", ".join(o.capitalize() for o in (g.get("agents") or [])) or "unassigned"
        status = (g.get("effective_status") or g.get("status") or "").strip()
        lines.append(f"- {g['title']} — owners: {owners}" + (f" [{status}]" if status else ""))
    return lines


def system_digest(realm_root) -> str:
    """The deterministic managed body (Markdown) — owner, environment, realm identity, roster, goals.
    No timestamp inside, so change-detection compares real content only."""
    realm_root = Path(realm_root)
    cfg = _load_json_safe(realm_root / "realm.json")
    user = cfg.get("user") or {}
    # environment: fresh probe, merged over whatever the prior digest held (keeps GPU etc.)
    prior = ""
    sysf = realm_root / "memory" / SYSTEM_MEMORY_FILE
    if sysf.exists():
        _, prior = _frontmatter(_read(sysf))
    env = {**_parse_bullets(prior), **probe_environment()}
    for stale in ("Owner", "Name", "Timezone", "Gender", "Birthdate"):     # owner facts live below, not in env
        env.pop(stale, None)

    def block(title, lines):
        return f"## {title}\n" + "\n".join(lines) if lines else ""

    owner_lines = [f"- {lbl}: {user[k]}" for lbl, k in
                   (("Name", "name"), ("Gender", "gender"), ("Birthdate", "birthdate"))
                   if str(user.get(k) or "").strip() and user.get(k) != "Prefer not to say"]
    # Free text the owner wrote about themselves — kept verbatim and last in the block, so it
    # reads as their words rather than another generated field.
    about = str(user.get("about") or "").strip()
    if about:
        owner_lines.append("- In their own words:\n" + "\n".join(
            "  " + ln for ln in about.splitlines()))
    env_lines = [f"- {k}: {env[k]}" for k in ("Operating system", "Machine", "CPU", "Memory", "GPU", "App")
                 if env.get(k)]
    roster = _roster(realm_root)
    coord = next((f"{d} — {r}" for d, r, _o, c in roster if c), "")
    realm_lines = [f"- Name: {cfg.get('name') or realm_root.name}"]
    # Timezone is a realm fact — it's what the scheduler runs this realm's jobs against, and two
    # realms on one machine can legitimately differ. It used to sit under Owner.
    tz = str(cfg.get("timezone") or user.get("timezone") or "").strip()
    if tz:
        realm_lines.append(f"- Timezone: {tz}")
    if coord:
        realm_lines.append(f"- Coordinator: {coord}")
    realm_lines.append(f"- Members: {sum(1 for *_x, c in roster if not c)} + 1 coordinator")
    roster_lines = [f"- **{d}**{(' — ' + r) if r else ''}{'  (coordinator)' if c else ''}{(': ' + o) if o else ''}"
                    for d, r, o, c in roster]
    goals = _goals_glance(realm_root)

    intro = ("This is the realm's System memory — auto-maintained by ARMADA and loaded for every agent. "
             "It is read-only: change the source instead (owner facts in Settings → User settings, the "
             "realm's timezone in Settings → Realm settings, goals in the Goals section, agents via "
             "Appoint) and it updates itself. Add your own realm-wide notes as a normal realm memory, "
             "not here.")
    parts = [intro, block("Owner", owner_lines), block("Environment", env_lines),
             block("Realm", realm_lines), block("Cabinet — who's who", roster_lines),
             block("Goals at a glance", goals)]
    return "\n\n".join(p for p in parts if p).strip() + "\n"


def _snapshot_system(realm_root: Path, old_text: str, trigger: str, changed_summary: str) -> None:
    from .util import write_text_atomic
    vd = Path(realm_root) / "memory" / _SYS_VERSIONS_DIR
    vd.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().astimezone()
    stamp = ts.strftime("%Y%m%dT%H%M%S")
    write_text_atomic(vd / f"{Path(SYSTEM_MEMORY_FILE).stem}.{stamp}.md", old_text)
    with (vd / "_ledger.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": ts.isoformat(timespec="seconds"), "trigger": trigger or "manual",
                            "summary": changed_summary}, ensure_ascii=False) + "\n")
    # keep only the most recent 30 snapshots
    snaps = sorted(vd.glob(f"{Path(SYSTEM_MEMORY_FILE).stem}.*.md"))
    for old in snaps[:-30]:
        try:
            old.unlink()
        except OSError:
            pass


def refresh_system_memory(realm_root, trigger: str = "") -> dict:
    """Regenerate the read-only System memory from live sources. Only rewrites (and snapshots the
    prior version) when the substantive content actually changed. Returns {changed, path}."""
    from .util import write_text_atomic, file_lock
    realm_root = Path(realm_root)
    p = realm_root / "memory" / SYSTEM_MEMORY_FILE
    body = system_digest(realm_root)
    old_text = _read(p) if p.exists() else ""
    _, old_body = _frontmatter(old_text)
    if old_text and old_body.strip() == body.strip():
        return {"changed": False, "path": str(p)}
    updated = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    front = (f"---\ntitle: System memory\nkind: system\nmanaged: true\nupdated_by: system\nupdated: {updated}\n---\n")
    new_text = front + body
    with file_lock(p):
        if old_text.strip():
            _snapshot_system(realm_root, old_text, trigger, f"updated ({trigger or 'manual'})")
        write_text_atomic(p, new_text)
    return {"changed": True, "path": str(p)}
