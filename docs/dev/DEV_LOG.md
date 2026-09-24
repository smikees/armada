# ARMADA — development log

*The project README from v0.2 to v0.99, kept for its history: what each early version added and
how it was validated. Superseded by [the README](../../README.md), [ARCHITECTURE.md](ARCHITECTURE.md)
and the changelog in the app (Settings → App → Changelog). Paths like `D:\Work\Hand` are the
developer's machine.*

**Your standing team of minds — in your own words.**

ARMADA is a **local, single-user, provider-agnostic** app for building and running a personal
team of AI agents — a *realm* of agents you direct, each with its own personality, memory,
skills, jobs, and autonomy. At its core it's a **human-intuitive memory/context-management
system**: it decides what each agent (and each thread) sees, so you get sharp, token-efficient
agents without hand-managing files. Your realm is a **folder you own** (portable, Git-versioned);
the app is a stateless engine over it. You bring your own paid subscription — ARMADA never holds
your credentials or runs in the cloud.

See **[SPEC.md](../../SPEC.md)** for the full product & architecture spec.

## Status — v0.7 (P1 cockpit · P2 runner+engine+doctor+serve · P3 memory+threads · P4 themes+templates · P5a skills+telemetry · P5b cmd-jobs+scheduler)
The first milestone: ARMADA **adopts an existing realm folder and renders a read-only cockpit** —
agents, the jobs each owns, health, run volume, and the gaps ARMADA would formalize. It's
dogfooded against a real, live realm (the reference "Cabinet") as the test fixture.

**Validated on real hardware (2026-09-04):** the Claude adapter runs subscription-priced end-to-end
via the native `claude.exe`, with ARMADA owning the full context (`--system-prompt` + `--safe-mode` +
`--tools ""`). A `hello` job went from **128K tokens → 898** (~99% leaner) while returning a correct,
honest answer — the memory-management thesis, proven.

## Run it
```bash
python3 -m armada open /path/to/realm --out prototype-output/cockpit.html
# e.g. the reference cabinet:
python3 -m armada open "D:\Work\Hand"
```
Open the generated `prototype-output/cockpit.html` in a browser. Read-only — nothing is written
back to the realm.


## New in v0.2 — run a job, check the env, dogfood live
```bash
matcap doctor --realm "D:\\Work\\Hand" --engine claude   # preflight: Python, Git, engine auth
matcap run examples/demo-realm scout hello --engine mock     # offline test (no tokens)
matcap run examples/demo-realm scout hello --engine claude   # real, on your subscription
matcap serve "D:\\Work\\Hand"                            # live cockpit + Update & Restart button
```
The runner writes a **tokenized run-report** per run (input/output/cache tokens + cost), which the
cockpit surfaces as per-agent **Tokens (30d)**. `serve` bakes in the **⟳ Update & Restart** dogfood loop.

## New in v0.15 — polish pass (review feedback)
Icons standardized on **Lucide** (via Iconify) + a Claude mark on the model pill; threads UTF-8 fix
(engine output decoded as UTF-8); per-agent **role** shown beside the name (not "AGENT"); Configure
gains **Profile, Role, Tenets, Inbox-frequency, and avatar image upload**; new **Inbox** sub-tab;
**Memories** rename; jobs get an **editable name, Created column, and sortable headers**, one
expandable list, resizable light prompt, and a play icon on Run; ministers cards show profile +
appointed; **user-added sections** (promote an artifact to the top nav); dashboard **edit-layout**
(drag to reorder + resize widgets, persisted); and a two-step **realm-creation wizard** (template
cards + icon picker + Browse-folder + choose which agents staff the realm, with the full cabinet
roster as State presets).

## New in v0.14 — the app is feature-complete (all sections wired)
- **Realm-level pages** behind the top nav: Ministers roster, all-Jobs + 7-day **health grid**,
  realm Memory (+ per-agent), Skills (manifest.lock), Artefacts (shared/).
- **Full job-detail page** (`/job/<agent>/<job>`): editable prompt, kind, thread, model/effort,
  a **cadence editor** (presets + day circles + time + live cron), allowed-skills, on-failure,
  budget, run history — **Save** writes the job file.
- **Write-path**: Configure edits an agent (name, autonomy, model/effort, mandate, soul) and saves;
  jobs save from the detail page.
- **Create flows**: Add agent, Add job, and a **New-realm wizard** (create-from-template or adopt
  an existing folder).
- **Multi-realm**: a realm **switcher** in the nav + a `~/.armada/realms.json` registry; switch
  between independent realms.
- **Settings** (engine/doctor status, Update & Restart, appearance, data-flow note) and an
  **Approvals inbox** (file-backed; empty until the autonomy gate produces items).

## New in v0.13 — Threads (live chat + loaded-context) + Jobs polish
- **Threads screen** (the memory differentiator): a thread list, the conversation transcript, a
  composer that actually **chats with the agent** (`/api/chat` → the engine, with the agent's core
  context + thread history; the turn is appended to the thread), and a **"Loaded context · next
  reply"** rail showing the proportion + token estimate of base prompt+soul / realm memory / agent
  memory / compaction summary / recent turns — so you can *see* what the agent is being given.
