"""ARMADA realm reader — adopts a realm folder into the model.

v0.1 speaks two dialects:
  * ARMADA-native (the neutral schema in SPEC.md §4) — future.
  * The reference cabinet (D:\\Work\\Hand) — the brownfield test fixture: it maps
    schedule.json + <minister>.md bulletins + runs/*.jsonl into the ARMADA model.

Reading a realth this way is exactly the "Adopt an existing setup" path from the
setup flow, and it doubles as a schema-validation exercise: whatever the cabinet
does NOT yet declare (skills, token usage) surfaces as a Gap, not a silent blank.
"""
from __future__ import annotations
import json, re, datetime
from pathlib import Path
from .model import Realm, Agent, Job, Gap
from . import status as _status


def _read(p: Path) -> str:
    try:
        return p.read_bytes().decode("utf-8-sig", "replace")
    except OSError:
        return ""


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


def _first_headline(body: str, limit: int = 220) -> str:
    for raw in body.splitlines():
        s = raw.strip().lstrip("#-* ").strip()
        if s and not s.startswith("##"):
            return (s[:limit] + "…") if len(s) > limit else s
    return ""


def is_cabinet(root: Path) -> bool:
    return (root / "cabinet" / "schedule.json").exists()


def read_cabinet(root: Path) -> Realm:
    cab = root / "cabinet"
    cfg = json.loads(_read(cab / "schedule.json") or "{}")
    now = datetime.datetime.now().astimezone()
    realm = Realm(
        name="The Cabinet", root=str(root),
        theme_collective="Cabinet", theme_agent="Minister", theme_coordinator="Hand",
        engine="Claude (Max subscription)",
        generated_at=now.strftime("%A %d %B %Y, %H:%M"),
    )

    # --- run-reports: latest status per task id + 30-day counts per minister ---
    lo = (now.date() - datetime.timedelta(days=30)).isoformat()
    latest: dict[str, tuple[str, str]] = {}     # task -> (iso_ts, status)
    count30: dict[str, int] = {}                # minister -> runs in last 30d
    tok30: dict[str, int] = {}                  # minister -> tokens in last 30d (when logged)
    runs_dir = cab / "runs"
    if runs_dir.is_dir():
        for jf in runs_dir.glob("*.jsonl"):
            mid = jf.stem
            for ln in _read(jf).splitlines():
                ln = ln.strip().lstrip("\ufeff")
                if not ln:
                    continue
                try:
                    ev = json.loads(ln)
                except json.JSONDecodeError:
                    continue
                ts = str(ev.get("ts", ""))[:19]
                day = ts[:10]
                tid = ev.get("task")
                if tid and (tid not in latest or ts > latest[tid][0]):
                    latest[tid] = (ts, str(ev.get("status", "ok")))
                if len(day) == 10 and day >= lo:
                    count30[mid] = count30.get(mid, 0) + 1
                    tk = ev.get("tokens")
                    if isinstance(tk, dict):
                        tok30[mid] = tok30.get(mid, 0) + int(tk.get("total", 0) or 0)

    def cadence(t: dict) -> str:
        return f"{t.get('days','daily')} {t.get('time','')}".strip()

    # --- ministers -> agents ---
    for mc in cfg.get("ministers", []):
        mid = mc["id"]
        is_coord = mid == "hand"
        a = Agent(
            id=mid, display=mc.get("display", mid.title()),
            leader=mc.get("leader", ""), theme_role="Hand" if is_coord else "Minister",
            is_coordinator=is_coord, placeholder=mc.get("placeholder", ""),
            runs_30d=count30.get(mid, 0), tokens_30d=tok30.get(mid, 0),
        )
        if mc.get("bulletin"):
            meta, body = _frontmatter(_read(cab / mc["bulletin"]))
            a.status = meta.get("status", "unknown")
            a.last_run = meta.get("last_run", "")
            a.goal_metric = meta.get("goal_metric", "")
            a.bulletin = _first_headline(body)
        elif a.placeholder:
            a.status = "planned"
        realm.agents.append(a)

    # The coordinator (the Hand / Marcus) isn't in the ministers[] list — synthesize it so
    # its cross-cutting jobs (the daily brief, the weekly realm) have an owner.
    if "hand" not in {a.id for a in realm.agents}:
        realm.agents.insert(0, Agent(
            id="hand", display="Marcus (PM)", leader="after Marcus Agrippa",
            theme_role="Hand", is_coordinator=True, status="green",
            bulletin="Coordinates the realm — runs the daily brief and the weekly State of the Realm; "
                     "handles cross-cutting matters. Never executes trades or moves money.",
            runs_30d=count30.get("hand", 0), tokens_30d=tok30.get("hand", 0)))

    # --- jobs -> attach to owning agent ---
    by_id = {a.id: a for a in realm.agents}
    for t in cfg.get("tasks", []):
        owner = t.get("minister") or ("hand" if t.get("id", "").startswith("marcus") else None)
        a = by_id.get(owner)
        if not a:
            continue
        rid = t.get("report_task") or t["id"]
        seen = latest.get(rid)
        a.jobs.append(Job(
            id=t["id"], name=t.get("name", t["id"]), cadence=cadence(t),
            summary=str(t.get("summary") or ""),
            report_task=t.get("report_task"),
            last_status=(seen[1] if seen else None),
            last_seen=(seen[0][:10] if seen else None),
        ))

    # --- gaps (what ARMADA would formalize) ---
    n_agents = len(realm.members)
    realm.gaps.append(Gap("info", f"{n_agents} agents, {sum(len(a.jobs) for a in realm.agents)} jobs registered."))
    if all(not a.skills for a in realm.agents):
        realm.gaps.append(Gap("warn", "No agent declares its skills/connectors yet — ARMADA would pin these in a per-agent manifest (SPEC §4)."))
    realm.gaps.append(Gap("warn", "Cabinet run-reports don't yet carry token usage — the ARMADA runner (P2) now logs tokens/cost per run, so per-agent Tokens populate as jobs run through ARMADA (SPEC §10)."))
    planned = [a.display for a in realm.members if a.placeholder]
    if planned:
        realm.gaps.append(Gap("info", "Planned (not yet established): " + ", ".join(planned) + "."))
    return realm


