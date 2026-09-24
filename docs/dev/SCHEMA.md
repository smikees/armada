# ARMADA realm — on-disk schema

The contract behind "a realm is a portable, Git-versioned folder." Everything ARMADA reads or
writes lives here; the setup wizard and any importer must produce this layout. Paths are relative
to the realm root. JSON is read tolerant of a BOM (`utf-8-sig`); Markdown is UTF-8.

```
<realm>/
  realm.json            # realm config (below)
  theme.json            # display labels (below)
  objectives.md         # realm north-star (injected into every agent's core)
  tenets.md             # realm guardrails (injected into every agent's core)
  dashboard.json        # dashboard layout/widgets (portable, per-realm)  — see _load_dashboard
  icon.<ext>            # optional uploaded realm icon (else theme.icon Lucide name)
  memory/               # realm-level memories — load for EVERY agent
    core-context.md     #   the auto 'kind: core' owner+environment memory
    <slug>.md           #   manual memories
  goals/                # realm goals
    <slug>.md           #   one goal per file (frontmatter below)
  user/
    avatar.<ext>        # optional owner avatar (shown instead of "You")
  shared/               # artefacts agents write for the owner
  addons/<id>/addon.json  # optional add-ons (data only) — see docs/dev/EXTENSION_POINTS.md
  logs/                 # NOT here — server logs live in ~/.armada/logs/, outside the realm
  agents/<id>/
    agent.json          # agent config (below); <id> is [a-z0-9][a-z0-9_-]*
    mandate.md          # "Role and Mission" (structural)
    soul.md             # "Soul" (character, voice & traits)
    tenets.md           # agent-specific rules (optional)
    avatar.<ext>        # optional uploaded avatar (else generic bust)
    memory/<slug>.md    # private memories — load only for this agent
    jobs/<id>.json      # scheduled/on-demand jobs (below)
    runs/<id>.jsonl     # append-only run reports (tokens, status, ts)
    threads/<name>/
      messages.jsonl    # append-only turns  [{role:user|assistant, ts, content}]
      summary.md        # compaction summary of older turns (optional)
    threads/_meta.json  # per-agent thread order / pinned / unread / titles
    skills.json         # per-agent skill manifest
```

## realm.json
```jsonc
{
  "name": "The Cabinet",              // display name
  "schema_version": 2,                // on-disk format version — see "Format versioning" below
  "owner": "Mihai",                   // kept in sync with user.name; used by reader theme gate
  "template": "state",                // state | company | crew | scratch (drives default labels)
  "default_engine": "claude",
  "provider": "claude",
  "default_model": "Claude Opus 4.8", // agents/threads inherit unless overridden
  "default_effort": "high",
  "timezone": "Europe/Madrid",        // IANA name, or "" = the host OS timezone (scheduler local)
  "grace_minutes": 120,               // a job missed by a reboot still fires within this window
  "user": {                           // owner settings — SOURCE OF TRUTH (Settings → User settings)
    "name": "Mihai", "timezone": "Europe/Madrid", "gender": "", "birthdate": "YYYY-MM-DD"
  },
  "env": {                            // machine facts, captured at setup; merged into core memory
    "Operating system": "...", "Machine": "...", "CPU": "...", "Memory": "...", "GPU": "...", "App": "..."
  },
  "sections": [ { "name": "...", "assets": "...", "entry": "index.html", "url": "..." } ],
  "toolkit": { "connectors": [...], "plugins": [...], "skills": [...] }
}
```

### Format versioning
`schema_version` is an integer, owned by `armada/realmformat.py` (`CURRENT`). `realmformat.migrate()`
walks a realm from its version up to `CURRENT` one registered step at a time (`MIGRATIONS[n]` takes
v`n` to v`n+1`), under the realm.json lock, and runs when a realm is **opened** (server start,
`/switch`, each non-dry-run scheduler pass — memoised on realm.json's mtime) and **imported** (adopting
a folder). New realms are scaffolded at `CURRENT`. Unstamped realms, and the legacy string stamp
`"0.1"` that `armada new` wrote before this existed, count as v0. A realm stamped *newer* than
`CURRENT` is left untouched and reported (adopt shows a warning; `armada validate` warns). A failing
migration is logged and the realm still opens with the tolerant readers.

| version | change |
|---|---|
| 0 → 1 | none — stamps the version (v0.99.38) |
| 1 → 2 | the internal rename `matcap` → `armada` (v0.99.56, ADR-010): command jobs' `-m matcap` → `-m armada`, the realm cache folder `.matcap/` → `.armada/`, and `MATCAP` in `env.App` → `ARMADA` |

Adding a non-additive change to any realm file means: bump `CURRENT`, register the step, add a row
here, and add a test in `tests/test_realm_format.py`. Steps must be idempotent (an interrupted one
reruns from the start).

## theme.json
```jsonc
{ "collective": "Cabinet", "coordinator": "Prime Minister", "agent": "Minister",
  "icon": "landmark", "template": "state", "voice": "..." }
```
Labels default from `template` when omitted (`reader._TYPE_LABELS`): state→Prime Minister/Minister,
company→CEO/Executive, crew→Captain/Mate, else Coordinator/Agent. The label **"Hand"** is private to
the owner's Cabinet (gated in `reader._resolve_theme` on realm name + owner) and never shown to others.

## agents/<id>/agent.json
```jsonc
{ "id": "finance", "display": "Warren", "role": "Minister of Finance",
  "coordinator": false, "autonomy": "manual|auto|skip", "model": null, "effort": null,
  "mandate": "mandate.md", "soul": "soul.md", "appointed": "YYYY-MM-DD", "membership": "cabinet",
  "inbox_frequency": "every run|hourly|daily|manual", "toolkit": { ... } }
```

## agents/<id>/jobs/<id>.json
```jsonc
{ "name": "Daily Brief", "kind": "agent|command", "thread": "main",
  "schedule": "0 9 * * 1-5" | "manual",           // 5-field cron, or "manual"
  "prompt": "..." /* agent */ , "run": "..." /* command */ }
```

## goals/<slug>.md   (frontmatter + description body)
```
---
title: Become proficient in Spanish
status: Not started | On track | At risk | Blocked | Done
target: YYYY-MM-DD            # ETA; a past ETA is shown as "At risk"
agents: warren,ray            # non-coordinator owners; coordinator is always an owner
---
Free-text description.
```

## memory/*.md and agents/<id>/memory/*.md
```
---
title: Lodging preference
kind: core            # only on the auto owner/environment memory; omitted for manual ones
---
Body text (a bullet list for core).
```
Realm memory loads for every agent; agent memory only for that agent. The `kind: core` memory's
owner fields are managed from Settings → User settings (`memory.merge_core_fields`); manual lines
in it are preserved.

## Injected context (memory.assemble_core / _core_sections)
Order, per agent, every run: realm objectives + realm tenets + realm memory + mapped goals +
agent mandate + soul + agent tenets + agent private memory. Thread history (summary + recent
turns) is appended and IS compacted; the core above is re-assembled fresh and never compacted.
