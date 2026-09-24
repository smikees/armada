# Handoff: ARMADA — multi-realm agent dashboard

## Overview
ARMADA is a desktop app for running a "cabinet" of AI agents (a realm). The owner appoints agents (the Hand + ministers), gives each a base prompt, soul, model, effort and humour level, grants skills/connectors, schedules jobs, chats in scoped threads, and reviews memory and artefacts. This package covers the **current, approved direction**: the realm dashboard, the full agent frame with all seven sub-tabs (Overview, Threads, Jobs, Skills, Memory, Artefacts, Configure), and the Job detail page. Realm-wide Memory/Skills/Artefacts, create flows (setup wizard, Add agent/job/skill), Settings, Approvals inbox, Scheduler and the "Board of Executives" re-skin are **not designed yet** — see "Out of scope".

## About the design files
Everything in this bundle is a **design reference built in HTML** (`ARMADA.dc.html` + `assets/` + the Industry design-system stylesheet). It is a prototype that shows the intended look and behaviour; it is not production code and should not be shipped. Recreate these screens in the app's existing stack (React/Electron, Tauri, Swift, etc.) using its component and state patterns. If no stack exists yet, a desktop shell (Electron or Tauri) with React + CSS variables is the closest fit to how the prototype is structured.

Open `ARMADA.dc.html` in a browser to see every screen. It is a canvas of turns, newest at the top: **turn 4** (Job detail, `#4a`) and **turn 3** (agent screens `#3a`–`#3f`) are the approved direction; **turn 2** holds the dashboard (`#2b` light, `#2c` dark edit-layout) and the component sheet (`#2a`); **turn 1** is superseded exploration (ignore `#1a`–`#1d`). Anchor ids (`#3c` etc.) jump to a screen. Every screen is a 1280 × 800 desktop window, with a 32 px OS title bar included in the frame.

## Fidelity
**High-fidelity.** Colours, type, spacing, states and copy are final. Recreate pixel-close. Two caveats: (1) the prototype is static except for the Jobs collapsibles and telemetry tooltips — behaviour is described below; (2) the wordmark uses the brand font Heavitas (`assets/Heavitas.ttf`, loaded via @font-face).

---

## Frame shared by every screen

Layout, top to bottom (all screens 1280 wide, content area scrolls internally — the window never scrolls):