# Default display labels per realm type (coordinator, agent, collective). theme.json may
# override any of them; if it doesn't, the type default applies so labels always read right
# for the realm's kind (a company gets CEO/Executive, a state gets Prime Minister/Minister…).
_TYPE_LABELS = {
    "state":   ("Prime Minister", "Minister",  "Cabinet"),
    "company": ("CEO",            "Executive", "Company"),
    "crew":    ("Captain",        "Mate",      "Crew"),
}
_DEFAULT_LABELS = ("Coordinator", "Agent", "Realm")


def _resolve_theme(cfg: dict, theme: dict) -> tuple[str, str, str]:
    """Coordinator / agent / collective display labels for a realm.

    'Hand' is a private label reserved for the owner's personal Cabinet — it is NEVER shown to
    other users: it only applies when the realm is 'The Cabinet' AND owned by Mihai, and any
    stray 'Hand' in some other realm's theme falls back to the type default.
    """
    tmpl = str(cfg.get("template") or theme.get("template") or "scratch").lower()
    d_coord, d_agent, d_coll = _TYPE_LABELS.get(tmpl, _DEFAULT_LABELS)
    coord = theme.get("coordinator") or d_coord
    agent = theme.get("agent") or d_agent
    coll = theme.get("collective") or d_coll
    private_hand = (cfg.get("name") == "The Cabinet"
                    and str(cfg.get("owner", "")).strip().lower() == "mihai")
    if private_hand:
        coord = "Hand"
    elif coord == "Hand":
        coord = d_coord
    return coord, agent, coll


