# `armada/memory.py`

Layered memory + always-on core assembly (SPEC §5).

The core is what ARMADA injects into EVERY run for an agent, from files, never compacted:
  realm objectives + realm tenets + realm memory (known to all)
  + the agent's mandate + soul + tenets + its OWN private memory (scoped to it).

Realm memory loads for every agent; agent memory loads only for that agent — "everyone
knows the owner's name; only Travel knows he prefers hotels." Thread history is separate
(threads.py) and IS subject to compaction; the core here is always re-assembled fresh.

### `_read(p: Path)`

—

### `_mission_framing(text: str)`

The realm's North Star FRAMING only — title, mandate/guardrails, and the meta-objective — with the per-goal enumeration stripped out. Every agent shares the framing, but each agent's actual goals are injected SCOPED to it (goals_for_agent), so no one carries all nine. We cut at the first section heading that isn't 'Meta' (where the goal listing begins); if the doc isn't structured that way, it's kept whole.

### `_frontmatter(text: str)`

—

### `_memories(mem_dir: Path)`

—

### `_core_sections(realm_root, agent_dir, agent: dict)`

The always-on core, as ordered (bucket, text) sections. `bucket` groups sections for the 'Loaded context' breakdown: 'mission' (objectives/tenets/mandate/soul), 'realm_memory', 'goals', 'agent_memory'. This is the SINGLE source of truth — assemble_core() joins these into the prompt and core_breakdown() sizes them, so the UI can't drift from what's injected.

### `assemble_core(realm_root, agent_dir, agent: dict)`

—

### `core_breakdown(realm_root, agent_dir, agent: dict)`

Char counts per context bucket (mission / goals / realm_memory / agent_memory), measured on the exact section text that assemble_core() puts into the prompt.

### `core_stats(realm_root, agent_dir, agent: dict)`

—

### `build_core_memory(owner: str='', env: dict | None=None)`

The realm's default core memory: baseline facts every agent should know about the owner and the machine ARMADA runs on. Marked `kind: core` so the UI flags it as auto-generated.

### `seed_core_memory(realm_root, owner: str='', env: dict | None=None, overwrite: bool=False)`

Write memory/core-context.md if missing (or overwrite=True). Returns the path.

### `merge_core_fields(realm_root, fields: dict)`

Update only the given '- Label: value' bullets in memory/core-context.md, preserving the machine facts and any lines the user added by hand (an empty value removes that bullet). This is what Settings → User settings calls, so saving there never clobbers manual edits. If the file doesn't exist yet, seed a fresh one from `fields`.

### `default_env()`

Best-effort environment facts from the standard library (portable; no extra deps).

### `probe_environment()`

Best-effort machine facts (stdlib only, never raises). RAM via a native call; GPU is left to carry-forward from the prior digest (no portable probe), so it isn't lost.

### `_parse_bullets(text: str)`

{Key: value} for every '- Key: value' bullet in text (used to carry forward env facts we can't re-probe this run, e.g. GPU).

### `_load_json_safe(p: Path)`

—

### `_roster(realm_root: Path)`

(display, role, one-liner, is_coordinator) per agent, coordinator first.

### `_goals_glance(realm_root: Path)`

—

### `system_digest(realm_root)`

The deterministic managed body (Markdown) — owner, environment, realm identity, roster, goals. No timestamp inside, so change-detection compares real content only.

### `_snapshot_system(realm_root: Path, old_text: str, trigger: str, changed_summary: str)`

—

### `refresh_system_memory(realm_root, trigger: str='')`

Regenerate the read-only System memory from live sources. Only rewrites (and snapshots the prior version) when the substantive content actually changed. Returns {changed, path}.
