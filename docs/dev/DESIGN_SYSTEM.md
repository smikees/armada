# ARMADA design system

*Phase 3, step 3.2 — Phase 4's contract. Written 2026-09-24 against v0.99.40 from a survey of every
rendered page (`tests/golden/*.html`) and the component helpers that produce them. Builds on
[`DESIGN_TOKENS.md`](DESIGN_TOKENS.md), which defines the tokens; this defines what's built from them.*

**How to use this.** Each component below has: what it's for, the **canonical spec** (the one way
to draw it), the **class** it should be (existing, or to be added in Phase 4 — marked *new*), and the
**variants seen today** that must converge on it. The Phase 4 audit (`docs/dev/UI_AUDIT.md`) turns every
"seen today" line into a ticket. When the canonical spec here and the code disagree, the code is
wrong — unless the spec is, in which case fix this page first, then the code.

**The goal is not new visuals.** Every canonical spec below is the variant the app already uses
most. Converging on it changes a handful of pixels on the outliers and nothing on the majority.

---

## 1. Principles

1. **One component, one class.** A button, pill, field or dialog is drawn by a class in
   `brand.css`, not by a style string copied into Python. Inline `style=` is for layout
   (position, width, margin, flex) — never for the component's own look. The 2.2 modal classes
   (`.mc-modal-ov`, `.mc-modal-box`) are the model.
