# UI audit — the Phase 4 backlog

*Phase 4, step 4.2. Written 2026-09-24 (Opus 5.5) against v0.99.42, from the rendered golden pages,
the component helpers, and a walk through every page of the live app in light and dark mode at
desktop and narrow widths. Each ticket names the pages, the problem, the fix against
[`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md), a size (S ≤ 1h · M ≤ ½ day · L > ½ day) and who should do it.*

**How to work this list** (the Haiku procedure is in [`dev/HAIKU_AGENT.md`](HAIKU_AGENT.md)):
one ticket, one commit, suite at baseline, golden diff read line by line, a screenshot of the page
before and after. Tickets are ordered: do **F1** first — every later ticket depends on the classes
it adds. Within a section, top to bottom. Mark a ticket `[x]` with the version it shipped in.

Model key: **H** Haiku 4.5 · **S** Sonnet 5 · **M** needs Mihai.

---

## Already fixed during the audit

- [x] **D1** Dark mode: every `--text-*` / derived token resolved against the light ink (declared
  on `:root` only) — muted text was near-black on near-black. **v0.99.41**, guarded by
  `tests/test_dark_tokens.py`.
- [x] **D2** Dark mode: widget title bars `#eee`; `--color-neutral-200…900` had no dark values
  (Usage bar tracks pale); compaction gauge track `#fff`. **v0.99.42**.

## F — Foundation

- [x] **F1** *(committed 2026-09-24, ships with the next release)* Add every class marked *new* in DESIGN_SYSTEM.md to `brand.css` (`.btn-sm`,
  `.btn-danger`, `.btn-secondary.is-danger`, `.btn-link`, `.mc-iconbtn`, `.mc-x`, `.mc-pill` +
  tones, `.mc-chip`, `.mc-count`, `.mc-field`, `.mc-label`, `.mc-textarea`, `.mc-hint`,
  `.mc-h-page`, `.mc-eyebrow`, `.mc-h-card`, `.mc-h-sect`) and the tokens `--status-bad-16`,
  `--accent-16`, `--accent2-16` (in the `:root,.armada-dark` rule). Set ARMADA's md button
  (12.5px / 6px 14px) on `.btn` and put `color:#fff` in `.btn-primary`. **Acceptance:** golden
  suite unchanged except where `.btn`'s new defaults already matched inline styles (expect zero
  diffs — classes nobody uses change nothing). S · **S**

## B — Buttons

- [x] **B1** *(v0.99.68)* Strip `color:#fff` from every `btn-primary` call site (45 in `webui/*.py` + JS) now that
  the class carries it. H · **H**
- [x] **B2** *(v0.99.68)* Replace inline button sizes with the class: md needs nothing, sm gets `.btn-sm`.
  Collapse the outliers — `4px 10px`, `5px 10px`, `5px 12px`, `6px 12px`, `11.5px` — onto sm/md.
  All pages; do it one file at a time (≈10 commits). M · **H**
- [x] **B3** *(v0.99.68)* Filled danger buttons → `.btn-danger`: memory delete (`mem-del-modal`), capability
  remove (`mc-cap-del`, and the Remove in `mc-cap-modal`), goal delete (`goal-del-modal`, and in
  `goal-edit-modal`), widget remove (`mc-twdel-modal`), section delete (`sec-del-modal`), thread
  delete (JS in `threadlist.js`). S · **H**
- [x] **B4** *(v0.99.68)* Red-outline entry buttons → `.btn-secondary.is-danger`: "Delete section" (Edit
  section page), Settings realm delete/archive, anywhere else `color:var(--status-bad)` sits on a
  secondary. S · **H**
- [x] **B5** *(v0.99.68)* Dialog button order → right-aligned, Cancel then confirm (as `mcConfirm`): today every
  *form* dialog is left-aligned, primary first — `mem-add-modal`, `mem-edit-modal`, `mc-cap-modal`,
  `goal-add-modal`, `goal-edit-modal`, `mc-twren-modal`, `mc-thren-modal`, `mc-addsec-modal`.
  Delete dialogs already follow the rule. Move each dialog's status span to the left of the row.
  M · **H**
- [x] **B6** *(v0.99.68)* `mc-conn-modal` ends with **Close**, **Refresh from Claude** and **OK** — two dismiss
  buttons. Keep Close + the primary; drop OK. S · **H**
- [x] **B7** *(v0.99.68)* Page-header create buttons disagree: "+ Appoint" (secondary, text `+`), "Add goal" and
  "Add memory" (secondary, plus icon), "New job" (**primary**), "+ New realm" (secondary, text
  `+`). All become `.btn.btn-secondary.btn-sm` with `_icon("plus", 14)` and no typed `+`. S · **H**