- **Jobs polish** (from review): one **expandable** job list (no more duplicated table), the job
  prompt is a **resizable** field on a **light** background (dark mode comes later).

## New in v0.12 — it's clickable: the agent frame
The dashboard's Register rows now open each agent's page (`/agent/<id>`), with the design's agent
header (portrait, name, role, model pill) and the **seven sub-tabs**: Overview, Threads, Jobs,
Skills, Memory, Artefacts, Configure. Overview shows the mandate + soul + jobs + memory/skills;
**Jobs** lists each job with its real prompt and a **Run** button wired to the live engine (mock or
Claude) with streamed output; Skills/Memory/Configure show real per-agent data; Threads lists the
agent's threads. Breadcrumb + logo + tabs navigate back to the realm overview.

## New in v0.11 — the app UI, matched to the approved design (realm overview)
`matcap serve` now renders the **realm dashboard** from the design handoff — the ARMADA title bar,
top nav (realm switcher + themed tabs + user sections), the KPI header, and the Register /
From-the-Hand / Attention / Today widgets — server-rendered from live realm data, reusing the
Industry design-system tokens + ARMADA brand overrides (`armada/webui/static/`). Cadences render as
friendly labels ("weekdays 14:00", "1st Sat 08:00"), 7-day health bars come from run-reports, and
telemetry/attention/today reflect the real realm (honest empty-states when there are no runs). The
agent frame, threads, and job-detail screens build on this next. Still zero-build + Update-&-Restart,
so it's ready to be wrapped in a native window.

## New in v0.10 — agent jobs run for real (engine tool + path parity)
An **agent job** (LLM + tools) now runs end-to-end through the Claude engine on the user's machine:
- **Launcher fix:** npm ships a ~500 B `bin/claude.exe` *stub* that only re-launches node; running it
  directly fails with WinError 216. ARMADA now prefers `node <cli-wrapper.cjs>` (the real entry), so
  runs work on current Claude Code installs; a real native binary is still used if present.
- **UTF-8 env:** the engine sets `PYTHONUTF8`/`PYTHONIOENCODING` so scripts the agent runs via its
  Bash tool don't crash on Unicode.
- **Host/path preamble:** each tool-using run is told the OS, realm folder, and that Cowork sandbox
  paths (`/sessions/.../mnt/Work`) don't exist here — plus Windows Bash path guidance. The exporter
  also rewrites those sandbox paths to native ones.

*(Validated 2026-09-05: a read-only agent job ran `decisions.py` via Bash through `claude.exe` and
returned `OVERDUE=5 URGENT=3`, no manual workarounds.)*

## New in v0.9 — the interactive app (clickable, runs jobs)
```bash
matcap serve "D:\Work\Hand-realm"      # then open http://127.0.0.1:8756
```
`serve` is now a real local app, not a static page: a sidebar of agents (coordinator crowned),
click an agent to see its jobs, click a job to read its **actual prompt**, then **Run** it (mock or
the live engine) and watch the output stream back — plus a live **What's due** check against the
scheduler and one-click **⟳ Update & Restart** (git pull + hot re-exec) so the UI can be iterated
fast. Same runner/scheduler underneath as the CLI; stdlib-only, local-only. (This browser-served UI
is the substance of the interface; wrapping it in a native window is a thin follow-on.)

## New in v0.8 — cron cadences + realm validator (export-ready)
```bash
matcap validate D:\Work\Hand-realm     # is this folder a runnable realm? what's present/missing?
# jobs can now carry real cron, matching the reference cabinet's cadences:
#   {"cron":"0 8 1-7 * 6"}   first-Saturday   ·   {"cron":"0 11 1 1,4,7,10 *"}   quarterly
```
The scheduler now understands full 5-field **cron** (lists, ranges, steps, and the Vixie
day-of-month/day-of-week OR rule), so the cabinet's real cadences transfer faithfully — a job
declares `"cron": "..."` or the simple `"schedule": "mon-fri 09:30"` grammar, both honoring the
realm's timezone + grace. **`matcap validate`** is the contract check behind "point ARMADA at a
folder and it figures out the realm": it reports agents, jobs, and any missing/malformed files,
and tells a cabinet-format folder to export to native first. This is the groundwork for migrating
the live cabinet by **export** (write it into the native spec) rather than a bespoke importer.

