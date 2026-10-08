# ARMADA — architecture

**Current implementation (October 2026).** The engine seam now supports Claude Code, Codex CLI
and Gemini through Antigravity CLI. Provider discovery and authentication use Windows-installed
CLIs; the desktop launcher starts independently of provider desktop apps. Jobs persist execution,
audit outcome and delivery against individual runs, with bounded retries and run-specific evidence.
See [Gemini](../../armada/docs/user/gemini.md), [jobs](../../armada/docs/user/jobs.md), and the
generated [module reference](reference/index.md) for the current implementation. Dated sections
below retain their original context; the single-engine description is historical.

*Phase 2, step 2.10 — the doc that comes out of the architecture phase. Written 2026-09-24 against
v0.99.40. Feeds Phase 3 (`docs/dev/`). Keep it short; when it and the code disagree, the code wins
and this gets fixed.*

**2026-09-26 follow-up:** the working-tree review found gaps in the locking, memory protection,
run lifecycle and content-boundary guarantees described here. See
[`ARCHITECTURE_REVIEW_2026-09-26.md`](ARCHITECTURE_REVIEW_2026-09-26.md) for verified findings and
launch-plan 2.11–2.21 for the required work. Provider behavior now also includes
[`CODEX_INTEGRATION.md`](CODEX_INTEGRATION.md); the Claude-only passages below are historical.

**2026-09-27:** content boundaries (2.11), capability admission (2.12), exclusive shared-file
mutations (2.13), scheduler claims (2.14), destructive memory rollback (2.15) and compaction (2.16) are repaired in
source. See [Shared state and recovery](PERSISTENCE.md) for locks and durable claims and
[Memory boundaries](MEMORY_BOUNDARIES.md) for provider restrictions and non-destructive audits.
Thread compaction now validates its snapshot, retains concurrent appends and uses a recoverable
summary/log transaction; the model call runs outside the lock.

Read with: [`SCHEMA.md`](SCHEMA.md) (the realm on disk), [`ENGINE_SEAM_AUDIT.md`](ENGINE_SEAM_AUDIT.md)
(what assumes Claude), [`EXTENSION_POINTS.md`](EXTENSION_POINTS.md) (add-ons),
[`DESIGN_TOKENS.md`](DESIGN_TOKENS.md) (CSS), and the ADRs in [`adr/`](../adr/).

---

## 1. What runs

ARMADA is a local, single-user app over a folder. One desktop/server owner per Windows account, plus its owned scheduler service:

```
ARMADA.exe ─► armada app ─► app.py (pywebview window)
                              └─ thread: serve.serve()  ── HTTP on 127.0.0.1:8756
                                   + thread: ContentHandler ── 127.0.0.1:8757, untrusted pages only (5.8a)
                                   Handler = route tables (serve.py) + mixins (routes/*)
                                   GET  → reader.read(realm) → webui.render_*() → HTML
                                   POST → routes/* → realm files (locked, atomic)
                                   chat → routes/agents._chat_stream → runner.chat_stream → TurnCoordinator → engine (SSE)

SCHEDULER.vbs ─┐
app.py launch ─┴► armada schedule ─► scheduler.run_daemon()   (windowless pythonw, detached)
  (schedsvc.ensure_running)          every 60 s, for EVERY registered realm (rescanned each pass):
                                       realmformat.ensure → preflight hold? → sysjobs.run_due
                                       → due jobs → runner.run_job → engine.run → run report
                                     thread: telegram.listen (active realm only)
```

- **The server** selects a default realm (`Handler.realm`; `/switch` moves it and
  `activerealm` remembers it on the machine). Each request captures an immutable destination;
  in-flight turns and explicitly bound content retain their original realm. Stale-page mutations
  are rejected. See [request and run identity](REQUEST_CONTEXT.md). Installed updates use signed packages and the stable recovery bootstrap; development
  checkouts use Git. The account-wide `instance` lock covers all realms and ports.
- **The scheduler** is separate on purpose: a realm's jobs don't pause because you're looking at
  another one, or because the window is hidden in the tray. Full quit stops the owned scheduler. It holds an exclusive per-realm OS lease, with
  PID/token metadata in `scheduler.lock.json`. Durable daily claims prevent automatic replay
  after a crash (2.14). That lease is also how the app knows it's running
  (`schedsvc.status`): the window starts it on launch if not, and `schedbar.js` shows a bar on
  every page when it's down and the realm has scheduled jobs (5.5).
- **The engine** is a subprocess per turn: Claude Code via `engine/claude.py` or Codex CLI via
  `engine/codex.py`, or Antigravity via `engine/gemini.py`. ARMADA assembles
  the whole system prompt itself; the CLI supplies tools, MCP servers, skills and plugins.
  All agent model turns share the [turn coordinator](EXECUTION_CONTRACTS.md).
  Provider model turns share `engine/process.py` for deadlines, bounded pipe handling and
  process-tree ownership; each adapter retains its protocol parser. See [CLI turn lifecycle](PROCESS_LIFECYCLE.md).
