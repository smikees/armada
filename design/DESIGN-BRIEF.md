# ARMADA — UX/UI Design Brief (paste into the Claude design app)

Design a desktop application called **ARMADA**. Produce high-fidelity, clickable-feeling mockups
of every key screen plus a reusable component system, and iterate with me until I'm happy. Ask me
questions when a choice is genuinely mine to make; otherwise pick sensible defaults and show them.

## What ARMADA is
A **local, single-user, desktop app for building and running a personal team of AI agents** — a
"realm" of agents you direct, each with its own personality, memory, skills, scheduled jobs, and
level of autonomy. It runs on the user's own machine and their own paid AI subscription; nothing is
hosted in the cloud. Tagline: **"Your standing team of minds — in your own words."**

The core value is two things working together: (1) a **human-intuitive memory/context system** —
the app decides what each agent sees, so agents stay sharp without the user hand-managing files; and
(2) **the realm is a folder the user owns** — portable, versioned, private.

## Who uses it and how it should feel
A capable non-developer power-user running a personal "cabinet" of AI agents that work for them on a
schedule (finance, health, strategy, etc.). The app should feel like a **calm personal command
center** — a control room for a small team of minds. Information-dense but composed, confident, a
little characterful (these agents have personalities), never a noisy dashboard. Think "mission
control meets a personal study," not "SaaS admin panel."

## The signature idea: structure vs. skin (themes)
Underneath, the structure is neutral: a *realm* contains a *coordinator* + *agents*; agents own
*jobs*; etc. On top sits a **theme** that renames everything into the user's own vocabulary, because
making the team relatable is a big part of the value. The UI must be **theme-skinnable**. Show these
themes and a theme picker:
- **State** → a *Cabinet* of *Ministers*, led by a *Hand*. (icon 🏛️)
- **Company** → a *Board* of *Executives*, led by a *CEO*. (🏢)
- **Crew** → a pirate *Crew* of *Mates*, led by a *Captain*. (🏴‍☠️)
- **Scratch** → neutral *Realm* / *Agents* / *Coordinator*. (🧭)
Design the primary screens in the **State/Cabinet** theme (that's the flagship user's realm), but
show one screen re-skinned as **Company** so the theming is visible.

## Concepts the UI must express (use the themed labels in the UI)
- **Realm** — the whole team + its objectives, tenets (rules), memory, and settings. One folder.
- **Agent** (Minister) — a persona with: a **mandate** (its structural role, fixed), a **soul**
  (personality/voice), **tenets**, **memory**, **skills/connectors**, **jobs**, **threads**, an
  **autonomy level**, and a flag for whether it joins team cross-talk or works isolated.
- **Coordinator** (Hand) — the one agent that coordinates the others and surfaces decisions.
- **Job** — scheduled or on-demand work an agent owns. Two kinds: **agent jobs** (an LLM prompt) and
  **command jobs** (a deterministic script). Has a **cadence** (e.g. "weekdays 14:00", or cron), a
  **prompt**, a target **thread**, allowed skills, and a run history.
