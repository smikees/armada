"""`armada new` — scaffold a ARMADA-native realm from a template (SPEC §12).

Writes the neutral on-disk schema (realm.json, theme.json, objectives.md, tenets.md, and
each agent's folder with agent.json + mandate.md + soul.md). This is the greenfield path;
the read/adopt path (reader.py) handles an existing realm.
"""
from __future__ import annotations
import json, datetime
from pathlib import Path
from .templates import TEMPLATES
from .realmformat import CURRENT as SCHEMA_VERSION  # a new realm is born at the current format
import logging
from .util import swallowed
log = logging.getLogger(__name__)


def scaffold(folder, template_id: str = "scratch", name: str | None = None,
             icon: str | None = None, agents: list | None = None) -> Path:
    if template_id not in TEMPLATES:
        raise SystemExit(f"ARMADA: unknown template '{template_id}' (have: {', '.join(TEMPLATES)})")
    t = TEMPLATES[template_id]
    root = Path(folder)
    if (root / "realm.json").exists() or (root / "cabinet" / "schedule.json").exists():
        raise SystemExit(f"ARMADA: {root} already holds a realm — refusing to overwrite. Use `armada open`.")
    root.mkdir(parents=True, exist_ok=True)

    theme = dict(t["theme"])
    if icon:
        theme["icon"] = icon
    agent_list = agents if agents is not None else t["agents"]
    realm_name = name or f"{theme['collective']}"
    (root / "realm.json").write_text(json.dumps({
        "name": realm_name, "schema_version": SCHEMA_VERSION, "theme_ref": "theme.json",
        "default_engine": "claude", "template": template_id,
        "created": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
    }, indent=2), encoding="utf-8")
    (root / "theme.json").write_text(json.dumps({**theme, "template": template_id}, indent=2,
                                                ensure_ascii=False), encoding="utf-8")
    (root / "objectives.md").write_text(t["objectives"] + "\n", encoding="utf-8")
    (root / "tenets.md").write_text(t["tenets"] + "\n", encoding="utf-8")
    (root / "memory").mkdir(exist_ok=True)
    (root / "shared").mkdir(exist_ok=True)
    # Seed the default "core" memory (owner + environment). The wizard fills in the owner's
    # name; environment is captured now. Marked kind:core so the UI flags it as auto-generated.
    from . import memory as _memory
    _memory.seed_core_memory(root, owner=(name or ""), env=_memory.default_env())

    _today = datetime.date.today().isoformat()
    import re as _re
    for a in agent_list:
        aid = a.get("id") or _re.sub(r"[^a-z0-9]+", "-", a["display"].lower()).strip("-")
        adir = root / "agents" / aid
        adir.mkdir(parents=True, exist_ok=True)
        (adir / "agent.json").write_text(json.dumps({
            "id": aid, "display": a["display"], "role": a.get("role", ""), "leader": a.get("leader", ""),
            "coordinator": bool(a.get("coordinator")), "membership": "cabinet",
            "autonomy": "propose", "model": None, "appointed": _today,
            "mandate": "mandate.md", "soul": "soul.md",
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        (adir / "mandate.md").write_text(a.get("mandate", f"You are {a['display']}.") + "\n", encoding="utf-8")
        (adir / "soul.md").write_text(a.get("voice", theme.get("voice", "")) + "\n", encoding="utf-8")
        (adir / "jobs").mkdir(exist_ok=True)
        (adir / "memory").mkdir(exist_ok=True)
        # skills.json: seed any template-declared skills (pinned + scoped), else an empty manifest.
        (adir / "skills.json").write_text(json.dumps([
            {"id": s["id"], "source": s.get("source", "builtin"),
             "version": s.get("version", "*"), "scopes": list(s.get("scopes", []))}
            for s in a.get("skills", [])
        ], indent=2, ensure_ascii=False), encoding="utf-8")

    from . import skills as _skills
    _skills.lock(root)   # write the initial manifest.lock (empty or seeded)

    # Generate the full read-only System memory now that the agents exist — owner + environment +
    # realm identity + cabinet roster + goals. Without this a freshly scaffolded realm would show
    # only the minimal owner/env seed until some later action (appoint, goal edit, settings save)
    # happened to trigger a refresh. Best-effort: never let it break scaffolding.
    try:
        _memory.refresh_system_memory(root, trigger="realm-created")
    except Exception:  # noqa
        swallowed(log, 'scaffold: failed; ignored')

    print(f"ARMADA: created a '{template_id}' realm → {root}")
    print(f"  {theme['icon']} {realm_name} · {theme['collective']} of {theme['agent']}s "
          f"(coordinator: {theme['coordinator']})")
    n = len(agent_list)
    print(f"  {n} agent{'s' if n != 1 else ''} seeded" + (" — add your own with agents/<id>/" if n == 0 else "")
          + ".  Open it:  armada open \"" + str(root) + "\"")
    return root
