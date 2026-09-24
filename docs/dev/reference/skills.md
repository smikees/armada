# `armada/skills.py`

Skills/connectors provisioning (SPEC §6 / §14) — the manifest layer.

Each agent declares its capabilities in `agents/<id>/skills.json`:
    [{"id", "source", "version", "scopes": [...]}, ...]
Skills are **pinned** (source+version) and **scoped** (files|network|connectors|shell) so
that what an agent can touch is explicit and auditable. A realm-level `manifest.lock`
aggregates every declared skill across agents — the single list a provisioner would install
and the doctor would verify. This module owns reading/writing those files; nothing here runs
a skill (that's the engine's job) — it records intent.

JSON, not YAML: the whole realm on-disk format is JSON (realm.json, agent.json, jobs/*.json),
so skills stay JSON too — zero third-party deps, one format to learn.

### `_read(p: Path)`

—

### `_skills_file(realm_root: Path, agent_id: str)`

—

### `load(realm_root, agent_id: str)`

—

### `save(realm_root, agent_id: str, skills: list[Skill])`

—

### `add(realm_root, agent_id: str, skill_id: str, source: str='builtin', version: str='*', scopes: list[str] | None=None)`

—

### `remove(realm_root, agent_id: str, skill_id: str)`

—

### `lock(realm_root)`

Regenerate manifest.lock — every declared skill across all agents, pinned by source+version.
