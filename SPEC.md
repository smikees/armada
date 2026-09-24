# ARMADA — Product & Architecture Spec (v0.1)

> Working name: **ARMADA** (was "Retinue"). Owner: Mihai. Drafted with Marcus, 2026-09-03.
> Status: first draft for build kickoff. This is a design artifact, not code.

---

## 1. What it is (one paragraph)
Retinue is a **local, single-user desktop app** for building and running a personal **team of AI agents** — a "realm" of agents you direct, each with its own personality, memory, skills, jobs, and level of autonomy. At its core it is a **human-intuitive memory/context-management system**: the app decides what context each agent (and each thread) sees, so you get sharp, token-efficient agents without hand-managing files. It is **provider-agnostic by design** (Claude first; the engine behind it can change without changing your realm), **file-based and portable** (your realm is a folder you own and can move or version in Git), and **open source** (the app is a public repo; your realm data is private and never in it). You bring your own paid subscription; Retinue never holds your credentials or runs in our cloud.

## 2. Core principles (the invariants — do not violate)
1. **The realm is the files; the app is a stateless engine over them.** Everything an agent is or knows lives in files on disk. The app reads/writes them; it stores no source-of-truth state elsewhere. This is what makes portability, brownfield-adoption, and Git versioning free.
2. **Structure vs. skin.** A neutral internal ontology (`realm`, `agent`, `coordinator`, `objective`, `tenet`, `job`, `thread`, `memory`, `skill`, `connector`, `artifact`, `message`) is rendered through a **theme** that maps those to the user's own vocabulary (Cabinet/Ministers, Board/Execs, Crew/Mates, or custom). The theme is presentation + voice only; the stored structure stays neutral and portable.
3. **Memory-management first.** The product's central value is deciding *what context loads where*. Realm-level context loads everywhere; agent- and thread-level context is scoped tight. Core context is always present; everything else is optimized away.
4. **Propose by default.** Agents propose; irreversible / money / outbound actions require human approval unless the user raises an agent's autonomy. Safety is a first-class, per-agent setting.
5. **Provider-agnostic via a strict adapter seam.** No engine-specific concept leaks into the realm files. Swapping Claude → another engine changes an adapter, not your realm.
6. **GUI and files are two synced views of the same canonical data.** Nothing requires editing a file; power users still can. The app enforces file naming + format so the structure stays clean and debuggable.

