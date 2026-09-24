# `armada/routes/_shared.py`

Shared helpers for the route mixins in armada/routes/.

Module-level functions used by more than one area: the realm registry at ~/.armada/realms.json,
a realm's JSON projection, a job's JSON projection, thread-title heuristics. Plus `SharedRoutes`,
a mixin of handler methods that are themselves genuinely cross-cutting (`_slug`,
`_write_data_image`, `_refresh_system`/`_refresh_system_ep`, `_render_md`) rather than belonging
to one area.

Split out of serve.py (Phase 2, 2.3) — a pure move, no behaviour change.

### `_derive_title(text: str)`

A short thread title from the first prompt (heuristic, no model call): first meaningful line, stripped of markdown/quotes, trimmed to a word boundary, sentence-cased.

### `_llm_title(agent_dir, first_msg: str)`

A concise topic-summary title from a cheap model (haiku), like the Claude app. Best-effort: returns '' on any failure so the caller can fall back to the heuristic.

### `_reg_path()`

—

### `_reg_load()`

—

### `_reg_save(items: list[dict])`

—

### `_reg_rename(path: str, name: str)`

Keep the registry's copy of a realm's name in step with realm.json.

### `_reg_ensure(path: str, name: str)`

—

### `_realm_json(realm)`

—

### `_job_detail(realm_root, agent_id, job_id)`

—

### class `SharedRoutes`

—

- `SharedRoutes._refresh_system_ep(self, body: dict)` — —
- `SharedRoutes._slug(s: str)` — —
- `SharedRoutes._refresh_system(self, trigger: str)` — Regenerate the read-only System memory after a change that affects realm basics. Best-effort — never let it break the triggering action.
- `SharedRoutes._write_data_image(base_no_ext: Path, dataurl: str)` — —
- `SharedRoutes._render_md(self, body: dict)` — Render markdown to HTML. Writes nothing, reads nothing — it exists so the browser can preview unsaved text without a second markdown renderer of its own. Two renderers is how a preview starts quietly disagreeing with the page; this way the preview IS the page's.