- [x] **B8** *(v0.99.68)* Redundant `display:inline-flex;align-items:center;gap:5px` on buttons — `.btn` already
  does it. Remove as part of B2 in the same files. — · **H**

## I — Icon buttons and closes

- [x] **I1** *(v0.99.68 — the plain icon buttons; `mc-um`, `mc-jc-nav`, `mc-jc-view` and `mc-jv` are toggles whose inline colours carry their on/off state, so they keep them)* Icon buttons → `.mc-iconbtn` (one grey, `--text-muted`, hover to text): `mc-act`
  (turn actions), `mc-wdots` (widget ⋮, `--text-65`), `mc-thdots`, `mc-um` (user menu),
  `mc-usage-refresh`, `mc-jc-nav`/`mc-jc-view` (calendar), `mc-jv` (Jobs view toggle), the
  capability-connectors refresh. Keep each one's own class for its JS hooks. M · **H**
- [x] **I2** *(v0.99.68)* Dialog close × → `.mc-x` (the 20px `×` button: 5 source sites render on ~20 pages). S · **H**

## P — Pills, chips, counts

- [x] **P1** *(v0.99.69)* One pill tint (16%): `catalogue._cat_pill` (14%), `goalsview._goal_status_badge`
  (15%), `capabilities._cap_new_badge` (18%) → the `-16` tokens. S · **H**
- [x] **P2** *(v0.99.69)* Hand-drawn pills → `.mc-pill.is-*`: goal status badge (10.5px, 2px 9px), Settings →
  Engine "Connected" / "Coming soon", Settings `_soon_pill`, every `mc-cap-pill` call site (16)
  moves to `.mc-pill` + a tone class instead of inline colours. M · **H**