1. **OS title bar** — 32 px, `--color-surface`, no bottom rule. Left: 16 px grid mark, then `ARMADA — <Realm> — <Context>` in 12 px at 70 % text. Right: `– ☐ ✕` in 46 px wide cells.
2. **Top nav** — `display:flex; align-items:center; gap:22px; padding:4px 24px 0`, no bottom rule.
   - Logo (54 × 24 inline SVG, see Assets).
   - **Realm switcher**: 1 px `--color-divider` frame, 4 px radius, `padding:5px 10px`, `🏛️` glyph (replace with the realm's icon) + realm name in Barlow Condensed 600 15 px + up/down chevrons (Lucide `chevrons-up-down`, 12 px, 60 % opacity).
   - **Realm tabs** (`.mc-tab`): Barlow Condensed 600 15 px, `padding:9px 2px`, 62 % text colour, 2 px transparent bottom border; hover → full text colour; current → full text + `--color-accent-2` (teal) bottom border. Tabs: Overview · Ministers ▾ · Jobs · Memory · Skills · Artefacts. Then a 10 px gap, then **user-added sections** (`.mc-tab-user`): Barlow 500 13.5 px italic, current state uses a *dashed* teal underline. Then a `chevron-right` (14 px) "More sections" affordance.
   - Right cluster, `margin-left:auto; gap:16px`: Engine status (8 px dot `--status-ok` + "Engine", 12 px 70 %), bell icon (Lucide `bell` 18 px, 70 %) with a red count badge (min-width 15 px, height 15 px, radius 8 px, `--status-bad`, white 9.5 px 700), settings gear (Lucide `settings` 18 px, 70 %).
3. **Breadcrumb** (`.mc-crumb`): `padding:8px 24px 0`, 12 px, 60 % text, `›` separators, links → full text on hover, last item weight 500 full colour. E.g. `The Cabinet › Ministers › Warren › Jobs › Daily Brief`.
4. **Agent header** (agent screens only): `padding:12px 24px 0; display:flex; gap:16px; align-items:center`, no bottom rule.
   - Portrait: 56 px circle, 1 px `--color-divider` border, `--color-sand-100` fill, `overflow:hidden`, `margin-bottom:12px`. Image is `object-fit:cover; transform:scale(1.3); transform-origin:50% 30%` so the illustration fills the circle with no whitespace below the bust.
   - Row 1 (`align-items:baseline; gap:10px`): name Barlow Condensed 600 26 px; role 11 px uppercase `letter-spacing:.08em` `--color-accent-700`; status (8 px dot + 11 px 60 % text, e.g. "idle · next 14:00" or teal pulsing "running Daily Brief"); **model pill** (`.tag` 1 px frame, 10.5 px, `padding:1px 7px`, "Claude Sonnet 4.5 · medium" where "· medium" is 55 % opacity, chevron-down 10 px) — clicking opens the model/effort picker; right-aligned monospace 11 px 45 % "appointed 12 Mar 2026".
   - Row 2 sub-tabs (`.mc-sub`): 13 px, `padding:8px 0; gap:16px`, 62 % text, 2 px transparent bottom border; current → full text + `--color-accent` (navy) bottom border. Counts after label at 50 % opacity: Overview · Threads · Jobs 3 · Skills 4 · Memory 12 · Artefacts 6 · Configure.
5. **Body**: `flex:1; min-height:0; display:grid; grid-template-columns: 1fr 320px` (Threads: `220px 1fr 300px`). Centre column `overflow:auto; padding:18px 28px 24px 24px`. Right rail `background:--color-surface; padding:18px 24px; display:flex; flex-direction:column; gap:14px`, **no border-left** — the surface tint is the separator. Rail section labels: 10 px uppercase `letter-spacing:.1em` 55 % text.

**Principle: no decorative hairlines.** Separation comes from surface tint, whitespace and type weight. Keep 1 px rules only inside tables/lists (row rules) and on collapsible section headers.

---

## Screens

### 1. Realm dashboard — Overview (`#2b` light, `#2c` dark + edit mode)
Purpose: the realm at a glance; a rearrangeable widget grid.
- Header row under the nav: five spec-sheet KPIs (label 10 px caps 55 %, value Barlow Condensed 600 26 px, sub 11 px 55 %): Agents 8 · Jobs 12 · Runs 214 /30d · Tokens 430k /30d · API-eq ≈$18. Right: `Edit layout` secondary button.
- Grid: `grid-template-columns: repeat(4,1fr); grid-template-rows:auto 1fr; gap:14px`.
  - **Register** (cols 1–2, both rows): table of agents — portrait 40 px with status dot bottom-right (9 px, 1.5 px `--color-bg` ring), name (Barlow Condensed 600 17 px) + role (10.5 px caps `--color-accent-700`), autonomy icon, jobs/next, 7-day health bars (7 × 7 × 14 px, gap 2: teal ok / `--status-warn` / `--status-bad` / `--color-neutral-300` missed), tokens.
  - **From the Hand** (cols 3–4, row 1): `--color-accent-2-100` fill, border 50 % teal; the Hand's portrait + a quote in Barlow Condensed 600 16–19 px + two actions.
  - **Attention** (col 3, row 2): list of Failure / Approval / Decision items — dot, kind + who (11 px), text 12.5 px, age; Approvals show `Approve` primary + `Deny` secondary + ghost `Context`.
  - **Today** (col 4, row 2): time-ordered runs (monospace time, job, agent, note; future rows 60 % opacity).
- **Widget chrome** (`.mc-widget`): 1 px `--color-divider` border, `--color-bg` fill, header `padding:8px 12px` with a grip icon (Lucide `grip-vertical` 12 px) that is `opacity:0` and fades to `.55` on hover (150 ms), title Barlow Condensed 600 15 px, meta 10.5 px 50 %. User-added widgets use a dashed header rule.
- **Edit layout mode**: every widget gets `outline:1px dashed` 70 % teal, `outline-offset:3px`; grips at `.8`; the dragged widget lifts (`rotate(-.6deg) translateY(-4px)`, `--shadow-lg`, teal border); a 12 px teal L-shaped resize handle appears bottom-right; an **Add widget** slot (dashed frame) lists the library: Health grid 2×1, Approvals inbox 1×1, Token usage 1×1, Recent runs 2×1, plus user sections in italic. `Done` returns to view mode. Persist layout per realm.

### 2. Agent · Configure (`#3a`)
Body `1fr 320px`. Centre: sections as `grid-template-columns:170px 1fr; gap:20px`, stacked with `gap:22px`. Left cell = section title (Barlow Condensed 600 16 px) + 11.5 px 55 % explainer.
- **Identity**: Name input; Mandate input (read-only, 60 % opacity, lock icon); **Base prompt** textarea on the "owner-authored" treatment: `background:--color-sand-100; border-color:--color-sand-500`, 13 px/1.45, label suffix "· ~180 tok · in your words"; **Avatar** row: dashed-circle Upload tile (40 px, `--color-accent` upload icon) first, then 20 illustrated tiles (40 px circles); selected tile has navy border + `0 0 0 2px --color-bg, 0 0 0 3px --color-accent` ring; then a 3-column row `1.15fr .95fr 1fr`:
  - **Model**: `.input` dropdown "Claude Sonnet 4.5 · Anthropic"; menu grouped by provider with header (10 px caps: Anthropic — Claude Max · OpenAI — not connected · Local — Ollama) and rows (name + note "deepest · slow / default / fast · cheap"; selected row `--color-accent-100` + navy check).
  - **Effort**: segmented control Low · Medium · **High** · Max (Medium selected: navy fill, white text), label suffix "· thinking budget", helper "Default for every thread and job; each may override."
  - **Humour** 0–9: ten bars (heights 8 → 20.6 px, gap 3), bars ≤ value navy-filled, value bubble (16 px navy circle, white 9.5 px 700) above the selected bar; scale text "0 · deadpan / 3 · a wry line now and then / 9".
- **Soul**: Voice textarea (sand treatment); **Tenets** list (sand frame, numbered `01 02 03` monospace `--color-sand-700`, rows 12.5 px, "+ Add a tenet" navy link).
- **Autonomy**: icon radio group (`.mc-auto`: 34 × 30 px cells, 1 px frame, checked = navy fill white icon) — propose-only (message-square), act in folder (folder), act with connectors (plug), autonomous (zap) — with title + explainer; two toggles (`.mc-tog` 32 × 18, navy on / `--color-neutral-400` off): "Joins cabinet cross-talk", "Whitelist: send email to broker".
- **Skills & connectors**: monospace chips `name@version | scope` + `+ Grant` outline tag; link "Manage in Skills →".
- **Dismiss**: red (`--status-bad`) title, explainer, red-outlined secondary button "Dismiss minister…". Confirm in a dialog.
- Rail: "Preview · as seen in the register" card (portrait, name, role, autonomy icon, persona line, meta); "What Warren loads · every run" list (Base prompt ~180 tok, Soul + tenets ~460, Realm memory, Warren's memory, Thread history — sand rows for owner-authored items); bottom: "N unsaved changes · written to agents/warren/agent.yaml" + Discard / Save (full-width pair).

### 3. Agent · Overview (`#3b`)
Centre: 2-col grid — **Soul** card (sand fill, kicker 10 px caps `--color-sand-700`, headline Barlow Condensed 600 19 px, body 12.5 px, autonomy line, "Configure →") and **Latest** card (last messages of main thread + live "Warren is thinking · loading 'taxes' sub-thread…" with pulsing teal dot). Then **Jobs** table (Job · Kind tag · Cadence mono · Thread · Last run dot+text · 7d bars · ghost `Run` button). Then 2-col **Threads** list and **Memory** preview (two sand notes + "+10 more").
Rail: **Telemetry · 30 days** — 2 × 2 KPIs (Tokens 128k "30 % of realm", API-eq ≈$5.40 "quota, not billed", Runs 64 "62 ok · 2 issues", Avg run 2m 14s "2.0k tok"); 30-bar sparkline (bars `flex:1`, teal, hovered bar `--color-accent-2-600` with a dark tooltip "24 Aug · 5.4k tokens · ≈$0.23" — tooltip is `--color-text` bg, `--color-bg` text, 10.5 px, radius 3, 7 px rotated caret); axis labels 10 px 50 %; **Waiting on you** approval card (Approve / Deny / Context); bottom pair `Open main thread` / `Ask Warren`.

### 4. Agent · Threads (`#3c`)
Body `220px 1fr 300px`.
- Left list: label "THREADS" + navy `+`; rows `padding:8px 16px`, name 13 px (main 600) + right monospace time, sub-line 11 px 55 % ellipsised; selected row `--color-accent-100` with 2 px navy left bar. Foot note 11 px 50 %: "Sub-threads scope memory…". Threads: main · taxes · ira-rollover · Daily Brief · outputs (job thread).
- Centre header (`padding:12px 20px 6px; flex-wrap:wrap; gap:10px`): **editable thread name** — name (Barlow Condensed 600 17 px) + pencil icon (Lucide `pencil` 12 px, 45 %) in a hoverable pill (`cursor:text`); click → inline text input in the same type, Enter/blur saves, Esc cancels, empty reverts; `main` cannot be renamed. Meta 11 px 55 % "sub-thread · 38 messages · compacted twice". **Per-thread model/effort pill** ("Claude Opus 4.1 · high", border `--color-accent-300` when overriding) opening the same provider-grouped picker plus the effort segment; when it overrides the agent, a 10.5 px note "overrides Warren's Sonnet 4.5 · medium · reset" (reset = navy link, returns to inherit). Right: ghost `Compact now`, `Export`.
- Transcript (`padding:14px 20px; gap:14px; 13px/1.5`): compaction summary chip centred (1 px frame, surface fill, archive icon, "expand" link); agent messages = 28 px portrait + "Warren · Tue 13:02" 11 px 55 % + text; user messages `flex-direction:row-reverse`, 28 px navy circle "You", bubble max-width 70 % in sand frame; tool-use footnote (1 px frame, surface fill, "Used market-data@0.4.1 · 1 call · 1.9k tokens · 6.2s · trace"); typing indicator with pulsing dot.
- Composer (`padding:8px 20px 16px`): framed row — round 28 px `+` icon button (attach file/artefact), borderless textarea "Ask Warren in the taxes thread…", primary `Send`.
- Rail "Loaded context · this reply": 8 px stacked proportion bar (navy base / sand-500 realm memory / sand-300 agent memory / teal compaction / neutral-300 recent), per-item cards (colour square, name, monospace tokens, desc), "Not loaded: … keeps this reply at **7.2k** tokens", foot "Compacts at 40k · core context always present".

### 5. Agent · Jobs (`#3d`)
Centre: title row "Jobs · 3 · Warren owns" + primary `+ New job`; jobs table (no outer frame; selected row `--color-accent-100` + 2 px navy left bar; columns Job · Kind · Cadence · Thread · Skills · Last run · 7d). Then the **selected job** as a stacked, full-width block:
- Title row: "Daily Brief" 17 px, `agent job` tag, teal running pill "running · 0:47"; right: "Open full page →" link, `Edit` secondary, disabled primary "Running…" with pulsing white dot.
- **Settings** collapsible: header row (`padding:9px 6px`, 1 px top rule, hover tint, chevron-right rotating 90° over 150 ms when open, title Barlow Condensed 600 14.5 px, summary 11.5 px 55 %: "· prompt · weekdays 14:00 · → main · Sonnet 4.5 · medium · 2 skills"). Body (`padding:2px 6px 18px 28px`): prompt on sand treatment, then a 5-column key/value grid (Kind, Cadence, Target thread, Model · effort "Sonnet 4.5 · medium · inherited", May use).
- **Status** collapsible: header with summary "· run #65 in progress · 64 runs · 97 % healthy" and the 7-day bars right-aligned. Body: `260px 1fr` — live step log (monospace 11 px: ✓ context · 2.1k tok, ✓ brokerage.positions() · 1.2s, ✓ market-data.quotes(14) · 2.8s, → writing brief…) beside the streaming output box (1 px frame, 12.5 px/1.55, teal 7 × 12 px blinking caret); then "RUN HISTORY" rows (grid `110px 10px 1fr 70px 60px`: when mono · status dot · output ellipsised · duration · tokens).
- Both sections default open; persist open/closed per user.
Rail: "Next 7 days · Warren" (mono time · job rows), "Health · 7 days" grid (job rows × 7 day columns F S S M T W T, 18 px cells radius 2), foot note.

### 6. Agent · Skills & Connectors (`#3e`)
Two sections (Skills, Connectors), each split into **Third-party** and **User-created** groups with counts. Rows: name (link to detail) + source tag (`core` navy tag, `verified` teal tag, `yours` neutral), description, version + update note ("0.4.2 available"), scope chips (network / connectors / files), used-by, calls, enable toggle. Connectors also show a status dot + state ("linked · 2 accts", "token expires 12 Sep" warn). A community skill shows a **trust gate** before enabling. Rail: lockfile view (`skills.lock`).

### 7. Agent · Memory (`#3f`)
Warren's notes as sand cards: text, creator avatar ("W" sand circle or navy "You"), created date, source thread, tag (`by you` / `learned` / `learned · unconfirmed` in `--color-accent-2-100` / `-800`). A newly learned note is highlighted (bg `--color-bg`, teal border, `--shadow-sm`) with **Keep / Promote to realm / Forget** actions. Realm memory is one link away. Rail: scope legend (realm = everyone, agent = only him, thread = scoped).

### 8. Job detail — full page (`#4a`)
Breadcrumb `The Cabinet › Ministers › Warren › Jobs › Daily Brief`. Header: title 26 px, `agent job` tag, teal running pill, enabled toggle + "enabled"; owner strip (22 px portrait, "Owned by **Warren** · Minister of Finance · weekdays 14:00 ET · → main thread · 64 runs · 97 % healthy", right mono "created 12 Mar 2026 · agents/warren/jobs/daily-brief.yaml"); actions `Duplicate`, `Stop run`, disabled primary `Running…`.
Body `1fr 1fr`:
- **Definition** (left, editable): Prompt textarea (sand) with "Insert variable ▾" and variable chips (`maxWords = 120`, `today`, `lastRun.output`); 3-col row **Kind** segment (Agent · prompt / Command · script) · **Target thread** dropdown · **Model · effort** dropdown ("Sonnet 4.5 · medium", label "· Warren's default"); **Cadence** frame: preset chips (Weekdays selected navy · Daily · Weekly · Monthly · On demand · Custom), day-of-week circles (28 px; on = `--color-accent-100` fill / `-800` text / `-300` border), time input `14:00`, timezone dropdown, footer with read-only cron `0 14 * * 1-5` + "edit cron" + "Next: Fri 14:00 · Mon 14:00 · Tue 14:00"; **Allowed skills** chips (✓ checked navy border, unchecked 50 %); **On failure** dropdown "Retry ×3, then alert me"; **Budget per run** "8k tokens · ≈$0.35 api-eq"; sticky footer "1 unsaved change · prompt" + Discard / Test run / Save.
- **Execution** (right, `--color-surface`): "Run #65 · started 14:00:02 · manual: no · 0:47 · 1.4k tok so far"; step log + streaming output; **Run history** header with 7-day bars; rows grid `20px 90px 1fr 56px 52px 60px` (# · when · dot+output · dur · tok · trigger tag SCHED/TEST); an issue row expands inline (warn icon + message, output excerpt, `Open in thread` / `Re-run` / ghost `Trace`).

---

## Interactions & behaviour
- **Navigation**: realm tabs switch the realm section; sub-tabs switch within an agent; breadcrumb items are links. Realm switcher opens a list of realms (+ "New realm").
- **Live state**: running = teal dot with `mc-pulse` (1.6 s infinite: box-shadow 0 → 6 px teal 60 % → transparent); streaming text ends in a 7 × 12 px teal caret pulsing 1 s. ok = `--status-ok`, issue = `--status-warn`, failed = `--status-bad`, idle = `--status-idle`.
- **Hover**: rows (`.mc-row`) tint `color-mix(text 4%)`; agent cards get 45 % text border + `--shadow-sm`; buttons/tags per Industry (accent ramp one step darker on press). Focus ring: `outline:2px solid --color-accent; outline-offset:2px`.
- **Collapsibles** (Jobs): click header toggles; chevron rotates 0 → 90° over 150 ms; content height animates ~150 ms ease.
- **Rename thread**: pencil/click on name → inline input; Enter/blur save, Esc cancel; validate non-empty, unique within agent.
- **Model/effort picker** (agent header pill, Configure, thread pill, job field): popover, providers grouped, unavailable providers ("not connected") disabled with link to Settings; effort segment below. Thread/job pickers show an "Inherit from <agent>" option (default) — an override adds the note + reset link.
- **Tooltips**: sparkline bars on hover show the dark tooltip; 0 ms delay, follow the bar.
- **Approvals**: Approve/Deny act immediately with an undo toast; Context opens the originating thread.
- **Edit layout**: drag to reorder (grid snap), corner handle to resize in cell units, Add widget slot; Done persists.
- **Empty / loading / error states**: not yet designed — use skeleton rows in list positions and a one-line empty message in 12.5 px 55 % text until designed.

## State management
- `realm` (id, name, sections incl. user-added), `agents[]` (name, role/mandate, basePrompt, voice, tenets[], avatar, model, effort, humour 0–9, autonomy enum, toggles, grants[], appointed, status).
- `threads[agent]` (id, name, kind main|sub|job, messages, compaction summaries, modelOverride?, effortOverride?).
- `jobs[agent]` (name, kind agent|command, prompt, variables, cadence {preset, dow[], time, tz, cron}, targetThread, allowedSkills[], onFailure, budget, modelOverride?, effortOverride?, enabled, runs[]).
- `runs` stream (steps, output tokens, duration, status, trigger).
- `memory` (realm notes, agent notes with creator/date/thread/state).
- UI: selected job, collapsible open flags, dashboard layout per realm, edit-layout mode, dark mode, unsaved-change counts per form.
- Files on disk mirror the model (`agents/warren/agent.yaml`, `agents/warren/jobs/daily-brief.yaml`, `skills.lock`) — show the path wherever a save writes.

## Design tokens
Base is the **Industry** design system (`industry-design-system/styles.css`) with brand overrides; use these variables, never raw values.

Colours (light): `--color-bg #f2f2f3` · `--color-surface` (Industry) · `--color-text #1d1f20` · `--color-divider` (Industry) · accent (navy) `--color-accent #0b3f86`, ramp 100 `#e8eff9` 200 `#cddcf2` 300 `#a6bfe4` 400 `#7599d0` 500 `#3f6bb0` 600 `#0b3f86` 700 `#08306a` 800 `#06234d` 900 `#041733` · accent-2 (teal) `--color-accent-2 #12a3b8`, ramp 100 `#e2f5f8` 200 `#bfeaf0` 300 `#8dd8e2` 400 `#56c1d0` 500 `#12a3b8` 600 `#0e849a` 700 `#0b667a` 800 `#084a59` 900 `#05303a` · sand (owner-authored surfaces) 100 `#e9e9ea` 200 `#dfdfe1` 300 `#d0d0d3` 500 `#b3b3b7` 700 `#6d6d71` 900 `#3a3a3d` · status ok `#2e9c6a` warn `#d08a1c` bad `#c9463d` idle `#98989b`.
Dark (`.matcap-dark`): bg `#0f1520` · surface `#161e2b` · text `#e4e8ee` · divider text 18 % · accent `#7599d0` (100 `#182337`, 200 `#1f2f4b`, 300 `#3a5a92`, 600 `#8fadd9`, 700 `#a9bfe2`, 800 `#c9d8ef`) · accent-2 `#56c1d0` (100 `#0d2a30`, 200 `#134048`, 300 `#1d5a66`, 700 `#8dd8e2`, 800 `#a9e2ea`) · sand 100 `#1c2431` 200 `#222b3a` 300 `#2e3847` 500 `#4a5568` 700 `#9aa3b2` 900 `#d5dae2` · shadows sm `0 1px 2px rgba(0,0,0,.5)` md `0 3px 10px rgba(0,0,0,.5)` lg `0 12px 32px rgba(0,0,0,.6)`.
Muted text is expressed as `color-mix(in srgb, var(--color-text) N%, transparent)` with N = 70 (nav), 65/60 (meta), 55 (labels), 50/45 (timestamps).

Type: headings **Barlow Condensed 600** (26 page title · 19 soul headline · 17 section/thread/job title · 16 configure section · 15 widget/tab · 14.5 collapsible), wordmark Heavitas 24 px (in a 50-unit viewBox); body **Barlow** (13.5 italic user tabs · 13 body/inputs · 12.5 table/cards · 12 meta · 11.5/11 captions · 10.5 pills · 10 uppercase labels `letter-spacing:.1em`); monospace `ui-monospace, Menlo, monospace` for times, cron, versions, paths, tokens (11–12.5 px). Line-height 1.45–1.55 for prose.

Spacing: 24 px page gutter · 18/16/14 px between blocks · 12/10 px inside cards · 8/6 px inline gaps · row padding 8 × 12. Radius: **4 px** everywhere (`--r`), circles for portraits/dots/toggles, 2 px for micro bars. Borders: 1 px `--color-divider`; sand surfaces use `--color-sand-500` (fields) or `-300` (notes) borders. Shadows: Industry `--shadow-sm/md/lg`; dropdown menus `--shadow-md`.

Controls (Industry classes): `.btn-primary` (navy fill, white text), `.btn-secondary`, `.btn-ghost`, `.btn-icon`; `.tag`, `.tag-accent`, `.tag-accent-2`, `.tag-neutral`, `.tag-outline`; `.field`/`.input`; `.seg` + `.seg-opt` (selected = navy fill white text); `.table`; `.dialog`. Custom: `.mc-tog` toggle 32 × 18 px, `.mc-auto` icon radio group, `.mc-tab`/`.mc-sub` tabs, `.mc-widget`, `.mc-frame` (plain 1 px frame — this brand drops Industry's corner registration marks). Disabled controls: 45 % opacity (primary "Running…" uses 60 %).

Icons: Lucide, stroke 1.5, 10–18 px as noted.

## Assets
- `assets/logo.svg` — ARMADA wordmark + mark (5 × 5 grid glyph, navy `#003e7c` / teal `#01a1af`; the prototype inlines it with `var(--color-accent)` / `var(--color-accent-2)` so it recolours in dark mode). Wordmark set in Heavitas (`assets/Heavitas.ttf`); Barlow Condensed is the fallback.
- `assets/mark.svg` — mark only (title bar, 16 px; app icon source).
- `assets/Heavitas.ttf` — brand wordmark font. *(Removed from the repository 2026-09-24: its licence
  for redistribution was never established, and the app now draws the wordmark as a bitmap. The
  prototype falls back to Barlow Condensed.)*
- `screenshots/` — one PNG per screen.
- `assets/avatars/a1–a20.png` — the 20 illustrated portrait tiles (owner-supplied). Render cropped: `object-fit:cover; transform:scale(1.3); transform-origin:50% 30%`.
- `assets/logo.png`, `assets/mark.png` — superseded raster versions; do not use.
- Icons: Lucide (bell, settings, chevrons-up-down, chevron-down/right, pencil, grip-vertical, upload, lock, message-square, folder, plug, zap, archive, play, pause, alert-circle, check).

## Out of scope / not yet designed
Realm-wide Memory, Skills and Artefacts pages · setup wizard · Add agent / Add job / Add skill flows · Settings · Approvals inbox · Scheduler & reliability · the "Board of Executives" (company) theme · empty/loading/error states. Build these on the frame above and the Industry components; flag for design review.

## Files
- `ARMADA.dc.html` — every screen (open in a browser; see anchors above). Requires `support.js` and the design-system folder alongside it.
- `support.js` — prototype runtime (not for production).
- `industry-design-system/` — Industry tokens + component CSS (`styles.css`, `readme.md`, `theme.json`, `_ds_bundle.js`). `styles.css` is the source for all non-brand tokens.
- `assets/` — logo, mark, avatars.