- **Logs** go to `~/.armada/logs/` — `armada.log` (server), `scheduler.log` (scheduler).

## 2. Module map

Arrows point down: a module may import from the layers below it, not above.

```
entry        cli.py · __main__.py · app.py · serve.py (route tables, dispatch, restart)
             scheduler.py (tick, daemon, lock) · telegram.py (listener)
────────────────────────────────────────────────────────────────────────────────────────
http         routes/  realm · agents · jobs · caps · catalogue · settings · dashboard · _shared
             (mixins on serve.Handler; one file per area — 2.3)
────────────────────────────────────────────────────────────────────────────────────────
render       webui/   pages (render_* entrypoints) → _core (composition) →
                      L2: layout · widgets · threadsview · capabilities · catalogue · goalsview ·
                          memoryview · realmpages · agentframe · agentcommon · changelog
                      L1: agentbits · consumption · schedfmt
                      L0: _base (escaping, safe markdown, field styles)
             webui/static/  brand.css · industry.css · js/*.js (63 files, via assets.js())
             render.py — the legacy static cockpit.html (`armada open`)
────────────────────────────────────────────────────────────────────────────────────────
execution    runner.py (compatibility entry points and context/capture helpers)
             execution.py (TurnCoordinator · RunSession: admission → progress → terminal persistence)
             thread_metadata.py (read/unread/last-thread persistence)
             memory_boundary.py (provider file-tool rules · bounded observation, never rollback)
             engine/ (contracts · base · claude · codex · gemini · mock — typed provider seam)
             sysjobs.py · sysskills.py + system_skills/ · inbox.py (agent → agent)
             capscan.py · catalogue/ (_shared · sources · realm) · models.py · usage_api.py · auth.py
────────────────────────────────────────────────────────────────────────────────────────
domain       reader.py → model.py (Realm/Agent/Job dataclasses — the in-memory view)
             memory · goals · jobs (proposals) · threads · capabilities (the grant rule)
             thread_store (coherent history reads · append · journaled compaction/truncation)
             skills · agentops · realmops · workspace · approot · realmformat · addons
             notify · status · clock · verbosity · vtheme · templates · setup
             validate · preflight · doctor
────────────────────────────────────────────────────────────────────────────────────────
infra        util.py (safe_seg, atomic writes, file_lock, pid_alive, swallowed, init_logging)
             appconfig · activerealm · assets · icons · brand
```

Two things about `webui/` that surprise people:

- **The namespace mirror.** `webui/__init__.py` and `pages.py` do
  `globals().update(vars(_core))`, so every helper is reachable as `webui.<name>`. It's why
  pyflakes reports "undefined name" in `pages.py`, and why a module-level name defined in `_core`
  (a logger, say) must be redefined *after* the mirror line in `pages.py` to stay its own.
- **L2 modules never import `_core`**; `_core` imports them back. That's what keeps the carve-up
  (Phase 3 of the old refactor, then 2.4) free of cycles.

## 3. The seams

A seam is a place where one side may change without the other noticing. These are the ones that
exist on purpose:

| Seam | Contract | Where | Notes |
|---|---|---|---|
| Engine | `EngineAdapter.doctor/run/run_stream`, `RunResult`, `Usage`, normalised stream kinds | `engine/` | Narrow and real; the *vocabulary* around it is Claude's — see the audit. |
| Realm on disk | the layout in `SCHEMA.md`; `schema_version` + `realmformat.MIGRATIONS` | `realmformat.py` | Every non-additive change is a registered, idempotent step (2.8). |
| Add-ons | data-only `addon.json`, five kinds, `addons.load()` | `addons.py` | Stubbed — nothing consumes it yet (2.7). |
| HTTP | `_GET_EXACT` / `_GET_PREFIX` / POST tables → handler method names | `serve.py` + `routes/` | Route tables stay in one place; bodies live by area. |
| Static assets | `assets.js(name)` / `CSSV` cache-buster | `assets.py` | Script order is the order of `<script src>` tags (2.1). |
| Capability grants | "who may use what", stated once | `capabilities.py` | MCP-backed kinds enforced at the engine via `mcp__<id>` denies; skills/plugins advisory. |
| Time | `clock.now()` / `clock.today()`, freezable | `clock.py` | Golden pages render at a frozen instant (`tests/golden_support.GOLDEN_NOW`). |
| Status | one run-status vocabulary | `status.py` | Everything that colours a job asks here. |

## 4. Invariants

Each: the rule, why it exists, what enforces it, and where it doesn't hold yet. A known exception
written down is a ticket; an unknown one is a bug.