## 3. Domain model (neutral ontology)
- **Realm** — the whole team + shared context. One realm per app instance (v1).
- **Agent** — a named persona with a **mandate** (structural role, invariant), a **soul** (personality/voice/traits, the skin), tenets, memory, skills, connectors, jobs, threads, artifacts, an inbox, and an **autonomy level**. Flagged `cabinet` (participates in cross-talk) or `isolated`. Each agent owns exactly one folder.
- **Coordinator** — an optional agent with realm-wide read access and the authority to delegate (the Hand/CEO/Captain). At most one. Not mandatory.
- **Objective** — realm-level goals (the North Star). Loaded into every agent.
- **Tenet** — guardrails/principles. Realm-level (all agents) or agent-level.
- **Job** — a scheduled or on-demand unit of work owned at realm-level (few, under the coordinator) or agent-level (most). Has a schedule, a prompt, a target thread, allowed skills, and an output contract.
- **Thread** — a conversation/work context under an agent. **Main** (default) + optional **sub-threads** for scoped memory (e.g. a `taxes` sub-thread that doesn't load options-trading context). Threads compact when long; core context is always re-injected.
- **Memory** — durable facts. **Realm memories** load into every thread; **agent memories** load only for that agent (token optimization). Example: everyone knows the user's name; only Travel knows "prefers hotels over Airbnb."
- **Skill / Connector / Plugin** — capabilities enabled per agent, pinned by source+version, with permission scopes. Engine-dependent.
- **Artifact** — an output (doc, report, app) mapped to the agent that made it; occasionally promoted to a **realm artifact** other agents can consume.
- **Message / Inbox** — inter-agent tasks. Agents check inboxes on cadence; an agent may **force an inbox read** for urgent items.

## 4. On-disk schema (the portable "Realm Spec")
The app enforces this layout, file names, and frontmatter. Example (neutral names; the theme only changes how they're *displayed*):

```
<realm>/
  realm.yaml                 # id, display_name, schema_version, theme_ref, default_engine, created
  theme.yaml                 # collective/coordinator/agent labels, voice, icon set, template_id
  objectives.md              # realm North Star — loaded into every thread
  tenets.md                  # realm-wide guardrails — loaded into every thread
  memory/                    # realm memories (loaded into every thread)
    <slug>.md                #   frontmatter: {scope: realm, title, tags}
  shared/                    # realm artifacts/data any agent may read
  agents/
    <agent-id>/
      agent.yaml             # name, mandate_ref, autonomy, model, engine, membership: cabinet|isolated,
                             #   coordinator: bool, avatar, channels
      mandate.md             # structural role/mandate (INVARIANT — theme-neutral)
      soul.md                # personality, voice, traits (the skin; may be theme-flavored)
      tenets.md              # agent-specific tenets
      memory/                # agent-scoped memories (loaded only for this agent)
      skills.yaml            # [{id, source, version, scopes[]}] — pinned + permissioned
      connectors.yaml        # [{id, type, vault_ref}] (e.g. IBKR) — secrets live in vault, not here
      jobs/
        <job-id>.yaml        # {schedule(cron|manual), thread, prompt_ref, allowed_skills[], output_contract}
      threads/
        main/messages.jsonl
        <subthread>/messages.jsonl
      artifacts/             # agent-owned outputs/apps/reports
      inbox.md               # incoming tasks/messages (status-tagged; never deleted, archived)
      runs/                  # run-reports (telemetry per job run)
  _system/                   # GENERATED, never hand-edited
    schedule.json            # computed job registry (all realm+agent jobs)
    manifest.lock            # deps lockfile: every skill/connector/plugin pinned by source+version
    usage/                   # telemetry: token accounting (realm total + per-agent)
    drift.json               # reconciliation: files-vs-registry, orphans, mislabels
    health.json              # run health (ran/missed/issues) for the cockpit
  .vault/                    # encrypted secrets — NOT portable-by-default, NOT in Git
  .git/                      # optional: realm versioning (private)
```

**Format enforcement / import:** to "import" an agent you drop a correctly-structured folder under `agents/` (or point setup at a realm folder); the app **validates + lints** it against the schema (a `retinue doctor` check), reports violations, and refuses to run a malformed agent until fixed. This keeps the realm clean and debuggable.

## 5. Memory & context model (the heart)
For any thread run, the app assembles context in this order, then compacts to fit:
1. **Always-on core** (never dropped): realm `objectives` + realm `tenets` + realm `memory/*` + the agent's `mandate` + `soul` + agent `tenets`.
2. **Agent memory** relevant to the thread.
3. **Thread history**, compacted when long: old turns are summarized, but the always-on core from (1) is **re-injected verbatim** every time (so compaction never erodes who the agent is or what the realm stands for).
Sub-threads inherit (1) but **not** sibling sub-thread history — that's the scoping lever (the `taxes` example). Compaction thresholds + summary style are per-realm settings.

## 6. Permissions, autonomy & security
- **Folder permissions (system-assigned, not manual):** each agent process is scoped to **its own folder + `shared/`** only. The **coordinator** may be granted **realm-wide read**. Users never set paths by hand; the app derives and enforces them.
- **Autonomy levels (per agent, editable in Manage Agent):** e.g. **L0 propose-only** → **L1 act within own folder** → **L2 act with connectors** → **L3 autonomous** — with irreversible/outbound actions always gated by an **Approvals inbox** unless explicitly whitelisted. Default = propose-only.
- **Skill trust:** skills are added with **permission scopes** (files / network / connectors / shell) and **pinned versions**; community skills pass a review/consent gate before first run. The lockfile records exactly what's installed.
- **Secrets vault:** API keys, connector OAuth, channel creds live in an encrypted `.vault/` (OS keychain-backed), excluded from the portable set and Git. Moving a realm re-prompts for secrets by design.
- **Data-flow honesty (for the open-source trust story):** everything is local except calls to the engine (LLM) and connectors the user enables; the app itself phones home to nothing.

## 7. Orchestration & messaging
- **Coordinator-mediated + auditable message bus.** Agents delegate work that another agent is better suited for; the coordinator can route/prioritize. All messages are logged (who → whom, when, status) for audit.
- **Inbox cadence + force-read.** Agents read inboxes on a schedule; an agent may **force an urgent read** by a peer. `cabinet` agents participate; `isolated` agents don't send/receive.
- Delegation is **advisory + owner-arbitrated** for anything crossing autonomy limits.

## 8. Jobs, scheduling & reliability (first-class)
- **The app owns the scheduler/runner** (a local daemon) — it does not depend on any vendor's cloud scheduler. Assumes the machine is on 24/7 and connected to the engine.
- Realm jobs (few, coordinator-owned) + agent jobs (most). Each run produces a **run-report** (status, tokens, duration, flags, output ref).
- **Reliability generalized from the reference cabinet:** a 7-day health grid, **telemetry-health reconciliation** (missed / mislabeled / ran-but-unverifiable), and **failure alerts** to the user's channels. A tooling failure must never masquerade as a normal result.
- Every job supports a **dry-run / test-now** before scheduling.

## 9. Engine adapter contract (provider seam)
An adapter implements: `auth()/status()`, `models()`, `capabilities()` (tools/skills/connectors supported), and `run(agent_context, thread, prompt, allowed_tools) -> {output, usage, artifacts}`. **Model is selectable per agent** and changeable anytime (subject to the active engine). v1 ships the **Claude adapter** (drives Claude Code / the Agent SDK on the user's Pro/Max subscription — no API metering). Later adapters (Codex CLI on a ChatGPT plan; a raw-API adapter) drop in without touching realm files.

## 10. Telemetry & usage
- **On by default.** Every run records input/output/cache tokens + cost estimate. The cockpit shows **realm-total** usage and a **per-agent** breakdown, over time. (This also finally answers "subscription vs API" with real numbers.) v1 = visibility only (no hard budgets).

## 11. Identity & experience
- Per agent: **name, avatar, personality (soul), behavior, voice-in-text**, and the theme's framing. Templates (State / Company / Crew / Scratch) seed a coordinator + starter agents with sensible mandates + skills.
- **Roadmap / nice-to-have:** audio voice per agent + text-to-speech ("let the agent speak").

## 12. Setup flow (greenfield + brownfield)
1. Launch → *Create new* or *Open existing*.
2. Point at a folder. Has a realm? → **Adopt** (read + show roster/jobs/skills → verify & resume). Empty? → **Create**.
3. Connect engine (v1 Claude; detect/verify the CLI is logged in on your subscription; test call).
4. Pick framing (theme) + template (or scratch).
5. Add/shape agents (name → mandate → skills/connectors → jobs → memory → soul/voice → autonomy → cabinet|isolated).
6. Set objectives (optional).
7. Provision dependencies from the lockfile (install missing skills/connectors; trust gate for community skills).
8. Secrets & channels (vault; pick Telegram/email per agent).
9. Review, test-run, launch → scheduler goes live, cockpit becomes home.
- **Move to a new PC:** Open existing → verify engine → re-provision from lockfile → re-enter secrets → resume.

## 13. Proposed tech stack (for discussion)
- **Desktop shell:** Tauri (Rust core + web UI) for a small cross-platform Windows-installable app; Electron is the fallback if team familiarity wins.
- **Frontend:** React or Svelte; the cockpit + manage-agent pages.
- **Local service/runner:** a background daemon (Node or Python) = scheduler + engine invocation + telemetry. Communicates with the shell over local IPC/HTTP.
- **Storage:** files are the source of truth (YAML/MD/JSONL). A local **SQLite index** may cache search/telemetry — derived, disposable, never authoritative.
- **Engine:** Claude adapter shells to Claude Code (headless/print mode) or the Agent SDK.
- **Versioning:** libgit2/simple-git for the realm repo. **Secrets:** OS keychain + encrypted vault file.
- **License:** permissive open source (MIT or Apache-2.0) — decide before first public commit.

## 14. v1 scope (MoSCoW)
**Must (v1):** local desktop app; file-based realm; greenfield + brownfield setup with schema lint/`doctor`; **Claude engine adapter (subscription-priced)**; agents with mandate/soul/tenets/memory/autonomy + cabinet|isolated; realm + agent memory; main + sub-threads with compaction + always-on core; realm + agent jobs on the app's own scheduler with run-reports + **test-run**; skills/connectors **manifest + provisioning with scopes + pinned versions**; **folder-permission enforcement + coordinator**; telemetry (realm + per-agent usage, visibility only); reliability (health grid + telemetry-health + alerts); themes + templates (State/Company/Crew/Scratch); GUI↔files sync; secrets vault; **realm Git versioning**; **Telegram channel** + Approvals inbox; coordinator-mediated message bus + inbox force-read.
**Should:** email channel; artifacts-as-apps; richer import UI.
**Could / later:** additional engine adapters (Codex CLI, raw API); voice/audio per agent; agent/realm template marketplace; mobile companion; hard cost budgets; extra backup targets — Google Drive / S3 / Dropbox, snapshot-not-mirror (§16).
**Won't (v1):** hosted SaaS; multi-user/multi-realm; bypassing any provider's billing/ToS; Google login as app identity or any continuous cloud file-mirror of a live realm (§16).

## 15. Suggested build order (so we can start tomorrow)
- **P0 — Schema + fixtures:** finalize this schema; use **Mihai's existing cabinet (`D:\Work\Hand`) as the reference realm/test fixture** (perfect brownfield dogfood).
- **P1 — Read-only cockpit:** app opens a realm folder and renders roster, jobs, skills, health, usage (evolve `status.html`). No writes. Immediate value + validates the schema against a real realm.
- **P2 — Runner + Claude adapter:** run one job end-to-end from the app (scheduler → engine → run-report). Proves the subscription-priced engine path.
- **P3 — Memory/threads:** context assembly, sub-threads, compaction with always-on core.
- **P4 — Setup wizard + themes/templates:** greenfield create + theme layer.
- **P5 — Skills/connectors provisioning + telemetry + reliability + Telegram + approvals.**
- **P6 — Git versioning + comms polish + editing UI (GUI↔files write path).**

## 16. Backup & sync
**Principle: snapshot, not mirror.** Backup/restore is a first-class *snapshot* operation, never a continuous file-mirror of a live realm.
- **Why not a continuous mirror (Drive/Dropbox/MEGA-style):** the runner writes files constantly (`.jsonl` appends, run-reports, thread history, state). A live mirror over that produces partial-sync reads, mid-append corruption, and last-writer-wins clobbering — the exact class we already code around on the MEGA-synced `D:\Work` (the `sanitize()` guards, the BOM/truncation bugs, stale mounts). And two machines syncing a realm while both run the daemon = **two schedulers double-firing jobs**.
- **Mechanism — pluggable backup targets.** v1 = **private Git remote**: atomic commits, real history, rollback, off-site copy — strictly better than folder-mirroring for text-heavy realm data. Later targets (Google Drive, S3, Dropbox) are **snapshot destinations** (periodic atomic snapshot / git-bundle pushed), not live mirrors.
- **Exclusions (always):** `.vault/` (secrets) and volatile run-logs / heavy artifacts are excluded from every backup and portable set, enforced by app-managed ignore rules.
- **Single-active-writer invariant:** exactly one machine runs a realm's daemon; every other copy is a *restore target*, not a concurrent runner. Restore/move = clone or pull → re-enter secrets → `doctor` re-provision → resume.
- **No Google login as identity.** The app stays account-less; Google Drive, if enabled, is only an opt-in backup *target*, authorized just-in-time for that purpose — never app sign-in.
- **Cadence:** user-set snapshot cadence (on-change / hourly / daily); the runner is briefly quiesced during a snapshot so nothing is captured mid-write; snapshots are atomic.

## 17. Dependencies & preflight (the `doctor`)
**Design goal: bundle everything we can.** The only things a user must supply are the **engine subscription** and **accounts for the connectors they choose**. Four tiers:

1. **Bundled (user installs nothing):** the UI runtime (WebView2 via Tauri, bootstrapped if absent; or Electron/Chromium); the runner runtime (Rust binary, or a packaged Node/Python); **Git** (libgit2/portable — no system Git needed); an **embedded Node** (drives `npx`-based skills/MCP servers *and* Claude Code).
2. **Required external — the engine (the one real dependency):** **Claude Code / the Agent SDK, installed and authenticated on the user's Pro/Max subscription.** We bundle Node and can auto-install Claude Code, then guide `claude login` — but the **subscription auth is the user's** (we detect it and launch the flow, we can't do it for them). The doctor verifies a **compatible version range**, since we inherit Claude Code's churn. (A future raw-API adapter removes the CLI/Node-engine dependency entirely, at the cost of metered pricing.)
3. **Conditional — per enabled skill/connector (from the manifest):** some skills/MCP servers need a **Python runtime** (`uvx`/pip) or a specific binary; connector OAuth needs the **system default browser**; all need network. Each skill *declares* its runtime + min version so the doctor knows what to check and bootstrap.
4. **Credentials, not installs:** the provider subscription, a **Telegram bot token**, email/SMTP creds, connector API keys/OAuth. Checked (test call) and stored in the vault — nothing to "install." **No GPU** required (unless a future local-LLM engine adapter, which would pull in Ollama + a capable GPU — explicitly "later", ties to the G7 rig).

**The `doctor` (preflight)** runs at **first setup**, on **brownfield import**, whenever a **skill/connector is added**, and **on-demand** (it also feeds the cockpit health view). It verifies, in order: engine present + compatible version + authenticated (tiny test call; launch `claude login` if needed) → bundled runtimes healthy → each enabled skill's declared runtime present at the required version → vault/keychain reachable → network to engine + configured connectors → channel creds valid (send a Telegram test). It **auto-resolves what it can** (install a missing runtime, bootstrap a skill) and, for what it can't (the subscription login, a connector account), reports a **clear, actionable gap and blocks only the affected agent/skill — never the whole app**. Version-pinning the engine means a breaking Claude Code update is *caught*, not silently broken.

## 18. Open items / decisions still to make
- Trademark/domain check on the name before committing.
- Exact autonomy-level taxonomy (L0–L3 above is a starting proposal).
- Compaction summary strategy (extractive vs LLM-summarized) and thresholds.
- How connectors' OAuth refresh is handled inside a local app (per-provider).
- Community-skill review model specifics (static scan? manual consent only? signature/registry?).
- Whether v1 is truly Claude-only or we stub the adapter interface from day one (recommended: stub the seam, ship one adapter).