def read_native(root: Path) -> Realm:
    """Read a ARMADA-native realm (realm.json + theme.json + agents/*) — the greenfield format."""
    now = datetime.datetime.now().astimezone()
    cfg = json.loads(_read(root / "realm.json") or "{}")
    theme = json.loads(_read(root / "theme.json") or "{}")
    _coord, _agent, _coll = _resolve_theme(cfg, theme)
    realm = Realm(
        name=cfg.get("name", "Realm"), root=str(root),
        theme_collective=_coll,
        theme_agent=_agent,
        theme_coordinator=_coord,
        theme_icon=theme.get("icon", "🏛️"),
        engine=(cfg.get("default_engine", "claude").title() + " (subscription)"),
        generated_at=now.strftime("%A %d %B %Y, %H:%M"),
        sections=cfg.get("sections", []),
    )
    lo = (now.date() - datetime.timedelta(days=30)).isoformat()
    # The usage epoch is a clean-slate cutoff: runs before it stay on disk (job history and the
    # calendar still need them) but are excluded from USAGE totals. The Usage widget and the
    # Overview header honour it; this reader did not, so the Register's per-agent "TOK / 30D"
    # column and the header's "Tokens /30d" were computed over different windows and disagreed by
    # more than 2x on the same screen. One cutoff everywhere, or the label is a lie.
    _epoch = str(cfg.get("usage_epoch") or "")
    if _epoch > lo:
        lo = _epoch
    adir_root = root / "agents"
    for adir in (sorted(p for p in adir_root.iterdir() if p.is_dir()) if adir_root.is_dir() else []):
        c = json.loads(_read(adir / "agent.json") or "{}")
        aid = c.get("id", adir.name)
        latest: dict[str, tuple[str, str]] = {}
        count30 = tok30 = 0
        cost30 = 0.0
        rf = adir / "runs" / f"{aid}.jsonl"
        if rf.exists():
            for ln in _read(rf).splitlines():
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    ev = json.loads(ln)
                except json.JSONDecodeError:
                    continue
                ts = str(ev.get("ts", ""))[:19]
                tid = ev.get("task")
                if tid and (tid not in latest or ts > latest[tid][0]):
                    latest[tid] = (ts, str(ev.get("status", "ok")))
                if len(ts[:10]) == 10 and ts[:10] >= lo:
                    count30 += 1
                    tk = ev.get("tokens")
                    if isinstance(tk, dict):
                        tok30 += int(tk.get("total", 0) or 0)
                        cost30 += float(tk.get("api_equiv_usd", 0) or 0)
        status = "unknown"
        if latest:
            s = max(latest.values(), key=lambda x: x[0])[1]
            status = {_status.SUCCESS: "green", _status.QUIET: "green",
                      _status.WARN: "yellow", _status.FAILED: "red"}.get(_status.normalize(s), "unknown")
        mandate = _read(adir / c.get("mandate", "mandate.md"))
        from . import skills as skills_mod
        is_coord = bool(c.get("coordinator"))
        role = c.get("role") or (realm.theme_coordinator if is_coord else realm.theme_agent)
        appointed = c.get("appointed") or c.get("created") or ""
        if not appointed:
            try:
                appointed = datetime.date.fromtimestamp((adir / "agent.json").stat().st_mtime).isoformat()
            except OSError:
                appointed = ""
        a = Agent(id=aid, display=c.get("display", aid.title()), leader=c.get("leader", ""),
                  theme_role=role, is_coordinator=is_coord, membership=c.get("membership", "cabinet"),
                  status=status, bulletin=_first_headline(mandate),
                  runs_30d=count30, tokens_30d=tok30, cost_30d=round(cost30, 4), appointed=appointed,
                  skills=skills_mod.load(root, aid))
        jdir = adir / "jobs"
        if jdir.is_dir():
            for jf in sorted(jdir.glob("*.json")):
                jc = json.loads(_read(jf) or "{}")
                jid = jc.get("id", jf.stem)
                seen = latest.get(jid)
                kind = jc.get("kind") or ("command" if (jc.get("run") or jc.get("command")) else "agent")
                cadence = jc.get("schedule") or jc.get("cron") or "manual"
                a.jobs.append(Job(id=jid, name=jc.get("name", jid), cadence=cadence,
                                  summary=str(jc.get("summary") or ""),
                                  # absent means on: a job written before the toggle existed, or by
                                  # hand, should run rather than silently sit there switched off
                                  enabled=jc.get("enabled", True) is not False,
                                  kind=kind,
                                  last_status=(seen[1] if seen else None),
                                  last_seen=(seen[0][:10] if seen else None)))
        realm.agents.append(a)

    realm.gaps.append(Gap("info", f"{len(realm.members)} agents, {sum(len(a.jobs) for a in realm.agents)} jobs."))
    if not any(a.jobs for a in realm.agents):
        realm.gaps.append(Gap("info", "No jobs yet — add agents/<id>/jobs/<job>.json to schedule work."))
    n_sk = sum(len(a.skills) for a in realm.agents)
    unpinned = [f"{a.display}:{s.id}" for a in realm.agents for s in a.skills if s.version == "*"]
    if n_sk == 0:
        realm.gaps.append(Gap("info", "No skills declared yet — `armada skills add <agent> <id> --version --scope` to provision (SPEC §6)."))
    else:
        realm.gaps.append(Gap("info", f"{n_sk} skill(s) declared across agents; manifest.lock pins them by source+version."))
    if unpinned:
        realm.gaps.append(Gap("warn", "Unpinned skills (version '*'): " + ", ".join(unpinned) + " — pin a version for reproducibility."))
    if realm.cost_30d:
        realm.gaps.append(Gap("info", f"Usage (30d): {realm.tokens_30d:,} tokens · api-equiv ${realm.cost_30d:.2f} "
                                      f"(subscription quota — not a $ charge)."))
    realm.gaps.append(Gap("info", "ARMADA-native realm — themed via theme.json; portable and re-themeable."))
    return realm


def order_agents(realm: Realm) -> Realm:
    """Coordinators first, then everyone else; alphabetical by display name within each group.

    Sorted once, here, because every list in the app reads realm.agents or realm.members and they
    should all agree. Ordering them per page is how the Ministers grid ended up leading with the
    coordinator while the Memory sidebar and the capability roster listed by folder name — three
    views of one cabinet, three different orders, and nothing to point at as the right one.

    By display name rather than id: the id is a folder ('hand', 'development'), the display name is
    what the reader is looking at ('Marcus', 'Steve'). Case-folded so casing can't scatter the list.
    """
    realm.agents.sort(key=lambda a: (not a.is_coordinator, (a.display or a.id).casefold()))
    return realm


def read(root: str | Path) -> Realm:
    root = Path(root)
    if is_cabinet(root):
        return order_agents(read_cabinet(root))
    if (root / "realm.json").exists():
        return order_agents(read_native(root))
    raise SystemExit(f"ARMADA: no realm at {root} (expected cabinet/schedule.json or realm.json). "
                     f"Create one with `armada new`.")
