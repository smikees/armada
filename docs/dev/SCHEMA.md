# ARMADA realm — on-disk schema

Provider selection: `realm.json.providers` is an optional list containing any combination
of `claude`, `codex` and `gemini`, controlling the combined model picker. The job's
`model` overrides the agent's `model`, which overrides `default_model`; the model determines
which CLI runs. Existing Claude IDs/labels remain valid. OpenAI IDs (for example an ID from the
local Codex catalogue) select Codex; `codex:default` follows the Codex CLI default. The legacy
`provider`/`default_engine` fields are fallback selectors. This is additive; no migration of
existing realm or agent files is required. New-team defaults depend on connected engines.
See [Provider onboarding](PROVIDER_ONBOARDING.md).

The contract behind "a realm is a portable, Git-versioned folder." Everything ARMADA reads or
writes lives here; the setup wizard and any importer must produce this layout. Paths are relative
to the realm root. JSON is read tolerant of a BOM (`utf-8-sig`); Markdown is UTF-8.

Mutation reads are strict. Newer schemas remain read-only and corrupt state is preserved;
see [Shared state and recovery](PERSISTENCE.md) for locks, writer rules and recovery procedures.

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
      .history-revision # opaque generation changed by compaction/truncation (optional until first rewrite)
      .history-transaction.json # pending schema-1 before/after journal; retain for crash recovery
    threads/_meta.json  # per-agent thread order / pinned / unread / titles
    skills.json         # per-agent skill manifest
```

Thread history rewrites are recoverable transactions; the messages-file lock also protects the
summary and revision. Readers/writers finish a pending journal before using the files. Preserve
the hidden journal when backing up or restoring an interrupted thread; see
[Shared state and recovery](PERSISTENCE.md). Ordinary appends do not change the revision.

## realm.json
```jsonc
{
  "name": "Example team",             // display name
  "schema_version": 2,                // on-disk format version — see "Format versioning" below
  "owner": "Morgan",                  // kept in sync with user.name
  "template": "state",                // state | company | crew | scratch (drives default labels)
  "default_engine": "claude",
  "provider": "claude",
  "default_model": "claude:default", // example only; codex:default and gemini:default are also supported
  "default_effort": "high",
  "timezone": "Europe/Madrid",        // IANA name, or "" = the host OS timezone (scheduler local)
  "grace_minutes": 120,               // a job missed by a reboot still fires within this window
  "user": {                           // owner settings — SOURCE OF TRUTH (Settings → User settings)
    "name": "Morgan", "timezone": "Europe/London", "gender": "", "birthdate": "YYYY-MM-DD"
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
company→CEO/Executive, crew→Captain/Mate, else Coordinator/Agent. Existing legacy
labels remain supported by the reader's compatibility handling.

## agents/<id>/agent.json
```jsonc
{ "id": "research", "display": "Research", "role": "Research specialist",
  "coordinator": false, "autonomy": "manual|auto|skip", "model": null, "effort": null,
  "is_inspector": false,                 // optional; also requires owner approval on this machine
  "mandate": "mandate.md", "soul": "soul.md", "appointed": "YYYY-MM-DD", "membership": "cabinet",
  "inbox_frequency": "every run|hourly|daily|manual", "toolkit": { ... } }
```

## agents/<id>/jobs/<id>.json
```jsonc
{ "name": "Daily Brief", "kind": "agent|command", "thread": "main",
  "schedule": "0 9 * * 1-5" | "manual",           // 5-field cron, or "manual"
  "prompt": "..." /* agent */ , "run": "..." /* command */,
  "dry_run_keep_days": 7,                // optional; 1–365; copied into new dry runs
  "dry_run_command": "" }                // command jobs only; explicit owner-approved draft command
```

### Dry-run runtime (additive, no migration)

`.armada/dry-runs/<agent>/<job>/<run-id>/` stores `job.json` (configuration snapshot),
`run.json` (schema_version 1, identity, model, requested_by, status, UTC started/finished,
owner_pid, keep_days, output_dir, usage and result), `transcript.json`, and `output/`
draft artifacts including host-written `final-answer.md`. Optional raw tool capture and
its index stay within this test tree. `stop.json` is a durable cancellation request.
Accounting rows use `kind: dry_run` and `task: dryrun:<job>`, separate from production
job history. Housekeeping removes expired terminal trees, skipping active owned runs.

Machine-local app configuration holds `inspectors` keyed by canonical realm/agent
identity and `dry_run_commands` keyed by realm/agent/job with a command-definition
fingerprint. Portable JSON alone cannot grant these authorities.
See [dry-run boundaries](ADR_014_DRY_RUNS.md) and [Jobs](../../armada/docs/user/jobs.md).

## Scheduler runtime and admission state

Model-turn `tokens.input`, `tokens.output`, `tokens.total` and `tokens.api_equiv_usd` may be JSON
null when the provider did not supply them. Explicit numeric zeros remain valid. Missing cost
makes aggregate cost unavailable; old numeric records are not rewritten. All model-turn paths
persist through the [shared execution coordinator](EXECUTION_CONTRACTS.md).

Interactive chat markers use `agents/<id>/runs/.running/_chat-<run_id>.json`, containing `kind`,
`owner_pid`, `thread`, `run_id` and `realm_id`. Each active run owns its own marker; legacy
`_chat.json` remains readable. Normal chat and agent-job telemetry rows add `realm_id` and
`run_id`. These additive fields need no format migration. Realm identity derives from the
canonical folder path, not a new `realm.json` field; see [REQUEST_CONTEXT.md](REQUEST_CONTEXT.md).
If deleting a completed interactive marker fails, it can remain with `status: finished`; the UI
ignores that marker. Interrupted model-turn messages and normal run reports retain partial output
with `status: error` or `status: stopped`. These are terminal outcomes, never successful turns.

`scheduler.lock.json` contains `schema_version: 1`, `pid`, `started` (UTC ISO timestamp), and a
unique `owner_token`. It is metadata; the stable `.scheduler.lock.json.lock` holds the actual
OS lock. Never delete that hidden file to resolve contention.

`.scheduler/attempts/YYYY-MM-DD.json` contains `schema_version: 1` and an `attempts` object
keyed by a hash of `[agent, job]`. Each entry contains `agent`, `job`, `day` (realm-local),
`attempt_id`, `owner_token`, `started`, and `state` (`claimed` or `finished`). Finished entries
also carry `status` and `finished`. This preserves one automatic attempt per job/day, including
cron schedules matching multiple minutes. Unfinished claims are not automatically replayed.

`system_jobs.json` retains its per-job map and adds an `attempt` object containing `attempt_id`,
`started` and `state`; completion adds `status` and `finished`. An explicit manual retry of an
interrupted job adds `retry_of` and retains the previous entry in bounded `interrupted_attempts`.
Per-job OS locks under `.scheduler/system/` exclude concurrent manual/scheduled execution.
System-job entries and completed attempts also carry a `reason` code. A completed check can be
`skipped`, including provider sign-out; history preserves that status without counting it as a
success or failure. See [PROVIDER_UPKEEP.md](PROVIDER_UPKEEP.md) for result and retry semantics.
These admission records are durable realm data, not disposable caches. See
[PERSISTENCE.md](PERSISTENCE.md) for recovery and the limits of external-side-effect guarantees.

## goals/<slug>.md   (frontmatter + description body)
```
---
title: Become proficient in Spanish
status: Not started | On track | At risk | Blocked | Done
target: YYYY-MM-DD            # ETA; a past ETA is shown as "At risk"
agents: research,planning    # non-coordinator owners; coordinator is always an owner
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
