"""`armada validate` — is this folder a runnable ARMADA realm, and what's in it?

This is the contract check behind "point ARMADA at a folder and it figures out the realm":
it reports what ARMADA expects (the native spec, SPEC §4), what's present, and what's missing
or malformed — per realm and per job — so an export (e.g. the cabinet) can be verified against
the spec before you try to run it. Errors block running; warnings are advisory.
"""
from __future__ import annotations
import json
from pathlib import Path
from . import scheduler


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8-sig") if p.exists() else ""


def _json(p: Path):
    try:
        return json.loads(_read(p)) if p.exists() else None
    except json.JSONDecodeError as e:
        return e


def validate(folder) -> dict:
    root = Path(folder)
    errors: list[str] = []
    warns: list[str] = []
    info: list[str] = []

    if not root.is_dir():
        return {"ok": False, "errors": [f"{root} is not a folder"], "warnings": [], "info": [], "agents": 0, "jobs": 0}

    # Cabinet-format folder → read-only, not runnable natively.
    if (root / "cabinet" / "schedule.json").exists() and not (root / "realm.json").exists():
        return {"ok": False, "kind": "cabinet",
                "errors": ["This is a cabinet-format folder (cabinet/schedule.json). ARMADA shows it "
                           "read-only in the cockpit but can't run it — export it to a native realm first."],
                "warnings": [], "info": [], "agents": 0, "jobs": 0}

    rj = _json(root / "realm.json")
    if rj is None:
        errors.append("no realm.json — not a native realm (create with `armada new`, or export the cabinet here)")
    elif isinstance(rj, Exception):
        errors.append(f"realm.json is invalid JSON: {rj}")
    else:
        if not rj.get("name"):
            warns.append("realm.json has no 'name'")
        if rj.get("timezone"):
            info.append(f"timezone: {rj['timezone']} · grace: {rj.get('grace_minutes', 120)}m")
        else:
            warns.append("realm.json has no 'timezone' — scheduler will use local time")
        from . import realmformat
        fp = realmformat.plan(rj)
        if fp["newer"]:
            warns.append(f"realm format v{fp['from']} is newer than this ARMADA understands "
                         f"(v{realmformat.CURRENT}) — update ARMADA before editing this realm")
        elif fp["steps"]:
            info.append(f"realm format v{fp['from']} — upgraded to v{realmformat.CURRENT} when next opened")
        else:
            info.append(f"realm format v{fp['from']}")

    for fn in ("theme.json", "objectives.md", "tenets.md"):
        if not (root / fn).exists():
            warns.append(f"missing {fn} (optional, but recommended)")

    adir = root / "agents"
    n_agents = n_jobs = 0
    if not adir.is_dir():
        errors.append("no agents/ folder")
    else:
        agent_dirs = sorted(p for p in adir.iterdir() if p.is_dir())
        if not agent_dirs:
            warns.append("agents/ is empty — no agents defined yet")
        coordinators = 0
        for ad in agent_dirs:
            n_agents += 1
            ac = _json(ad / "agent.json")
            if ac is None:
                errors.append(f"agent '{ad.name}': missing agent.json")
                continue
            if isinstance(ac, Exception):
                errors.append(f"agent '{ad.name}': agent.json invalid JSON: {ac}")
                continue
            if not ac.get("display"):
                warns.append(f"agent '{ad.name}': agent.json has no 'display'")
            if ac.get("coordinator"):
                coordinators += 1
            if not (ad / ac.get("mandate", "mandate.md")).exists():
                warns.append(f"agent '{ad.name}': no mandate.md")
            jdir = ad / "jobs"
            if jdir.is_dir():
                for jf in sorted(jdir.glob("*.json")):
                    n_jobs += 1
                    jc = _json(jf)
                    if isinstance(jc, Exception):
                        errors.append(f"job '{ad.name}/{jf.stem}': invalid JSON: {jc}")
                        continue
                    if not jc:
                        continue
                    is_cmd = jc.get("kind") == "command" or jc.get("run") or jc.get("command")
                    if is_cmd and not (jc.get("run") or jc.get("command")):
                        errors.append(f"job '{ad.name}/{jf.stem}': command job has no 'run'")
                    if not is_cmd and not jc.get("prompt") and not jc.get("prompt_ref"):
                        warns.append(f"job '{ad.name}/{jf.stem}': agent job has no 'prompt'")
                    sched = jc.get("schedule") or jc.get("cron")
                    if sched and sched != "manual":
                        ok_sched = isinstance(sched, str) and (
                            scheduler.is_cron(sched) or scheduler.parse_schedule(sched) is not None)
                        if not ok_sched:
                            warns.append(f"job '{ad.name}/{jf.stem}': unparseable schedule '{sched}'")
        if coordinators == 0 and n_agents:
            info.append("no coordinator flagged (optional)")
        elif coordinators > 1:
            warns.append(f"{coordinators} agents flagged coordinator — usually exactly one")

    ok = not errors
    return {"ok": ok, "kind": "native", "errors": errors, "warnings": warns, "info": info,
            "agents": n_agents, "jobs": n_jobs, "name": (rj or {}).get("name") if isinstance(rj, dict) else None}


def run(folder) -> int:
    r = validate(folder)
    print(f"ARMADA validate · {folder}\n" + "─" * 60)
    if r.get("name"):
        print(f"  realm: {r['name']} · {r['agents']} agents · {r['jobs']} jobs")
    for i in r.get("info", []):
        print(f"  · {i}")
    for w in r.get("warnings", []):
        print(f"  ⚠ {w}")
    for e in r.get("errors", []):
        print(f"  ✗ {e}")
    print("─" * 60)
    print("Valid runnable realm." if r["ok"] else "Not runnable yet — fix the ✗ items.")
    return 0 if r["ok"] else 1