### 4.1 The realm folder is the truth
**Rule.** Everything that describes a realm — its agents, jobs, memories, goals, threads, run
history, capabilities, dashboard, add-ons — lives in the realm folder, in plain JSON/Markdown, so
the folder can be zipped, committed, moved to another machine and opened there. The app is a
stateless engine over it; `reader.read()` rebuilds the model from disk on every page.
**Machine-local, by design, outside the realm:** `~/.armada/` — `config.json` (theme, last realm,
app root), `realms.json` (the registry), `logs/`, `addons/` (app scope), `catalogue/` (cached
sources), the Telegram credential store. Claude Code's own `~/.claude*` files are read, never
written (see 4.8).
**Machine-local, inside the realm** (runtime state that happens to live beside the data):
`scheduler.lock.json`, `usage-last.json`, `.armada/models.json` and the notification feed.
Caches can be rebuilt; ownership metadata may be recovered only while writers are stopped.
**Durable execution state:** `.scheduler/attempts/` and `system_jobs.json` contain admissions and
outcomes. Preserve them with the realm; deleting or restoring stale copies can admit duplicate
work. Never unlink a valid hidden OS lock file to resolve contention.
**Enforced by:** convention, `SCHEMA.md`, and `realmops.export` (which zips the folder, and
reports rather than silently skips a file it can't read).

### 4.2 No read-modify-write without a lock; no write that isn't atomic
**Rule.** Two processes write realm files (the server and the scheduler), so a read-modify-write of
a shared file uses `util.mutate_json` or holds `util.file_lock(path)` across the complete operation.
Atomic writers use a flushed temporary file plus `os.replace`. Lock timeout or I/O failure raises
without entering the critical section. Kernel ownership ends on close/crash; the hidden sibling
lock file is never unlinked. Mutation reads preserve malformed and future-schema state instead
of replacing it with defaults. See [PERSISTENCE.md](PERSISTENCE.md) for upgrade/recovery rules.
**Enforced by:** `tests/test_realm_write_locking.py` (every `realm.json` write path, 2.9),
`test_realm_format.py` (migrations lock), and `test_exclusive_state.py` (independent processes,
owner death, timeout/access failures and unsupported state), plus `test_scheduler_claims.py`
(scheduler/process races and interrupted dispatch). Compaction transactions remain tracked in 2.16.
**Also locked since v0.99.45:** `agent.json` saves from the Configure tab, thread `meta.json`
(routes, run replies, and the render-path writes — which take no lock when nothing changes), and
`dashboard.json` (the render-time span migration re-checks the file under the lock so it never
overwrites a newer save). `tests/test_agent_and_thread_locking.py`.

### 4.3 No network on a render path
**Rule.** Rendering a page never waits on the network or a subprocess. Anything that needs one —
subscription limits, sign-in state, the catalogue, a capability review — is fetched by the page
afterwards from an `/api/*` route, or read from a cache a system job keeps fresh.
**Enforced by:** structure — nothing under `webui/` imports `urllib` or `subprocess` (a grep says
so; it would make a cheap test). Phase 1 held the line for the Catalogue (`_cat_results` runs only
from `/api/catalogue`).
**Not yet:** `models.options()`, called while rendering model dropdowns, can *start* a background
thread to refresh a stale model catalogue. The render doesn't wait for it and it runs at most once
per TTL, but it's the one network call a page view can initiate.

### 4.4 Nothing fails silently
**Rule.** A broad `except` may fall back, but it logs first — `util.swallowed(log, "<func>:
<fallback>")` (ERROR with traceback, missing files at DEBUG, repeats rate-limited), or
`log.debug(…, exc_info=True)` where the failure *is* the expected path, or an explicit
`# silent-ok: <reason>` (2.5).
**Enforced by:** `tests/test_exception_logging.py` scans every broad handler in `armada/`.

### 4.5 The realm's format is versioned
**Rule.** `realm.json` carries an integer `schema_version`; a change a reader could misread is a
registered migration step, run on open and on import, never on a realm stamped newer than this
build (2.8).
**Enforced by:** `tests/test_realm_format.py` (a step for every version below `CURRENT`).

### 4.6 JavaScript lives in files
**Rule.** Page logic is in `webui/static/js/*.js`, loaded with `assets.js(name)`; Python emits only
tiny data shims (`<script>window.MC_X=…</script>`, a one-line call with arguments). Order is the
order of the tags (2.1).
**Not yet:** two leftovers the 2.1 sweep missed because neither is a `<script>` literal in the
Python source: `_core._WIZ_JS`, the 61-line new-realm wizard script held in a raw-string constant
and concatenated into `pages.render_new_realm`; and `serve.APP_HTML`, which appears to be dead code.
Both belong to 4.3's Haiku backlog.

### 4.7 One place decides who may use a capability
**Rule.** `capabilities.py` states the grant rule once — the realm holds the catalogue, a
coordinator may use all of it, everyone else only what was granted — and every page and the
runner ask it rather than deciding. Enforcement is real for MCP-backed kinds and advisory for skills
and plugins; the module says so in its first paragraph.

### 4.8 ARMADA never touches another app's credentials
**Rule.** Sign-in is Claude Code's own flow in its own console (`auth.py`); ARMADA asks whether
you're signed in and never sees, stores, refreshes or writes a token. `usage_api` and `models` read
Claude Code's OAuth token read-only and deliberately don't refresh it (a rotated refresh token
would break Claude Code's sign-in); the `usage-keepalive` system job makes Claude Code refresh it
itself.

### 4.9 Extensions are data
**Rule.** Whatever users (or, later, Alexander) add to ARMADA is data the app validates and renders
with its own code — never HTML, JS, Python or shell commands (ADR-002, `EXTENSION_POINTS.md`).
Undo is deleting a folder.

## 5. Three flows, end to end

**A page view.** `GET /jobs` → `serve.Handler.do_GET` → `_route_get` (`_REALM_PAGES` first, then
the exact table, then prefixes) → `routes/realm._get_realm_page` → `reader.read(realm)` builds `model.Realm` from
disk → `webui.render_*` composes HTML from `webui/` layers → `_send` with `no-store`. Static assets
come back with a long cache and a `?v=<mtime>` buster.

**A chat turn.** `POST /api/chat-stream` (answered as a server-sent event stream) → `routes/agents._chat_stream` →
`runner.chat_stream`: resolve model/effort/budget, assemble context (`memory.assemble_core` +
`runner._tool_preamble` + thread history, compacted by `threads.Thread.compact_if_needed` when it
nears the model's window) → `engine.run_stream` → normalised events relayed to the browser and
through `runner._TurnCapture` (artefacts, publish boundary, capabilities used) → turn appended to
`messages.jsonl` under lock → usage row → notification.

**A scheduled job.** `scheduler.run_daemon` → every realm → `tick`: `realmformat.ensure`,
exclusive lease and per-pass gate, preflight hold check, `sysjobs.run_due`, then each `due_now`
job not already `ran_today` → durable daily claim → `runner.run_job` (agent job: same context +
engine path as chat; command job: a subprocess) → run report / notification → complete the claim.
An uncertain claim is not retried automatically. System jobs claim their interval under a
separate per-job execution lock, shared with app-startup nudges and manual requests.
System-job cost does not gate authentication. Inbox and Telegram check the selected recipient's
provider; Claude keepalive declares its fixed provider. The [upkeep contract](PROVIDER_UPKEEP.md)
defines signed-out skips, pending-message preservation and normalized job outcomes.

## 6. Testing

- **Golden pages** (`tests/test_golden_pages.py`) render every page against a deterministic fixture
  realm at a frozen instant and compare byte-for-byte. Regold with `ARMADA_REGOLD=1` *after* the
  version bump and changelog entry (the changelog renders into `settings`), and read every diff.
  All of them are deterministic: anything the render path shows about time goes through
  `clock.now()`, and so does anything it reads back (UI_AUDIT L7).
- **Guard tests** keep the invariants from rotting: `test_exception_logging`,
  `test_realm_format`, `test_realm_write_locking`, `test_addons` (including drift checks against
  the lists it mirrors).
- **The standing baseline** is 31 failures in the Linux sandbox, all path/OS-specific
  (`WindowsPath` on Linux, backslash paths), visible since 2.5 made the swallowed errors log. They
  are not app bugs; on Windows they should pass.

## 7. Where new code goes

- A new page or panel → a renderer in the right `webui/` layer, its logic in
  `webui/static/js/<name>.js`, its route in the matching `routes/` file and one line in `serve.py`'s
  table.
- A new realm file or field → `SCHEMA.md` first; additive fields default on read; anything else is a
  `realmformat` migration.
- Anything that talks to Claude → through `engine/` if it's a turn; if it can't be, add it to the
  contract rather than import `engine.claude` (see the audit's three rules).
- Anything recurring → a system job in `sysjobs.JOBS`, not a timer in the server.
- Anything a user should be able to add without code → an add-on kind, not a setting.


## Scoped draft reviews (0.99.95)

Inspector authority is agent-level, tool selection is job-level. Approved skill
scripts and blind model pairs use managed draft tools with frozen inputs. See
[DRAFT_REVIEW_ARCHITECTURE.md](DRAFT_REVIEW_ARCHITECTURE.md) for the isolation,
private mapping, score reveal and retention boundaries. This supersedes the
agent-wide inspector tool selection in 0.99.93.