2. **Tokens, never values** (DESIGN_TOKENS.md's rule). The exceptions stay the same: `#fff` on a
   filled accent/status fill, and categorical chart palettes.
3. **Colour means something.** Status colours mean status (`ok` / `warn` / `bad` / `idle`), the
   accent means "the app's own action or selection", accent-2 means "live / running / current".
   Nothing is coloured for decoration.
4. **Dense, not small.** The app is a desktop cockpit: 12–13px UI text, 10–11px labels. Nothing
   interactive below 11px; no body copy below 12px.
5. **Same thing, same words.** A concept has one name everywhere it appears (§9).

## 2. Type

| Role | Family | Size / weight | Case | Canonical | Class |
|---|---|---|---|---|---|
| Page title | heading | 26px / 600 | Title | `_base._page_title` | *new* `.mc-h-page` |
| Agent page title | heading | 26px / 600 (the page size, beside the portrait; was specced 20px, kept at 26 as shipped) | Title | agent frame header | `.mc-h-page.is-agent` |
| Page title suffix ("· 4 across the realm") | body | 11px / 400, `.08em` | UPPER | `_page_title(sub=)` | *new* `.mc-eyebrow` |
| Dialog / card title | heading | 16px / 600 | Sentence | modal headers | *new* `.mc-h-card` |
| Widget title | heading | 15px / 600 | Title | `widgets._wid_header` | `.mc-wid-h` (extend) |
| Section heading inside a page | heading | 14px / 600 | Sentence | Settings sub-sections | *new* `.mc-h-sect` |
| Field label | body | 10px / 400, `.06em`, `--text-muted` | UPPER | `_base._LBL` | *new* `.mc-label` |
| Meta / eyebrow | body | 10.5–11px, `.08em`, `--text-soft` | UPPER | widget meta, page suffix | *new* `.mc-eyebrow` |
| Table header | body | 11px, `.08em`, `--text-dim` | UPPER | `industry.css .table th` | `.table` (use it) |
| UI text (rows, cards, menus) | body | 12.5–13px | Sentence | — | — |
| Helper / hint text | body | 12px, `--text-muted` | Sentence | form hints | *new* `.mc-hint` |
| Body copy (docs, memories, chat) | body | 13.5–14px, 1.55 | — | `.mc-md` | `.mc-md` |

*Seen today:* page titles at 20, 22, 26 and 28px — 26px is the page title; 20px is the agent frame;
the Overview's 22px and 28px are the KPI strip's own numbers, not titles, and stay.

## 3. Spacing and layout

Scale in use (px): **4 · 6 · 8 · 10 · 12 · 14 · 16 · 20 · 24**. New code picks from it; odd values
(5, 7, 9, 11, 13) are papercuts unless they align an icon optically — then say so in a comment.

| Where | Value |
|---|---|
| Page gutter (left/right) | 24px |
| Page title → content | 14px (`_page_title`'s margin) |
| Card / frame padding | 12px dense rows · 16px forms · 18px dialogs (`.mc-modal-box`) |
| Widget header | 8px 12px, hairline below |
| Gap between buttons in a row | 8px |
| Gap icon ↔ label | 5px (sm) · 6px (md) — `.btn` already sets `gap:6px` |
| Field stack | label 14px above field (`_LBL`'s margin), 4px label → field |

## 4. Colour usage

| Purpose | Token | Tint strength |
|---|---|---|
| Hover on a neutral control | `--text-7` / `.btn-secondary:hover` | 7% |
| Menu row hover | `color-mix(--color-text 8%)` | 8% |
| Selected segment / open dropdown | `--text-12` | 12% |
| **Pill / badge fill** | tone at **16%** (`--status-ok-16`, `--status-warn-16`; add *new* `--status-bad-16`, `--accent-16`, `--accent2-16`) | 16% |
| Neutral pill / chip fill | `--text-8` (pill) · `--text-7` (chip) | 7–8% |
| Faint row stripe / empty track | `--text-6` | 6% |

*Seen today:* pill tints at 14%, 15%, 16% and 18% for the same idea (`_cat_pill` 14%, goal badge
15%, `_cap_badges` 16%, `_cap_new_badge` 18%). Converge on 16%.

## 5. Buttons

**Variants** (all on `.btn`, which already gives `inline-flex`, `gap:6px`, heading font, `--r` radius):

| Variant | Use | Spec | Class |
|---|---|---|---|
| Primary | the one action a view or dialog is for | accent fill, **white text** | `.btn.btn-primary` — move `color:#fff` into the class |
| Secondary | every other action; Cancel | divider border, transparent | `.btn.btn-secondary` |
| Danger (confirm) | the confirm button *inside* a delete/remove dialog | `--status-bad` fill and border, white text | *new* `.btn.btn-danger` |
| Danger (entry) | the button that *opens* that dialog ("Delete section…") | secondary with `--status-bad` text and border | *new* `.btn.btn-secondary.is-danger` |
| Text action | a low-weight inline action ("Show more", "Reveal") | no border, `--color-accent` text, 12px | *new* `.btn-link` |

**Sizes:**

| Size | Font | Padding | Where |
|---|---|---|---|
| md (default) | 12.5px | 6px 14px | dialogs, forms, page-level actions |
| sm | 12px | 5px 11px | toolbars, card footers, dialog-header "Close", table rows |

`.btn` in `industry.css` defaults to 14px — the design-system base, not ARMADA's. Phase 4 sets
ARMADA's md in `brand.css` and adds *new* `.btn-sm`, so call sites stop carrying sizes.

*Seen today:* 54 distinct button style strings on the rendered pages for, in effect, these seven
variants × two sizes. Paddings 4px 10px, 5px 10px, 5px 12px, 6px 12px collapse into sm or md;
11.5px text becomes 12px; `display:inline-flex;align-items:center;gap:5px` repeated inline is
already what `.btn` does.

**Rules.**
- **One primary per view or dialog.** Two filled buttons side by side means one of them is secondary.
- **Order.** *Dialogs:* right-aligned, **Cancel first, confirm last** — what `mcConfirm`
  (`static/js/confirm.js`) does, and every dialog should match it. *Forms on a page* (an inline
  editor, the Edit section page): left-aligned, **primary first**, then Cancel, then the status
  message (`<span id="…-msg">`) — the actions follow the form's left edge.
- Labels are verbs, sentence case: "Save", "Add to realm", "Remove widget". "OK" only in
  `mcAlert`.
- A button that starts something slow says so while it runs ("Reviewing… 0:42"); disabled
  buttons use `.btn:disabled` (opacity .45), never a restyle.

## 6. Icon buttons and close

| Kind | Spec | Class |
|---|---|---|
| Icon button (row actions, ⋮ menus, refresh) | no border, transparent, padding 3px (16–18px icon) or 4px 6px (with text), `--r` radius, colour `--text-muted` → `--color-text` on hover | *new* `.mc-iconbtn` |
| Dialog close × | 20px glyph, `--text-soft`, `margin-left:auto`, no border | *new* `.mc-x` |

*Seen today:* icon buttons in five greys (`--text-42`, `--text-soft`, `--text-muted`, `--text-dim`,
`--text-65`). One grey (`--text-muted`), one hover. The close × is already consistent (23 of 25) —
it just needs the class.

## 7. Pills and chips

Two badge shapes, on purpose, and the difference is what they say:

| Shape | Says | Spec | Class |
|---|---|---|---|
| **Pill** (fully round) | a *state or judgement*: status, risk, cost, source, "new", "soon" | 10px / 600, padding 1px 8px, radius 999px, fill = tone at 16%, text = tone | `.mc-cap-pill` → rename *new* `.mc-pill` + tone `.is-ok` `.is-warn` `.is-bad` `.is-accent` `.is-accent2` `.is-neutral` |
| **Chip** (`--r` radius) | an *identity or setting*: model + effort, an owner, a scope | 10.5px / 600, padding 2px 8px, `--r`, `--text-7` fill, `--text-62` text | `_base._mini_pill`'s look → *new* `.mc-chip` (+ `.is-accent`) |

*Seen today:* the goal status badge and the Settings "Connected / Coming soon" status are pills
drawn by hand at 10.5px / 2px 9px; `_mini_pill` is a chip that calls itself a pill. Pills converge
on `.mc-pill`; chips on `.mc-chip`.

**Counts** (unread, pending) are a third, tiny thing: accent fill, white 10px text, 999px radius,
padding 0 6px — the nav badge. *new* `.mc-count`.

## 8. Status, health and risk vocabulary

These are the words and colours the app already uses. They're listed here so no new surface
invents a sixth.

**Run / job status** (`armada/status.py` is the source; `webui/schedfmt._STATUS_FILTERS` the labels):
Success (`ok`) · Running (accent-2) · Warning (`warn`) · Failed (`bad`) · Missed (✕ on grey) ·
plus the health strip's Scheduled (hollow accent-2) and Not scheduled (grey). Squares are drawn by
`agentbits._health_square` from `_HEALTH_STYLES`; the legend by `_health_legend_chips`. Anything
that shows a job's health reuses those two functions.

**Goal status** (`goalsview._GOAL_STATUS_COLOR`): Not started (`idle`) · On track (`ok`) · At risk
(`warn`) · Blocked (`bad`) · Done (accent-2).

**Capability risk.** One scale, red / amber / green, derived in `capabilities.py` from what a
capability can run and touch, floored so nothing reads safer than its worst ability. It currently
has **two sets of words**:

| Colour | User tab & legend (`_TIER_META`) | Bring-a-link review card (`catalogue._RISK_META`) |
|---|---|---|
| red | Caution | High risk |
| amber | Review | Medium risk |
| green | Trusted | Low risk |

→ **Open question for Mihai** (ticket in the audit): pick one set. The review card's words came
from Phase 1's rounds with you; the User tab's predate them. Until decided, don't add a third.

**Runs / Can touch** icons and colours (`capabilities._RUNS_ICON`, `_SCOPE_ICON`, `_ABILITY_CLR`)
are the only way a capability's reach is drawn; the review card and the User tab share them.

**Autonomy** (`agentbits._AUTONOMY_MODES`): one icon per mode, drawn only by `_autonomy_badge`.

## 9. Words

What the app mostly says today; the audit lists where it doesn't.

| Concept | Say | Don't say |
|---|---|---|
| the workspace folder of agents | realm (lower case in a sentence) | Realm, workspace |
| an agent's scheduled work | job | task (tasks are inbox items between agents) |
| agent-to-agent work | task, in the inbox | message, job |
| add a capability to the realm | Add to realm | Add, Install |
| give an agent a capability | Grant / Give access | Enable, Assign |
| turn a capability on for the realm | Switch on / Switch off | Enable/Disable, Activate |
| the coordinator | the realm's own label (`theme_coordinator`), e.g. "Prime Minister" | "coordinator" in UI copy |
| an agent | the realm's own label (`theme_agent`), e.g. "Minister" | "agent" in UI copy, where the label is available |

"Realm" is capitalised only at the start of a sentence or in a title.

### 9a. Dates and times

One formatter (to live in `webui/schedfmt.py`, mirrored once in JS), never numeric day/month:

| Context | Format | Example |
|---|---|---|
| A moment near now (next run, last run, updated) | weekday day month, 24h time | `Thu 24 Sep, 22:30` |
| A date in the current year | day month | `24 Sep` |
| A date in another year, or where the year matters (ETA, appointed, archive) | day month year | `1 Oct 2027` |
| Table column of timestamps (artefacts, memories) | day month, time; year only if not this year | `19 Sep, 14:40` |
| Relative, only for "just happened" | `2 min ago`, `yesterday` — then switch to the above | |

Times are 24-hour. The month is always a word — `9/24` and `24/9` read differently to different
owners, `24 Sep` doesn't.

## 10. Fields

| Element | Spec | Class |
|---|---|---|
| Text input, select | `_base._FIELD`: block, 100%, 6px 8px, divider border, `--r`, `--color-bg`, 13px | *new* `.mc-field` |
| Label | `_base._LBL` (§2) | *new* `.mc-label` |
| Textarea (long text: prompts, mandates) | `_base._TA`: sand fill, 10px padding, 12.5px, 1.55 | *new* `.mc-textarea` |
| Required marker | `_base._STAR`, `--status-bad` * | `.mc-star` (exists) |
| Toggle | `.mc-toggle` (30×17) | exists |

**Selects: native in forms, `mc-fdrop` in filter bars.** A form field that saves a value is a
native `<select class="mc-field">`; a control that filters a list is `agentbits._filter_dropdown`
(the pill-summary `details` menu). Never the other way round.

*Seen today:* `_FIELD` is used everywhere as a copied string (≈40 inputs and 21 selects), and one
Inbox select is drawn at 12.5px / 6px 9px by hand. The industry `.input` class (14px, 36px min
height) is unused and should stay unused — ARMADA's density is `_FIELD`'s.

## 11. Filter bar

A list page's filters sit in one row above the list: search field first (placeholder "Search
jobs…"), then `mc-fdrop` dropdowns in the order *who → what → state* (owner, type/cadence, status),
then the result count ("4 of 4") and any legend right-aligned. Each dropdown has a fixed width so
picking a shorter option doesn't shift the row. The Catalogue greys impossible options
(`.is-empty`) rather than hiding them.

## 12. Tabs

Three kinds, each with one job:

| Kind | Where | Class | Selected mark |
|---|---|---|---|
| Top navigation | title bar | `.mc-tab` | 3px **accent-2** underline |
| Page tabs (User / System / Add a capability) | under a page title | `.mc-captab` | 2px **accent** underline |
| Agent sub-tabs (Threads, Goals, Jobs…) | agent frame | `.mc-sub` | 2px **accent** underline |

*Seen today:* Settings' Realm / User / App tabs are hand-drawn buttons that look like `.mc-captab`
(heading 14px, 2px underline) — they should *be* `.mc-captab`.

## 13. Tables

Use `industry.css`'s `.table` — header 11px uppercase `.08em` dim, hairline rows, 4% hover —
instead of re-declaring it. Sortable headers carry the ↕ glyph and `cursor:pointer`; numeric
columns right-align; a row that opens something is clickable as a whole (`.mc-row`).

*Seen today:* `class="table"` appears three times across all rendered pages; the Jobs list, the Register and Artefacts style their
own `<th>`. Converge on `.table`.

## 14. Cards, widgets, dialogs

- **Frame / card:** `.mc-frame` — divider border, `--r`. Content padding per §3.
- **Widget:** `.mc-widget` + `widgets._wid_header` (grip, 15px title, uppercase meta, right slot,
  ⋮ menu). Every dashboard widget, including thread widgets, uses that header.
- **Dialog:** `.mc-modal-ov` (or `-top` for tall forms) + `.mc-modal-box`; header = `.mc-h-card`
  title + `.mc-x` or a sm "Close"; body; actions per §5's dialog rule. Confirmations go through
  `mcConfirm` / `mcAlert` — never `window.confirm` / `alert`.

## 15. Motion and feedback

Transitions 0.15–0.2s on colour/opacity only. Spinners: the dots spinner inside the thing that's
waiting (the list, the button), not beside it. Every async action reports in its own status span
next to the buttons, in `--text-muted`; errors in `--status-bad` and in words ("error: …").

---

## Where Phase 4 starts

1. **Add the classes** marked *new* to `brand.css`, matching the canonical specs exactly, with a
   golden run proving nothing changed (a class nobody uses yet changes no page).
2. **Migrate call sites** one component at a time — one ticket, one commit, golden diff reviewed —
   in the order: buttons (most instances), pills/chips, fields, tabs, tables.
3. **Delete the style-string constants** (`_FIELD`, `_LBL`, `_TA`) only when nothing references
   them.