- [x] **P3** *(v0.99.69)* `_base._mini_pill` → `.mc-chip` (it's a chip; rename the helper `_chip`). Model chip
  (`agentbits._model_chip`) keeps its layout but takes `.mc-chip` for the shape. S · **H**
- [x] **P4** *(v0.99.69)* Nav/tab unread counts → `.mc-count` (the accent 999px badge repeated on 17 pages). S · **H**

## T — Type and headings

- [x] **T1** *(v0.99.69)* `_base._page_title` emits `.mc-h-page` + `.mc-eyebrow`; the agent frame title takes
  `.mc-h-page.is-agent`. S · **H**
- [x] **T2** *(v0.99.69 — Settings cards, Memory, Inbox → `.mc-h-sect`; the agent-tab headings (Jobs, Inbox, Goals) stay at their shared 17px, and Jobs now reads "Jobs · N active · X owns")* Section headings drawn inline (Agent → Jobs "Active jobs · 4 · Warren owns", Memory
  "Per-agent memories", Settings card headings, Inbox "New messages") → `.mc-h-sect`, and the
  agent-Jobs one reads like its realm counterpart ("Jobs · 4"). S · **H**
- [x] **T3** *(v0.99.69)* Dialog titles (16px heading, repeated in every modal) → `.mc-h-card`. S · **H**

## FI — Fields and filters

- [ ] **FI1** `_FIELD` (66 references), `_LBL` (84), `_TA` → `.mc-field`, `.mc-label`,
  `.mc-textarea`; then delete the constants. L · **H** (one file per commit)
- [ ] **FI2** Inbox filters are native `<select>`s (and one drawn at 12.5px / 6px 9px) with a
  "Clear" link — every other list filters with `mc-fdrop`. Rebuild with `_filter_dropdown`, a
  fixed width each, "Clear" as `.btn-link`. M · **S** (touches inbox JS)
- [ ] **FI3** Artefacts' "Touched" date range uses native date inputs: they render in the
  *browser's* locale (`mm/dd/yyyy` here, on a Madrid machine), wrap onto a second row at ~1000px,
  and the "Touched" label is Title case beside an UPPERCASE "FILTER". Replace with a small
  preset `mc-fdrop` ("Any time / Today / 7 days / 30 days / Custom…"). M · **S**
- [ ] **FI4** Filter-bar order (§11): Capabilities and Jobs put their dropdowns in different orders
  (type → agent → source → risk vs owner → status → cadence). Apply who → what → state. S · **H**

## TB — Tabs and tables

- [x] **TB1** *(v0.99.69)* Settings' Realm / User / App tabs are hand-drawn buttons → `.mc-captab`. S · **H**
- [x] **TB2** *(v0.99.69 — checked: every `<table>` already uses `.table`, with only widths/alignment inline; the Jobs and System jobs lists are grids by design, not tables)* Tables → `industry.css .table`: Jobs list, the Register widget, Artefacts, the agent
  Jobs tab, System jobs. Keep column widths inline; drop the per-`th` font/case/colour. M · **H**

## C — Copy and words

- [x] **C1** *(v0.99.66)* Jobs legend reads "-/+3D JOB OUTCOME AND OUTLOOK" — cryptic. → "Last 3 days · next 3
  days" (the strip is ±3 days around today). S · **H**
- [ ] **C2** **Dates come in six formats**: `Thu 9/24, 22:30` (Jobs next run — US month/day, on a
  European owner's machine), `17/09/26` (minister appointed), `19-09-26 14:40` (artefacts),
  `21-09-26` (memory, goals), `01 Oct 2027` (goal ETA), `Thu 24th` (Register next run). Add one
  formatter to `webui/schedfmt.py` implementing DESIGN_SYSTEM §9a and route every date through it —
  including `static/js/sysjobs.js`'s copy. M · **S**
- [x] **C3** *(v0.99.66)* Inbox: the page subtitle says "tasks your agents have handed each other"; the sections
  say "New messages" and "Message archive". → tasks (§9). S · **H**
- [ ] **C4** **M:** capability risk has two word sets for one red/amber/green scale — "Caution /
  Review / Trusted" (User tab, legend) and "High / Medium / Low risk" (bring-a-link review card).
  Pick one; then a one-commit rename. S · **M**, then **H**

## R — Layout at narrow widths

The app window can be dragged down to ~1000px; a laptop half-screen is about that.

**Correction (2026-09-24, found building 5.5):** it can't. `app.py` opens the window with
`min_size=(1400, 700)` on purpose (the Capabilities list and the dashboard grid need it), so the
app window never goes below 1400px wide. What these tickets describe is real only in a browser
tab on `armada serve`, or on a screen narrower than 1400px (where the window is larger than the
screen, which is its own problem for a small laptop). So: R1–R4 drop to **after the beta** unless
a beta user has a sub-1400px screen; the question to ask instead is whether 1400 is the right
minimum (a 1366×768 laptop can't show the whole window).

- [ ] **R1** Every page shows a horizontal scrollbar at a 1000px-wide window (seen on all pages
  walked; the threshold wasn't measured). Find the fixed-width element; let the nav wrap or scroll
  inside itself. M · **S**
- [ ] **R2** Jobs list: the Job column squeezes to ~100px and each description wraps into a
  6–10-line row; give the Job column a `min-width` and clamp descriptions to two lines. S · **H**
- [ ] **R3** Capabilities cards clip the "Can touch" column at ~1000px; stack Runs / Can touch
  under the name below a breakpoint. M · **S**
- [ ] **R4** Jobs toolbar: "Status as of … ⟳" and the legend each take their own row even when
  there's room beside the filters. S · **H**

## L — Leftovers carried from Phase 2 (were 4.3 (a)–(f))

- [ ] **L1** Externalize `webui/_core._WIZ_JS` (61-line new-realm wizard) to
  `static/js/newrealm_wizard.js`. S · **H**
- [x] **L2** *(v0.99.66)* Confirm `serve.APP_HTML` is unreferenced; delete it. S · **H**
- [ ] **L3** The ~30 `color-mix(` calls in `static/js/*.js` → the 2.2 tokens. M · **H**
- [x] **L4** *(v0.99.45)* Lock `routes/agents._save_agent`'s `agent.json` read-modify-write (it races
  `capabilities.py`'s locked grant writes). With a test. S · **S**
- [x] **L5** *(v0.99.45 — locked, kept in the render path; the no-change case takes no lock)* Thread `meta.json` written during a render (`_touch_last_thread`,
  `_clear_thread_unread`) and `_load_dashboard`'s migration write: lock them, or move the writes
  out of the render path. With a test. M · **S**
- [x] **L6** *(v0.99.66)* Effort dropdown lacks `xhigh`, which the runner accepts. S · **H**
- [x] **L7** *(v0.99.54 — `sysjobs.run_one` stamped `last_run` with real time while the page read the
  frozen clock, and the boot-time system job raced the first render; both fixed, both regolded)* Golden pages `jobs` and `agent_threads` have been failing since before 2.1 and are
  left un-regolded every release, so they no longer guard anything. Find why they differ (the
  2.1/2.2 analysis saw both accumulated legitimate changes and at least one date/number change
  under a frozen clock — `Mon`→`Fri`), fix the source of any real nondeterminism, regold, and
  remove the `git checkout` step from `dev/HAIKU_AGENT.md`. M · **S**