- **Thread** — a conversation/work context under an agent: a **main** thread plus **sub-threads**
  that scope memory (e.g. a "taxes" thread that doesn't load trading context). Threads compact when
  long; a core context is always present.
- **Memory** — layered: **realm memory** loads for every agent; **agent memory** loads only for that
  agent. This is the heart of the product — make it feel tangible and manageable.
- **Skill / Connector** — a capability enabled per agent, **pinned** (source + version) and
  **scoped** (files / network / connectors / shell). Community skills pass a trust gate.
- **Autonomy** — per agent: propose-only → act within own folder → act with connectors → autonomous.
  Irreversible/outbound actions route to an **Approvals inbox** unless whitelisted.
- **Telemetry** — token usage per agent and realm-total, with an "api-equivalent $" (what it would
  cost at API prices; on a subscription it's quota, not billed). Visibility only.
- **Reliability** — a 7-day job **health grid**, plus alerts when a scheduled job fails.

## Screens to design
1. **Realm overview (home).** The team at a glance: the coordinator featured, then agent cards
   (avatar, name, persona line, status dot, #jobs, tokens). Top: realm name, theme, engine status,
   telemetry KPIs (agents, jobs, runs/30d, tokens/30d, ≈$). A "what's due now / next" strip. A
   health-and-attention panel (failures, approvals waiting, decisions needing the owner).
2. **Agent detail.** The persona (mandate + soul/voice, avatar), autonomy control, its **jobs**
   table, its **skills** (as pinned+scoped chips), its **threads** list, its **memory** (agent-level
   notes), and its telemetry. Tabs or a well-organized single view.
3. **Job detail.** The job's **prompt** (readable, editable), kind (agent/command), cadence editor
   (friendly cron), tools/skills it may use, target thread, **Run now** button, and a **run history**
   with status + output. Show a live "running… → output" state.
4. **Threads / conversation view.** An agent's main thread + sub-threads; a readable transcript;
   a visible sense of "what context is loaded" (core memory + this thread's history + compaction
   summary). This is where the memory system becomes visible — make it elegant.
5. **Memory manager.** Realm memory vs. agent memory, as browsable/editable notes ("everyone knows
   the owner's name; only Travel knows he prefers hotels"). Show how a memory is scoped.
6. **Skills & connectors.** Per-agent manifest + a realm-wide lockfile view; adding a skill with its
   permission scopes and pinned version; the trust gate for a community skill.
7. **Scheduler & reliability.** A 7-day health grid (jobs × days, ran/issue/missed), what's due,
   recent runs, and a failure alert example.
8. **Approvals inbox.** Pending irreversible/outbound actions an agent proposed, each with
   approve/deny and context.
9. **App/settings.** Engine/subscription connection status, secrets vault, backup/versioning (Git),
    theme picker, and a one-click **Update & Restart**.

## Create / manage flows (design these as multi-step)
- **First-run / setup wizard.** Point at a folder → if it's a realm, **adopt** it (show roster to
  confirm); if empty, **create** one. Pick a **template + theme**. Connect the engine (detect the
  subscription, guide login). Land on the overview.
- **Add an agent.** name → mandate (role) → soul (personality/voice, pick an avatar) → skills →
  jobs → memory → autonomy → joins-team-or-isolated. A guided, friendly flow.
- **Add / edit a job.** name → kind → prompt → cadence → allowed skills → target thread → test-run.
- **Add a skill/connector.** choose source, pin a version, grant scopes, pass the trust gate.

## Visual direction
- **Platform:** Windows desktop app, primarily. Design for a resizable window (~1280×800 baseline),
  but keep a sensible min-width layout. Left nav + main content is a good default; propose better if
  you have one.
- **Brand:** deep navy `#0b3f86` + teal `#12a3b8` as primaries, on a light neutral canvas; clean,
  slightly technical, warm. Provide a **dark mode** too. (A logo exists — a ARMADA/"material capture"
  sphere mark in navy/teal; I'll drop it in. Leave a spot for it top-left.)
- **Tone:** calm, dense-but-legible, confident. Real typographic hierarchy, generous but efficient
  spacing. Status uses green/amber/red sparingly. Give agents **avatars** (the personas are named
  after historical figures — Marcus Agrippa, Warren Buffett-esque "Warren", etc. — so tasteful
  monogram/portrait-style avatars fit).
- Include **empty, loading, and error states** for the main screens, and a couple of realistic
  **micro-interactions** (running a job, a job failing, an approval arriving).

## Sample data to populate the mocks (make them feel real)
Realm: **"The Cabinet"** (State theme). Coordinator: **Marcus** (the Hand). Ministers: **Warren**
(Finance), **Ray** (Strategy), **Galen** (Health), **Steve** (Development), **Aristotle**
(Education), **Ibn Battuta** (Travel), **Palladio** (Estate). Example jobs: "Daily Brief · weekdays
14:00", "Intraday Radar · weekdays 16:00", "Whoop pull · daily 13:00", "Price watch · daily 08:00",
"Weekly Signal Scan · Sun 18:00". Example skills: `web-search@1.2.0 [network]`,
`market-data@0.4.1 [network, connectors]`. Telemetry: ~430k tokens / 30d, ≈ $18 api-equivalent.
Statuses mostly green, one amber (a job with issues), one agent "planned/not yet established".

## Deliverables
1. A **component system** (nav, cards, tables, chips, buttons, status, tabs, modals, forms, the
   agent avatar treatment) in light + dark.
2. **High-fidelity mockups** of screens 1–9 above, in the State/Cabinet theme, plus **one screen
   re-skinned as Company** to prove the theming.
3. The **three create/manage flows** as step sequences.
4. A short rationale for the navigation model and any key layout decisions.

Start with the **realm overview** and the **component system**, show them to me, and we'll iterate
screen by screen from there.