## New in v0.7 — the scheduler (jobs run on their own)
```bash
matcap schedule myrealm                       # daemon: fire jobs on their cadence, forever
matcap schedule myrealm --once                # single pass (drive from Windows Task Scheduler)
matcap schedule myrealm --dry-run             # show what's due now, run nothing
matcap schedule myrealm --at 08:30 --engine mock   # simulate a time (testing)
```
ARMADA now owns scheduling — no OS cron needed, so a realm stays self-contained and portable.
Each job's `schedule` (`"daily 14:00"`, `"mon-fri 09:30"`, `"mon,wed,fri 08:00"`, `"manual"`) is
evaluated against the realm's **timezone + grace window** (from `realm.json`, matching the
cabinet's `timezone` + `grace_minutes`), and firing is **idempotent** — a job runs once per day
when due, and a job missed by a reboot still catches up inside the grace window. Runs through the
same runner, so command and agent jobs both schedule. *(Validated 2026-09-04: the scheduler fired
the live cabinet's `decisions.py` on cadence on real hardware, with the idempotency guard holding.)*

## New in v0.6 — command jobs (deterministic scripts) — migration groundwork
```bash
# a job can now be a script, not just an LLM turn:
# agents/<id>/jobs/<job>.json → {"kind":"command","run":"python collect_x.py","schedule":"daily 08:00"}
matcap run myrealm ops decisions        # runs the script, captures status/output — no engine, no tokens
```
The runner now distinguishes two **job kinds**: *agent* (LLM via the engine) and *command*
(a deterministic script). Command jobs capture return code + output into the same run-reports,
so the cockpit shows them alongside agent jobs (tagged `cmd`). Child processes run with a forced
**UTF-8 environment** so Windows scripts that print Unicode (`─`, `⚡`, `€`) don't die when their
output is captured. This is the groundwork for migrating the reference cabinet — half of which is
deterministic Python collectors — to run under ARMADA. *(Validated 2026-09-04: ARMADA ran the live
cabinet's `decisions.py` end-to-end on real hardware, rc=0.)*

## New in v0.5 — skills provisioning & cost visibility (P5a)
```bash
matcap skills add myteam finance market-data --source uvx:matcap-market-data --version 0.4.1 --scope network,connectors
matcap skills list myteam            # per-agent manifest + lockfile warnings
matcap skills lock myteam            # regenerate manifest.lock (every skill pinned by source+version)
```
Each agent declares its capabilities in `agents/<id>/skills.json` — **pinned** (source+version)
and **scoped** (`files` / `network` / `connectors` / `shell`) so what an agent can touch is
explicit and auditable. A realm-level **`manifest.lock`** aggregates every declared skill (the
list a provisioner installs and the doctor verifies) and flags anything left unpinned. The
cockpit now shows each agent's skills as scoped chips, plus **usage telemetry** — realm-total
and per-agent tokens with an **api-equivalent $** (what it *would* cost at API list prices;
on a subscription it draws from quota, it is not billed). Visibility only — no hard budgets.

## New in v0.4 — build a realm from scratch (themes & templates)
```bash
matcap new myteam --template company --name "Acme Inc"   # or: state | crew | scratch
matcap open myteam                                        # themed cockpit: Company · Executives · CEO
```
Same neutral structure underneath; the **theme** just maps it to your vocabulary — a **State**
Cabinet of Ministers (a Hand), a **Company** Board of Executives (a CEO), a **Crew** of Mates
(a Captain), or **Scratch** (blank, name it yourself). Templates seed a coordinator + starter
agents (mandate + voice); the realm stays portable and re-themeable.

## New in v0.3 — memory & threads (the context engine)
```bash
matcap run examples/demo-realm scout hello  --engine mock                 # main thread
matcap run examples/demo-realm scout recap  --engine mock                 # continues that thread
matcap run examples/demo-realm scout hello  --engine mock --thread taxes  # scoped sub-thread
matcap threads examples/demo-realm scout                                  # list an agent's threads
```
- **Layered memory** — `realm/memory/` loads for every agent; `agents/<id>/memory/` loads only for
  that agent ("everyone knows the owner's name; only Travel knows he prefers hotels").
- **Threads** — a `main` thread plus **sub-threads** that share the always-on core but carry their
  own history (scope tax context away from options-trading context).
- **Compaction** — long threads summarize their oldest turns into `summary.md` while the core
  (realm objectives + tenets + memory + the agent's mandate) is re-injected verbatim every run.

## Layout
```
armada/        reader (folder -> model) · model (dataclasses) · render (model -> cockpit.html) · cli
assets/        brand (logo)
SPEC.md        product & architecture spec
prototype-output/   generated cockpit (gitignored)
```

## Roadmap (from SPEC §15)
- **P1 ✅ read-only cockpit** over an existing realm.
- **P2 ✅** runner + Claude engine adapter (run one job end-to-end, subscription-priced).
- **P3 ✅** memory/threads (realm+agent memory, sub-threads, compaction with always-on core).
- **P4 ✅** setup wizard + themes/templates (State / Company / Crew / Scratch).
- **P5a ✅** skills/connectors provisioning (pinned + scoped, `manifest.lock`) + usage telemetry.
- **P5b (migration-core, in progress)** — command jobs ✅ · scheduler ✅ · cabinet import (adopt live jobs) · reliability (health grid + telemetry-health).
- **P5c** Telegram + Approvals inbox (autonomy gate).
- **P6** Git versioning + comms + the editing (write) path.
