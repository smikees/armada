"""Skills/connectors provisioning (SPEC §6 / §14) — the manifest layer.

Each agent declares its capabilities in `agents/<id>/skills.json`:
    [{"id", "source", "version", "scopes": [...]}, ...]
Skills are **pinned** (source+version) and **scoped** (files|network|connectors|shell) so
that what an agent can touch is explicit and auditable. A realm-level `manifest.lock`
aggregates every declared skill across agents — the single list a provisioner would install
and the doctor would verify. This module owns reading/writing those files; nothing here runs
a skill (that's the engine's job) — it records intent.

JSON, not YAML: the whole realm on-disk format is JSON (realm.json, agent.json, jobs/*.json),
so skills stay JSON too — zero third-party deps, one format to learn.
"""
from __future__ import annotations
import json, datetime
from pathlib import Path
from .model import Skill

VALID_SCOPES = ("files", "network", "connectors", "shell")


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8-sig") if p.exists() else ""


def _skills_file(realm_root: Path, agent_id: str) -> Path:
    return Path(realm_root) / "agents" / agent_id / "skills.json"


def load(realm_root, agent_id: str) -> list[Skill]:
    raw = _read(_skills_file(Path(realm_root), agent_id))
    if not raw.strip():
        return []
    out = []
    for e in json.loads(raw):
        if isinstance(e, str):                       # tolerate a bare id list
            out.append(Skill(id=e))
        else:
            out.append(Skill(id=e["id"], source=e.get("source", "builtin"),
                             version=e.get("version", "*"), scopes=list(e.get("scopes", []))))
    return out


def save(realm_root, agent_id: str, skills: list[Skill]) -> Path:
    f = _skills_file(Path(realm_root), agent_id)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(
        [{"id": s.id, "source": s.source, "version": s.version, "scopes": s.scopes} for s in skills],
        indent=2, ensure_ascii=False), encoding="utf-8")
    return f


def add(realm_root, agent_id: str, skill_id: str, source: str = "builtin",
        version: str = "*", scopes: list[str] | None = None) -> list[Skill]:
    realm_root = Path(realm_root)
    if not (realm_root / "agents" / agent_id).is_dir():
        raise SystemExit(f"ARMADA: no agent '{agent_id}' in {realm_root}")
    scopes = scopes or []
    bad = [s for s in scopes if s not in VALID_SCOPES]
    if bad:
        raise SystemExit(f"ARMADA: unknown scope(s) {bad} — valid: {', '.join(VALID_SCOPES)}")
    skills = [s for s in load(realm_root, agent_id) if s.id != skill_id]   # replace if present
    skills.append(Skill(id=skill_id, source=source, version=version, scopes=scopes))
    skills.sort(key=lambda s: s.id)
    save(realm_root, agent_id, skills)
    lock(realm_root)
    return skills


def remove(realm_root, agent_id: str, skill_id: str) -> list[Skill]:
    realm_root = Path(realm_root)
    skills = [s for s in load(realm_root, agent_id) if s.id != skill_id]
    save(realm_root, agent_id, skills)
    lock(realm_root)
    return skills


def lock(realm_root) -> Path:
    """Regenerate manifest.lock — every declared skill across all agents, pinned by source+version."""
    realm_root = Path(realm_root)
    adir = realm_root / "agents"
    entries: dict[tuple[str, str, str], set] = {}     # (id, source, version) -> {agents}
    for ad in (sorted(p for p in adir.iterdir() if p.is_dir()) if adir.is_dir() else []):
        for s in load(realm_root, ad.name):
            entries.setdefault((s.id, s.source, s.version), set()).add(ad.name)
    locked = [{"id": i, "source": src, "version": v, "used_by": sorted(who)}
              for (i, src, v), who in sorted(entries.items())]
    unpinned = [e["id"] for e in locked if e["version"] == "*"]
    doc = {
        "generated": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "skills": locked,
        "warnings": ([f"{len(unpinned)} unpinned skill(s): {', '.join(unpinned)}"] if unpinned else []),
    }
    f = realm_root / "manifest.lock"
    f.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    return f
