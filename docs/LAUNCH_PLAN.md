# ARMADA — Launch plan (north star)

**Status of this document:** the reference for everything from here to the beta launch and
beyond. Phases run in order. Mihai decides when a step is complete; nothing below is marked done
without his say-so. When a session starts, read this first.

**Conventions**

- `[ ]` not started · `[~]` in progress · `[x]` done (Mihai marks) · `[–]` dropped
- **MIHAI** — a step that only Mihai can do: a decision, an artefact, work outside Claude. The
  agent's job on these is to *ask*, not to guess, and to keep the phase moving around them.
- **DEFERRED** — deliberately after the beta launch. Listed so we don't re-decide it.
- **Model:** each phase names the model to run it on. Within a phase, steps that override the
  default say so in-line as `→ Opus` / `→ Sonnet` / `→ Haiku`.

**Which model, and why it varies.** Mihai's subscription has a monthly token limit, so the plan
tiers the work. The lesson from the sessions that built v0.99: the bugs a weaker model would
have shipped were not in the hard work but in the *routine* work — a match that ticked eleven
wrong results, a script calling a function a later string defined. Judgement during mechanical
tasks is where model quality shows. So the cheaper tiers are safe only under two conditions,
both of which hold here: the expensive model wrote the spec first, and a test catches the drift.

- **Opus 5.5** — the documents everything else is built against: ADRs, the architecture doc,
  the extension-point contract, the design-system doc, the audit, the threat model,
  Alexander's prompt, the Council design. A weak spec costs more tokens downstream than it
  saves here.
  *Replaced Fable 5.1 on 2026-09-24, Mihai's decision, from 2.6 onward.*
- **Sonnet 5** — bulk implementation under the suite. Strong enough to notice when a failing
  test means the test is wrong.
- **Haiku 4.5** — one ticket, one commit, suite green, screenshot. Anything with a golden page
  behind it and a spec above it.

Two practices make this cheaper than any single choice: switch models per **phase**, not per
message (every switch re-reads the plan and the files, and that context is the real cost), and
leave each hand-off as a ticket in this document with its acceptance test named, so the cheaper
model implements to a target rather than interpreting intent. And do 2.3 and 2.4 (the two
file splits) at the *start* of Phase 2: every later step that touches `serve.py` or
`capabilities.py` reads the whole file into context, whatever model is running.

**Decisions already made (2026-09-21)** — these are settled, don't reopen them:

1. Original decision: Claude only for v1. Superseded by Mihai on 2026-09-26: existing agents
   must be able to select models across connected Claude and Codex CLIs. See
   [Codex integration](dev/CODEX_INTEGRATION.md). September 28 extends setup and Alexander to
   either provider; see [Provider onboarding](dev/PROVIDER_ONBOARDING.md).
2. Alexander ships as a *guide* in v1. Alexander-the-developer is deferred and, when it comes,
   works through extension points rather than forking the app's code.
3. The Council ships in v1 as a differentiating feature, plan-only, through the existing
   proposal machinery. It gets its own design session (Phase 7).
4. The first launch is a **labelled beta** with an in-app feedback path, to a small invited
   group, before anything public.
5. The Catalogue is reframed from "browse" to "search known sources, or bring a link" — the
   value is provenance and review, not discovery.

---

## Phase 0 — Decisions and ADRs *(one week)* — **Opus 5.5** *(the ADRs themselves were written on Fable 5.1, before the switch)*

The four decisions above plus two open ones, written down as short ADRs in `docs/adr/` so no
later session re-litigates them. An ADR here is a page: context, decision, consequences.

- [x] 0.1 ADR-001 Single engine (Claude) for v1; what a second engine would need.
- [x] 0.2 ADR-002 Alexander: guide in v1, developer via extension points later.
- [x] 0.3 ADR-003 Council: plan-only, proposals as output, coordinator-curated participants.
- [x] 0.4 ADR-004 Catalogue reframed: search + bring-a-link + review; browsing dropped.
- [x] 0.5 ADR-005 Launch shape — accepted, fields filled by Mihai: ~5 beta users; feedback
      goes through Alexander (support icon beside the settings gear → "report an issue" →
      Alexander records the message with section context → dedicated email via Resend);
      updates automatic with an off switch in Settings → Advanced. See 5.6 and 5.7 for what
      that implies.
- [x] 0.6 ADR-006 Platform — **decided by Mihai 2026-09-21**: Windows-only for the beta,
      macOS in scope after (D.4). Written; consequences for new code recorded in the ADR.
- [x] 0.7 ADR-007 Licence — accepted; text confirmed: PolyForm Noncommercial 1.0.0. ⚠ The repo
      still carries MIT (never distributed — no remote); `LICENSE` + README change in 5.9,
      before the first beta build.
- [x] 0.8 **MIHAI**: the name — working on it outside Claude, time-boxed to 2026-09-22.
      `brand.py` is the only file that changes; needed before Phase 5 builds an installer
      that carries it. Becomes ADR-008 when decided. **Decided 2026-09-24: the name stays
      ARMADA** ([ADR-008](adr/ADR-008-name.md)); `brand.py` already carries it. ADR-008 also
      recommended keeping the internal `matcap` identifiers for the beta; Mihai decided instead to
      rename them too, before the public push ([ADR-010](adr/ADR-010-internal-rename.md), v0.99.56).

---

## Phase 1 — Catalogue reframe *(short; it's mostly removal)* — **Sonnet 5**

Removes the parts of the Catalogue that promise discovery the data can't deliver, and adds the
bring-a-link path that was always the point. Done first because it's small, it's fresh, and the
review step it produces is what the wizard (Phase 6) will use.

- [x] 1.1 Drop the "Suggested" ordering and the popularity claim it made. Done: `suggested()`
      and its `rank()`/`why_ranked()`/`multi_vendors()` helpers are gone; results sort
      alphabetically. The empty-search registry sample itself came back in v0.99.26 (see below) —
      Mihai's call after using it: a Source filter that greys itself out with nothing typed read
      as broken, not as "search instead". `_cat_results` still never runs on the page-render
      path — only once the Catalogue tab is opened (`/api/catalogue`) — so the "no network call
      on render" rule holds; what changed is that first fetch now samples the registry instead of
      leaving it empty.
- [x] 1.2 Rename the tab and the entry point: "Add a capability", two paths — *search known
      sources* and *bring a link*. Done: tab label and the custom-capability modal's note text.
- [x] 1.3 Bring-a-link: paste a URL (GitHub repo, package, MCP server) → an agent runs the
      capability-review protocol against it → a **review report** the user reads before Add is
      enabled. Reuses `inspect`, the capability-review system skill, `adopt`, and the
      skill-registry contract. The report is the feature; the Add button is the afterthought.
      Done: `catalogue.review_url()` runs a real engine turn (`allow_tools=True`) with the
      capability-review skill as system prompt, asks for one JSON object back, and
      `catalogue.add_link_to_realm()` writes it to the realm — ungranted, off, same promise as
      `add_to_realm`. New UI block above the search bar (`_cat_bring_link`); new endpoints
      `/api/catalogue-review` and `/api/catalogue-add-link`. Costs real tokens and real minutes
      per review (a genuine read, not a lookup) — the button copy and the in-flight message say
      so. Tests use a fake engine; Mihai ran it for real against the live Claude CLI on
      2026-09-21 (adadvisor.ai) — it worked end to end, and the feedback from that run is what
      v0.99.26/v0.99.27 above address.
- [x] 1.4 The review report format, written once and used everywhere a capability is shown:
      what it is, who published it, what it can reach, what was actually found, what the
      reviewer could not check. Same shape on the User tab's expanded panel. Done, but by reuse
      rather than a new shared component: the review's `runs`/`touch`/`summary`/`warn` fields are
      written straight onto the realm record's existing `runs`/`touch`/`observed`/`warn` fields,
      so the User tab's already-built declared-vs-observed panel (`_cap_prov`) renders it —
      that panel existed but nothing populated `observed`/`warn` before this. The bring-a-link
      pane's own card, for the moment right after reviewing and before Add, was JS-rendered
      (a hand-built string) until v0.99.26 moved it server-side (`_cat_review_card`) so it could
      reuse the same Runs/Can-touch icon component (`_cap_iconcluster`, the User tab's own
      inline title-row cluster — `_cap_middle`, an earlier separate-band version of the same
      thing, is gone as of v0.99.28, orphaned once the card stopped using it) the User tab uses
      instead of a second version of it living only in JS.
- [x] 1.5 Info box copy updated for the reframe: sources are now "where we can search" plus
      "bring your own, we'll review it". **MIHAI** reviews the copy. Done, draft copy shipped —
      heading now "Search known sources, or bring a link for anything else."; closing paragraph
      no longer claims the old "Suggested" ranking. Read through and approved by Mihai, 2026-09-21.
- [x] 1.6 Remove or retire code the reframe orphans (`suggested()`, `why_ranked`,
      `multi_vendors`, the empty-search sample path). Tests follow. Done: all three functions
      (plus their shared `rank()` helper) removed from `catalogue.py`; `_cat_results` sorts
      alphabetically instead. `tests/test_catalogue.py`'s "Suggested order" section replaced with
      a guard that the names are gone plus the standing popularity-claim check;
      `tests/test_catalogue_filters.py` updated wherever a test's assumption was "an empty
      search samples the registry" (several were, per the bug this reframe intentionally
      changes) — see `test_with_no_search_only_the_mirrored_sources_are_live` for the new
      baseline. New file `tests/test_catalogue_bring_link.py` covers 1.3/1.4. Full suite run
      clean under Python 3.12 (this sandbox only has 3.10, which can't even import `webui` —
      unrelated pre-existing f-string syntax in `agentcommon.py` needs 3.12; installed 3.12 via
      `uv` to get a real run). Result: zero regressions against a pre-change baseline; the one
      expected golden diff (`capabilities.html`) reviewed field-by-field and regolded. Shipped as
      v0.99.25.

**v0.99.26 — polish round, from Mihai's first real use of 1.1–1.3.** Four fixes, no scope change:
the Review button was silent for the couple of minutes a real turn takes (added a dots spinner
and a running clock, on the button and the status line); the report was one small dense
paragraph (now leads with a short "Armada's recommendation" — a new `recommendation` field the
agent writes alongside `summary` — with the full evidence collapsed behind "Full review", and
reuses the User tab's Runs/Can-touch icons via `_cap_middle` instead of a plain text line); the
MCP registry's Source filter greyed itself out with nothing typed, which read as broken (1.1's
note above); and filtering/searching the catalogue dimmed the results with no other sign the app
was working (added a spinner in the search box). Full suite clean against the same baseline, one
more expected golden diff reviewed and regolded. `docs/adr/ADR-004-catalogue-reframe.md` still
holds — this didn't reopen "browse the whole catalogue", it just stopped one specific filter from
being unusable.

**v0.99.27 — same feedback session, second pass.** Mihai tried Bring a link for real against
`adadvisor.ai` (screenshots attached) and had four more notes, all addressed: the button and the
status line were each saying "still working" twice over (dots+clock in both places) — trimmed to
one signal each, the button counts, the status line spins; the search spinner moved off the
search box into the results area itself, which now shows only the dots while loading instead of
a dimmed stale list; the expanded "Full review" report — one dense paragraph in the real agent's
output — now breaks into a paragraph per Step 5 section (`_paragraph_break_before_labels`, matched
generically against "LABEL — " runs rather than a fixed list, since the exact wording is the
agent's own choice); and the recommendation now leads with a High/Medium/Low risk bucket in
red/amber/green — a new `risk` field the agent sets from its own Step 5 conclusion, falling back
to the same mechanical runs/touch read every other unrated capability gets when it doesn't. A
review with a clear risk bucket now also sets the added capability's trust tier, so the card and
the User tab agree afterward. Full suite clean, one more golden diff (`capabilities.html`,
JS/markup only — `_cat_review_card` isn't part of the static page) reviewed and regolded. This
was also the first time Bring a link ran against the real Claude CLI rather than a fake engine in
tests — it worked end to end.

**v0.99.28 — third pass, from a real review of a plugin with shell reach.** Mihai's screenshot
showed "Medium risk" and "medium confidence" side by side on the same card — two pills that both
sound like a verdict, unclear which one was about the capability and which about the review
itself — for a plugin the report said could run shell commands, which the User tab would always
stripe red. Both issues came from the same gap: the agent's own `risk` field was trusted outright
whenever it was a valid word, never checked against what Runs/Can-touch actually declared. Fixed
with `_cat_final_risk()`: the agent's bucket floored to at least the mechanical worst-case
`_cap_tier_why` would give the same capability on the User tab, so a shell-reaching review can't
read softer here than anywhere else in the app — the agent's word can only raise the bucket, never
lower it. Applied both on the card and in `serve.py`'s `/api/catalogue-review` response, so the
floored value is what round-trips into the realm record when Add is pressed. The confidence pill
is gone outright rather than reconciled with the risk one. Also from that screenshot: the
Runs/Can-touch icons moved into the header row where the confidence pill sat, next to "by X"; a
new lead icon on the risk pill and "Armada's assessment" replacing "Armada's recommendation"; a
bolder, larger warning glyph on a flagged finding; a fix for the full-review paragraph-break rule
splitting a compound label the agent wrote as one phrase ("DECLARED vs OBSERVED — …") into two,
which read as broken markup; and the "Full review" toggle now uses the same animated caret a
capability card's own expand arrow uses (`.mc-cap-caret`, reused via a new lightweight
`.mc-cat-full` wrapper rather than the full `.mc-cap` card-chrome class) instead of a static
chevron. Full suite clean against the same 32-failure baseline; the only golden diffs were the
two new icon bodies appended to the shared `MC_ICONS` registry embedded on every page — reviewed
and regolded.

**v0.99.29 — one-line follow-up.** The assessment icon and the Flagged-section icon sat on the
same card, one row apart, at two different sizes (15px vs 18px). Matched to 18px both.

Mihai read through 1.5's copy and signed off on 2026-09-21 — Phase 1 is closed.

---

## Phase 2 — Architecture review and refactoring *(≈ one focused week)* — **Sonnet 5**, design steps → Opus

On the current code, *before* new features. The September review's eleven done items stay done;
this phase takes the three that remain, the two oversized files, and produces the extension
points Alexander-the-developer will need later. Every step is a pure move or a mechanical
change guarded by the golden suite — no behaviour changes ride along.

- [x] 2.1 Extract the 27 remaining inline `<script>` blocks from Python strings into
      `webui/static/js/`. Root cause of a real bug this week (a script calling a function a
      *later* string defined). Order becomes explicit; JS becomes lintable. Done (v0.99.36):
      28 scripts (one file had two) externalized across 13 source files, following the
      `assets.py` `js()`-helper pattern already used for ~35 other scripts. Most were extracted
      byte-exact from the live module's runtime string via a regex script, eliminating
      transcription risk; a handful had realm-specific Python data baked into otherwise-static
      logic and were redesigned into a parameterized static function plus a tiny per-render
      `<script>call(args)</script>` shim (job-open scroll, mem-focus highlight, the token-
      consumption widget), or, for the Covenant modal, switched from a server-baked JSON
      literal to reading its own already-rendered text off the DOM once on load. All 28 files
      `node --check` clean. 22 tests across 9 files asserted on inline script content directly
      (source text, or ordering between two inline blocks) and were updated to read the
      extracted `.js` file instead, or to check the `<script src>` tag order; behaviour
      unchanged. Full suite clean against the standing 31-failure baseline, 17 golden pages
      regenerated and each diff reviewed to confirm only the script tag changed (two more,
      `jobs` and `agent_threads`, were already drifting on master for an unrelated reason
      before this change and were left as-is). One unrelated finding along the way:
      `serve.py`'s `APP_HTML` constant appears to be dead code — grep finds no reference to it
      anywhere else in the codebase — left untouched as out of scope for this step.
- [x] 2.2 Promote the 211 inline `color-mix(...)` expressions and the recurring inline style
      strings to CSS classes / custom properties. This is what makes "buttons look different
      page to page" fixable once, and it is Phase 4's foundation. Done as v0.99.37: two pieces.
      First, 190 of the 211 `color-mix(in srgb,var(--color-X) NN%,transparent)` calls (90%)
      recurred two or more times and are now a custom property — the existing
      `--text-strong/dim/muted/soft/faint/ghost` alpha scale already in `brand.css` extended with
      the rest of the percentages that recurred (`--text-6` through `--text-65`), plus the same
      idea for `--accent-13`/`--accent-38`/`--accent2-7`/`--status-ok-16`/`--status-warn-16`. The
      remaining 21 are one-off percentages or mix against something other than `transparent`
      (`var(--color-bg)`, a dynamic Python-side value) and stayed inline — legitimately out of
      the ≥2-occurrence scope, not silently dropped. Caught one real instance of the bug class
      along the way: `static/js/settings.js` carried its own hardcoded copy of a color-mix string
      that has to byte-match the Python-rendered one for the realm-icon-picker's "current" ring to
      line up, and it had drifted from the token rename until fixed — confirms the plan's premise.
      The ~30 other `color-mix(` calls living in `.js` files are a separate, larger cleanup (the
      "211" was counted from `.py` files only) and are explicitly out of scope here. Second piece:
      the modal overlay/box chrome (`display:none;position:fixed;inset:0;…` plus a
      background/radius/padding/shadow box) was duplicated near-verbatim across ~20 modals in 9
      files; it's now two classes, `.mc-modal-ov` (`.mc-modal-ov-top` for the few anchored to the
      top instead of centered) and `.mc-modal-box`, with only the genuinely per-modal bits —
      z-index, background alpha, box width, padding when it wasn't the default 18px — left as
      inline overrides. Three modals (the Covenant modal, the dashboard widget picker, the
      appoint-agent overlay) use a different alpha, a border, or a different box structure
      entirely and were deliberately left inline rather than force-fit into a class that doesn't
      actually match them. The 57+ other style patterns recurring ≥4 times found in recon (e.g.
      `font-size:12px;color:var(--text-muted)` ×27, `display:none` ×17) were judged too
      low-semantic-value for the effort and were not promoted — a follow-up opportunity, not
      forgotten. Pure moves, no behaviour change, guarded by the golden suite (18 pages
      regenerated, each diff verified byte-for-byte against a normalized reconstruction of the old
      content — including one page, `settings.html`, whose "current version" changelog tag had
      gone stale because 2.1's own regold ran before that release's version bump; now incidentally
      corrected). `jobs` and `agent_threads` remain excluded for the same pre-existing, unrelated
      drift noted in 2.1. Full suite clean against the standing 31-failure baseline.
- [x] 2.3 *(do first — cuts every later step's context)* Split `serve.py` (3,001 lines) along its route table: handlers grouped by area
      (realm, agents, jobs, capabilities, catalogue, settings) into `armada/routes/`. The
      table stays; the methods move. Done: `serve.py` is 574 lines now (3,033 before this pass
      — it had grown past the plan's 3,001 during Phase 1). The 158 handler methods it held
      split into 8 files under `armada/routes/` as mixins the `Handler` class multiply-inherits
      — `realm.py`, `agents.py`, `jobs.py`, `caps.py` (named to avoid colliding with
      `webui/capabilities.py`), `catalogue.py`, `settings.py`, plus `dashboard.py` for the
      sections/widgets/usage/memory/goals/inbox handlers that don't fit the plan's six named
      areas on their own, and `_shared.py` for cross-cutting helpers used by more than one area
      (the realm registry, a realm/job's JSON projection, thread-title heuristics, `_slug`,
      `_write_data_image`, `_refresh_system`). `serve.py` itself keeps only the route tables and
      core dispatch (`do_GET`/`do_POST`/`_route_get`/`_route_post`, `_send`/`_json`/`_query`/
      `_body`/`_same_origin`, `_static`, the git/restart plumbing) plus the `Handler` class
      declaration, now `class Handler(RealmRoutes, AgentRoutes, JobRoutes, CapabilityRoutes,
      CatalogueRoutes, SettingsRoutes, DashboardRoutes, SharedRoutes,
      http.server.BaseHTTPRequestHandler)`. Mechanically extracted (a script sliced serve.py by
      method boundary rather than 158 hand-done edits — far less error-prone for a move this
      size), which surfaced two real correctness traps a manual pass could easily have missed:
      every single-dot relative import (`from . import X`) inside a moved method had to become
      `from ..` once the method's home package changed from `matcap` to `armada.routes`; and two
      places read the class itself by name (`Handler.realm = newp` in the realm-switch handler,
      `Handler._streams[...]` in the chat-stream handlers) — a bare `Handler` reference that
      would have been a `NameError` once the method moved to a module that never imports
      `Handler` (importing it would be circular: `serve.py` imports the routes modules for the
      mixins). Fixed as `type(self).realm = newp` (same effect: sets the class attribute, not an
      instance one that a fresh per-request Handler would never see again) and `self._streams`
      (item-assignment/method calls on a mutable class-level dict — identical either way, self
      resolves the same object via the class). Five tests read `armada/serve.py`'s source text
      directly to assert a code pattern exists (`_derive_title`, `_telegram_status`,
      `_save_appearance`, `_save_realm_settings`'s `_refresh_system` call, every `dark=self._dark()`
      call site) — updated to look in the files those patterns actually live in now; one test
      monkeypatched `serve._reg_path` — updated to patch `armada.routes._shared._reg_path`,
      which is the name the moved code actually resolves at call time (a function's globals are
      fixed at its own definition site, not the call site). Full suite clean against the same
      32-failure baseline; zero golden-page diffs (nothing rendered differently — the route
      tables, and therefore every URL, are untouched). Also smoke-tested live: booted the real
      HTTP server against a scratch realm, hit every top-level page and several API routes, and
      exercised a realm-settings save end to end (renames realm.json, updates the switcher
      registry, and rebuilds system memory) — not just under the fake-engine unit tests.

**v0.99.31 — bugfix found while reading catalogue.py for 2.4, fixed first.** Mihai reported adding a capability by link that was already in the realm (sourced from Anthropic's skills listing) and getting a second entry rather than a refusal. Root cause: `add_link_to_realm`'s same-realm duplicate check compared `capabilities.cap_key(c)` (plain-lowercase, punctuation intact) against an id already run through `_norm_id` (alnum only) — so a realm record filed as `frontend-design` (a catalogue entry's slug) never matched a fresh review calling the same source `Frontend design` (its display name), and the dedupe silently missed. Fixed by switching both the same-realm check and a new cross-realm one to the name-token matcher (`_tokens`/`_same_capability_exact`) the catalogue's own “already added” hint (`installed_keys`) already used elsewhere — now scanned across every kind bucket in a realm's toolkit, not just the bucket the new entry's own kind guess would land in. Also shipped the feature Mihai asked for alongside the fix: a new `catalogue.realms_with_capability(name, url)` checks every realm ARMADA knows about (the same registry `_known_realms` already reads), and the bring-a-link report card now shows “Already added to this realm” with Add disabled, or “Added to Cabinet2, Skunkworks” with Add left active, before the owner can create the duplicate rather than after. Full suite clean against the same 32-failure baseline; no golden-page diffs (the changed card isn't one of the golden pages). Directly informs 2.4 below — the add/dedupe logic just worked on is exactly what that split has to carry forward intact.
- [x] 2.4 *(do first, with 2.3)* Split `catalogue.py` (1,398): the realm-writing side (`add_to_realm`, `adopt`,
      provenance) out of the fetch/search side. And `capabilities.py` (1,835): rendering from
      data. **Render half, v0.99.32.** `webui/capabilities.py` had grown to
      2,078 lines carrying the User tab, System tab, and the Catalogue tab's own rendering
      (search results, the bring-a-link review report, the info box) in one file. The Catalogue
      tab's 20 functions/constants (`_cat_results`, `_cat_card`, `_catalogue_pane`,
      `_cat_review_card` and the rest) moved to a new `webui/catalogue.py` (842 lines).
      `webui/capabilities.py` (1,263 lines) keeps the User tab, the System tab, and the
      cross-cutting trust-model helpers both tabs' cards are built from (risk tier, Runs/Can-touch
      icons, kind labels); the new file imports the three of those it needs
      (`_KIND_SINGULAR`, `_cap_iconcluster`, `_cap_tier_why`). `_realm_skills`, the page that
      stitches all three tabs into one screen, stayed in `capabilities.py` and reaches into
      `catalogue.py` locally for the two pieces it needs (`_catalogue_pane`, its filter JS) — a
      local import, not a module-level one, since a module-level import each way would be a
      cycle. Two external call sites updated (`routes/catalogue.py`, `webui/pages.py`), plus four
      test files whose `CAP.` calls named now-moved functions. Full suite clean, zero golden-page
      diffs (the Capabilities golden page exercises both tabs), live-smoke-tested end to end.
      **Data half, v0.99.33 — folded into 2.9 below, done together.** `armada/catalogue.py`
      (1,578 lines) is now a package, `armada/catalogue/` — `_shared.py` (277 lines: constants and
      the name/id matching `_tokens`/`_same_capability_exact`/`_known_realms` that both sides call),
      `sources.py` (600 lines: the mirrored/queried sources — marketplaces, the MCP registry,
      Anthropic's skills), `realm.py` (727 lines: adding a capability to a realm, adopting what
      discovery found, fetching a skill, the bring-a-link review flow). `__init__.py` re-exports
      every public and private top-level name the single file used to expose (~90 names), so every
      external caller (webui, routes, sysjobs, capscan) is unchanged. The hazard flagged when this
      was deferred was real: 13 private names monkeypatched offline in 9 test files across roughly
      60 call sites, several specifically to keep tests off the network. Once a monkeypatched
      function's callers live in a different module than the function itself, `setattr` on the
      package's re-exported name no longer reaches the caller's own module globals — this hit not
      just the 9 test files' own local fixtures but the suite's *global* autouse fixture in
      `conftest.py`, which is where most of the resulting failures traced back to. Every call site
      repointed at whichever module (`_shared`, `sources`, or `realm`) actually resolves the name
      bare; `conftest.py`'s docstring and `catalogue/__init__.py`'s module docstring both explain
      the trap for the next split. Full suite clean against the same 32-failure baseline.
- [x] 2.5 The 270 silent `except Exception` blocks: log the exception in each before returning
      the fallback. One `log.exception(...)` per block; the fallback behaviour stays. Done as
      v0.99.39: an AST scan found 282 broad handlers; 267 neither logged nor re-raised (176 fully
      silent, 91 that turned the error into a UI message but dropped the traceback). Every one now
      logs first and then does exactly what it did before. One deliberate deviation from "one
      `log.exception` each", because it would have been wrong on the render and poll paths: the
      default call is a new `util.swallowed(log, "<func>: <fallback>")`, which logs at ERROR with
      the traceback but (a) treats `FileNotFoundError` as the ordinary absent case, at DEBUG, and
      (b) holds back repeats of the same (logger, message, exception type) for 5 minutes and
      summarises the count on the next one through — a corrupt file behind the notification bell's
      poll would otherwise have written a traceback every few seconds and rotated the 4 MB log
      away. 195 sites use it. 71 sites where the failure *is* the expected path — probes
      (`_direct_launcher`, tz/zoneinfo, `ctypes`, pywebview API drift), writes to an SSE client that
      has disconnected, per-line/per-date parses in loops, `_wait_until_up` while the server boots,
      git fetch with no remote, request-body/origin parsing of client input — log at DEBUG with
      `exc_info`. One is marked `# silent-ok:` (`app._fatal`, where logging is what failed). The
      logger per module is `logging.getLogger(__name__)` where one didn't exist (existing
      `armada.serve`/`armada.runner`/`armada.notify` loggers kept); in `webui/pages.py` it's defined
      after the `globals().update(vars(_core))` mirror so pages keeps its own name. Necessary
      companion, or half of this would have gone nowhere: the scheduler is a separate, windowless
      `pythonw` process (SCHEDULER.vbs) that never configured logging, so everything the runner,
      sysjobs and Telegram listener logged was dropped. `serve._init_logging` moved to
      `util.init_logging(filename)`; the server keeps `armada.log`, `matcap schedule` now writes
      `scheduler.log` (a separate file because two processes rotating one file fails on Windows),
      and the stream handler is skipped when there is no stderr. Guard: `test_exception_logging.py`
      scans every broad except in `armada/` and fails on one that neither logs, re-raises, nor says
      `silent-ok:` — so the count can't creep back up — plus 8 tests on `swallowed`/`init_logging`.
      Found immediately: the `test_notif_feed` baseline failures are a sandbox artefact
      (`NotImplementedError: cannot instantiate 'WindowsPath'` on Linux, visible now that
      `notify.record` logs), not an app bug. Golden: `settings` (changelog) only — no render change.
      Full suite at the standing 31-failure baseline.
- [x] 2.6 → Opus · Engine seam audit (ADR-001's homework): list every place that assumes Claude rather
      than "an engine" — tool use, MCP, skills, usage limits, model catalogue, the capability
      model. Don't fix; document. This is the bill for OpenAI, priced. Done 2026-09-24 (Opus 5.5):
      [`docs/dev/ENGINE_SEAM_AUDIT.md`](dev/ENGINE_SEAM_AUDIT.md), linked from ADR-001. Eleven areas
      (A–K), each with `file.py:function` references, what a second engine would need, and a
      size; roughly **5–7 weeks** for an MCP-capable second engine, half of it the capability
      model (H). Headline findings: engine choice is never actually made — every call site
      hard-codes `"claude"` and the realm's `provider`/`providers`/`default_engine` settings are
      display-only (A); five modules call the Claude CLI outside the seam (B: thread titling,
      sign-in, capability scan, usage keepalive, token-expiry read); and the tool-event payloads
      are Claude Code's own tool names, which `runner.py` uses to find artefacts and enforce the
      publish boundary — the finding most likely to fail *silently* on another engine (D). Ends
      with an order of work for D.2 and three rules for new code now. Nothing fixed, per the
      ADR. One unrelated aside noted in C: the effort dropdown offers four levels, the runner
      accepts five (`xhigh`).
- [x] 2.7 → Opus · **Extension points, designed and stubbed** (ADR-002's homework): a plugin surface
      with a defined contract for the things Alexander-the-developer will be allowed to
      write — widgets (the registry exists), filters (already data), themes (already data),
      job templates, dashboard layouts. Each gets: a schema, a loader, a place on disk under
      the realm or the app-data folder, and a test that a malformed plugin fails safe. Nothing
      uses them yet. Done as v0.99.40 (Opus 5.5): contract
      [`docs/dev/EXTENSION_POINTS.md`](dev/EXTENSION_POINTS.md) (v1), loader `armada/addons.py`, 52 tests
      in `tests/test_addons.py`. **Named "add-ons", not plugins** — "plugins" and "extensions"
      are both already capability kinds on the Capabilities page. An add-on is a folder with one
      `addon.json`, **data only**: widgets (`markdown` or `links` — no HTML/JS, no data queries in
      v1), filters (jobs: status/cadence/agent/text; capabilities: kind/text), themes (the
      `vtheme.THEMES` shape; app-scope only), job templates (**agent jobs only — command jobs are
      refused**, since a shipped shell command is code by the back door), layouts (the
      `dashboard.json` shape; thread widgets refused as realm-specific). Disk:
      `<realm>/addons/<id>/` travels with the realm, `~/.armada/addons/<id>/` is per install; the
      folder name must equal the id so "undo is delete the folder" holds; realm shadows app;
      contributions are addressed `<addon>/<id>`. Fail-safe: `load()` never raises; a malformed
      add-on (bad JSON, newer contract, bad/mismatched id, >256 KB, symlinked) is skipped whole, a
      malformed contribution alone, a loader bug costs one add-on; every skip is a readable
      reason in `Registry.problems` and the log. Drift guards: the filter vocabularies are
      asserted equal to `webui/schedfmt.py`'s and `capabilities.KINDS`, the layout clamps to what
      `_save_dashboard` actually saves, and the doc's worked example is loaded by the suite. ADR-002's
      test ("a built-in uses the surface before Alexander does") is **not met yet** — by design of
      this step; the doc names themes as the cheapest first consumer. `docs/dev/SCHEMA.md` and ADR-002
      point here. Golden: `settings` (changelog) only.
- [x] 2.8 Realm format versioning: `realm.json` gains `schema_version`; a `migrate()` step
      runs on load and on import; the first migration is a no-op that stamps the version.
      Every field we added this month is the reason this is here. Done as v0.99.38: new
      `armada/realmformat.py` owns an integer `CURRENT = 1` and a `MIGRATIONS` registry
      (`MIGRATIONS[n]` takes v`n` → v`n+1`); `migrate()` walks a realm up under the realm.json
      `file_lock`, writes atomically, never raises (logs and opens as-is), and never touches a
      realm stamped *newer* than `CURRENT` (reported instead: adopt shows an `mcAlert`,
      `matcap validate` warns). "Load" is wired at the three places a realm is opened — server
      start, `/switch`, and each non-dry-run scheduler `tick()` (which is what reaches realms
      nobody has looked at since an upgrade) — through `ensure()`, memoised on realm.json's mtime
      so the hot path is one `stat()`; deliberately *not* in `reader.read()`, which is a render
      path and is called while route handlers already hold the realm.json lock (the lock isn't
      re-entrant: that would have been a 5-second stall per render). "Import" is the adopt mode of
      `/api/new-realm`. `matcap new` scaffolds at `CURRENT`. Found along the way: `setup.py`
      already wrote `"schema_version": "0.1"` — a string nothing ever read — so that and "no key"
      both count as v0. The rules for the next real migration (bump, register, table row in
      `docs/dev/SCHEMA.md`, test; steps idempotent) are written in `docs/dev/SCHEMA.md`. 29 new tests
      (`test_realm_format.py`), including a monkeypatched v0→v1→v2 chain to prove ordering for the
      first migration that actually does something. Golden: `new_realm` (the adopt warning) and
      `settings` (changelog) only. Full suite at the standing 31-failure baseline.
- [x] 2.9 Concurrency pass on the scheduler ↔ server boundary: the file locks exist; confirm
      every realm write goes through one, and that two schedulers (a real case I hit) can't
      double-fire a job. A lock file or a pid file for the scheduler. **Done, v0.99.33 — folded
      together with 2.4's data half above, since both touch this file's locking.** Audited every
      `realm.json` write site: `capscan.scan()` and `catalogue.realm`'s three writers already
      wrapped their read-modify-write in `util.file_lock`; eleven route handlers didn't —
      `routes/caps.py`'s five capability-editing handlers (save, toggle, delete, permission,
      refresh connectors) and `routes/dashboard.py`'s six section-editor handlers (add ×2, rename,
      delete, reorder, update) — nor did `workspace.py`'s `migrate()` and `set_root()`. All
      eleven-plus-two now wrap their read-modify-write in the same `util.file_lock`. Separately,
      the double-fire case: two schedulers ticking the same realm — a daemon left running in a
      forgotten terminal plus a second one started later, or a persistent daemon plus a one-shot
      `--once` run landing in the same minute — since `ran_today()`'s run-report check only closes
      that race *after* a job finishes, not while it's in flight (a job that takes any real time
      to run reads as "not yet run today" to a second ticker the whole time it's running). Each
      realm now gets a `scheduler.lock.json` naming the pid currently ticking it: `run_daemon()`
      claims it for every realm it's about to tick and holds it for its whole lifetime — refusing
      to start at all if the *primary* realm is already owned by another live process, dropping
      only an `--also` realm someone else owns rather than refusing outright — and a standalone
      `tick()` call (the CLI's `--once`/`--at`, or the web UI's dry-run preview route) claims the
      lock for just that one pass and backs off (returns a `"skipped"` record, fires nothing)
      if a live process already holds it. A recorded pid that's no longer running (new
      `util.pid_alive`, cross-platform: `os.kill(pid, 0)` on POSIX, `OpenProcess` on Windows) reads
      as a stale lock from a crash, not a live holder, and gets taken over rather than stuck.
      25 new tests (`test_scheduler_lock.py`, `test_realm_write_locking.py`) exercise the lock
      acquire/release/stale-takeover behaviour and confirm each fixed write path actually opens a
      critical section, rather than re-deriving the race by hand. Full suite clean against the
      same 32-failure baseline.
- [x] 2.10 → Opus · A short written architecture doc that comes *out* of this phase: the module map, the
      seams, the invariants ("the realm folder is the truth", "no write without a lock",
      "no network on a render path"). Feeds Phase 3. Done 2026-09-24 (Opus 5.5): [`docs/dev/ARCHITECTURE.md`](dev/ARCHITECTURE.md) — the two processes and what runs in
      each, a layered module map (entry → http → render → execution → domain → infra, with the
      `webui/` L0/L1/L2 carve-up and its namespace mirror), eight seams, nine invariants, three
      end-to-end flows (page view, chat turn, scheduled job), testing, and where new code goes.
      Each invariant carries its rule, what enforces it, and **where it doesn't hold yet** —
      checked against the code rather than asserted: (4.2) 2.9's lock audit covered `realm.json`
      only — `routes/agents._save_agent` writes `agent.json` unlocked while `capabilities.py`
      writes grants to the same file under a lock, thread `meta.json` is written during a render,
      and `_load_dashboard` migrates `dashboard.json` on load; (4.3) `models.options()` can start a
      background model-catalogue refresh from a render (non-blocking, once per TTL) — otherwise
      nothing under `webui/` imports `urllib`/`subprocess`; (4.6) two JavaScript leftovers 2.1's
      sweep missed because neither is a `<script>` literal: `_core._WIZ_JS` (the 61-line new-realm
      wizard, a raw-string constant) and `serve.APP_HTML` (dead code). Those five are tickets for
      4.3's backlog. Also recorded: the 31-failure sandbox baseline is OS-specific (`WindowsPath`,
      backslash paths), made visible by 2.5.

---

### Follow-up review — 2026-09-26 (required before beta)

Mihai requested a fresh review against the highest engineering standards, including the current
Codex work. Evidence, source locations, reproduced failure cases and rationale are in
[`ARCHITECTURE_REVIEW_2026-09-26.md`](dev/ARCHITECTURE_REVIEW_2026-09-26.md).
The earlier completed steps above remain historical; they do not close these newly demonstrated
gaps. Retain the local architecture and realm format. Refactor the ownership/transaction boundaries
incrementally, with focused regression tests. No implementation below is marked complete by this review.

**Order:** start 2.21's deterministic baseline immediately; fix 2.11–2.12 first, then 2.13 before
2.14–2.16. Do 2.17–2.19 with the minimum common contracts from 2.20. Finish the complete 2.21 gate
before 8.1. P1 = security/data integrity/execution integrity; P2 = functional/engineering gap.
All 2.11–2.21 are beta prerequisites; the complete UI namespace cleanup is explicitly deferred to D.8.

#### Execution order and feature sequencing — 2026-09-27

**Recommendation: address the safety and reliability work now, before expanding the wizard or
other features that create realms, grant capabilities or run agents.** Those features depend on
the boundaries being repaired; building on the current behavior increases both exposure and rework.
Wizard copy, template review and interaction design can continue alongside these fixes.

| Order | Ticket | Status | Work | Why here |
|---|---|---|---|---|
| 1 | 2.21 — baseline portion | Verified 2026-09-27: two full runs, 1,999 passed / 1 skipped each | Fix the three existing test failures; establish deterministic fixtures and regression checks | Gives the following fixes a trustworthy baseline; do not delay urgent safety fixes for completion of all CI tooling |
| 2 | 2.11 | Verified 2026-09-27: 2,022 passed / 2 skipped; browser SVG isolation check passed | Confine static files and isolate active content | Close file-serving and app-origin security gaps |
| 3 | 2.12 | Verified 2026-09-27: 2,153 passed / 2 skipped; installed CLI denial check passed | Fail closed on invalid capability policy | Permissions must remain enforced before adding onboarding/grant flows |
| 4 | 2.13 | Verified 2026-09-27: 2,178 passed / 2 skipped; independent-process lock checks passed | Make shared file mutations exclusive | Foundation for scheduler, memory and conversation consistency |
| 5 | 2.14 | Verified 2026-09-27: 2,204 passed / 2 skipped; synchronized startup and crash-recovery checks passed | Atomically claim scheduler ownership and job attempts | Prevent duplicate execution using the corrected ownership primitives |
| 6 | 2.15 | Verified 2026-09-27: 2,262 passed / 2 skipped; concurrent memory preservation checks passed | Replace destructive memory rollback | Protect legitimate owner and agent updates during concurrent work |
| 7 | 2.16 | Verified 2026-09-27: 2,298 passed / 2 skipped; concurrent compaction and process-crash recovery checks passed | Make compaction preserve concurrent history | Build recoverable conversation updates on the corrected persistence layer |
| 8 | 2.17 | Verified 2026-09-27: 2,309 passed / 2 skipped; overlapping realm switches, stale saves and run-ID reuse checks passed | Bind requests and runs to immutable realm identity | Keep every side effect attached to the correct realm through navigation |
| 9 | 2.18 | Verified 2026-09-27: 2,381 passed / 2 skipped; 70 lifecycle regressions including real process-tree cleanup | Supervise CLI processes and enforce terminal outcomes | Make timeout, cancellation and success/failure reporting reliable |
| 10 | 2.19 | Verified 2026-09-27: 2,425 passed / 2 skipped; 41 provider-upkeep regressions and a lock-initialization regression | Remove Claude-only gates from provider-neutral work | Make the repaired execution paths work correctly across connected providers |
| 11 | 2.20 — complete integration | Verified 2026-09-27: 2,494 passed / 2 skipped; 68 shared execution contract cases | Finish shared execution contracts and lifecycle ownership | Consolidate contracts introduced during steps 3 and 8–10 before further agent-execution features |
| 12 | 6.4 setup CX follow-up → 6.5 | Nine-step wizard review build ready: dedicated Naming step, editable Team and folder while setup is unfinished, custom-agent deletion, refreshed historical portraits/names, expanded Company/Ship profiles, progressive formatted first task, and Telegram as a Done action | User walkthrough, automatic connector setup and real first-artifact acceptance remain open | Latest full suite: 2,569 passed, 2 skipped. A completed test realm had kept a stale wizard route; completed setups now return to the app, and saved setup shows other registered realms on Folder. Package: `build/setup-cx-4gh7oua4/bundle/ARMADA-CX-Setup.exe`; a fresh isolated native review window is open, with earlier test realms preserved in their prior profile. Connector follow-up: `docs/dev/STARTER_CAPABILITIES.md` |
| 13 | 2.21 — final gate; 5.10; 8.1 | Queued | Run complete CI, clean-machine tests and the release rehearsal | Verify the integrated feature set before beta |
| After beta | D.8 | Deferred | Complete UI namespace/import cleanup | Structural cleanup can proceed incrementally without delaying the concrete safety fixes |

2.20 is incremental: introduce each small contract when its consumer needs it, rather than
building a new framework up front or waiting until step 11. 2.21 also spans the work: add each
regression as its defect is fixed, and re-run the release gate after remaining features land.
Existing behavior is preserved except where the ticket explicitly corrects it.

**Wizard status clarification:** 6.4 already records an implemented nine-step wizard and its
routes/scripts exist. The recorded open milestone is 6.5 (prove time-to-first-value with a real
artifact). The September 28 provider follow-up uses the contracts above for either-provider
onboarding and Alexander. Installed-app acceptance and the real artifact milestone remain open.

- [~] **2.11 · P1 · Confine files and isolate all active content (R1; extends 5.8a).** Replace
      `_static` string filtering with resolved containment; reject Windows drive/UNC/absolute
      escapes. Route or sanitize user-controlled SVG icons/avatars under the same trust policy
      as HTML attachments. **Accept:** an HTTP request for a scratch file outside the static
      directory fails; bundled assets still work; adversarial Windows paths are covered; a browser
      SVG-document test cannot access a harmless test-only API endpoint. Update the threat model.
      **Implementation verified 2026-09-27:** resolved containment and Windows path rejection
      protect bundled assets; all three user-image routes apply a script-free sandbox CSP and
      `nosniff`. HTTP regressions cover traversal, drive/UNC paths, assets and SVG responses.
      In-browser SVG documents remained visible and made zero calls to a test endpoint; the
      ordinary control page made one. Full suite: **2,022 passed, 2 skipped** (93.94s); this
      Windows host does not permit creating the symlink needed by one regression. Source verified;
      packaging, clean-machine validation and launch signoff remain separate gates.
- [~] **2.12 · P1 · Fail closed on invalid capability policy (R2).** Remove the fallback that
      drops per-agent restrictions when grant resolution fails. Validate policy and compare grants
      against each provider's effective inventory, including newly discovered servers. **Accept:**
      unreadable/malformed policy cannot launch a tool turn; empty, revoked and unknown grants
      cannot expose connectors under either adapter; the error reaches the user and run record.
      **Implementation verified 2026-09-27:** strict policy parsing and immutable grant snapshots;
      grants refreshed at launch; both adapters gate effective CLI MCP inventories and reject
      inventory errors. Failed admission is durable for chat, streaming chat, jobs and inbox tasks.
      The installed Claude CLI honored empty-grant settings: **3 configured servers → 0 available**,
      without a model call. Full suite: **2,153 passed, 2 skipped** (94.78s); the final compatibility
      facade and generated references also passed **251 focused checks**. Provider requirements
      and the invocation-level enforcement boundary are documented in `dev/CODEX_INTEGRATION.md`.
- [~] **2.13 · P1 · Make file mutations genuinely exclusive (R3).** A lock timeout or filesystem
      error must return busy/failure, never enter the critical section. Add safe owner-death recovery
      and a shared read/validate/mutate/atomic-write helper. Audit shared writers, including
      `system_jobs.json`, agent settings, grants and thread metadata. **Accept:** independent-process
      increments preserve every update; contention, crash and access-error cases never perform an
      unlocked write; malformed/future-schema state is preserved and surfaced rather than rewritten
      as defaults. Establish the read-only/recovery policy for unsupported schemas.
      **Implementation verified 2026-09-27:** bounded OS locks never yield on contention/error;
      ownership ends on process death without unlinking the stable lock file. Added strict
      `read_json_state` / `mutate_json`, repaired system-job result/switch merges and audited
      agent/grant, thread metadata, job route and migration writers. Unsupported realm schemas
      refuse edits and execution while inspection remains available. Four independent processes
      preserved **120/120 updates**; crash, timeout, access-error, corrupt-state and HTTP schema
      checks pass. Full suite: **2,178 passed, 2 skipped** (100.75s); final agent/read-reference
      checks: **120 passed**. See `dev/PERSISTENCE.md` for recovery. Deployment requires restarting
      the UI and scheduler together; the live installation has not been restarted during this work.
- [~] **2.14 · P1 · Atomically claim scheduler ownership and job attempts (R4; follows 2.13).**
      Replace read-then-replace ownership with an exclusive lease/OS lock and unique owner token.
      Prevent overlapping callers in one process as well as separate processes. **Accept:** two
      synchronized starters produce one owner and one job attempt; stale recovery cannot remove a
      live owner's lease; write failure blocks dispatch. Document retry/idempotency behavior after
      a crash without claiming exactly-once external side effects.
      **Implementation verified 2026-09-27:** OS-held realm leases with unique owner tokens;
      explicit daemon handles and a non-reentrant pass gate; durable daily agent/command claims
      before dispatch. System jobs also claim before execution under per-job locks shared by
      scheduler, app-startup and manual entry points, with cadence rechecked under ownership.
      Two synchronized processes produce **one owner / one dispatch**; same-process overlap,
      stale tokens, killed owners before/after an effect, claim/result write failures and explicit
      recovery pass. Interrupted attempts are held instead of automatically replayed; manual
      retries and external idempotency limits are documented in `dev/PERSISTENCE.md` and Jobs help.
      Added **26 regression cases**. Full suite: **2,204 passed, 2 skipped** (106.18s); the Docs
      golden change contains only the new recovery guidance. Source verified; the live UI and
      scheduler have not been restarted.
- [~] **2.15 · P1 · Replace destructive memory rollback (R5).** Remove whole-folder snapshot
      restoration that cannot attribute writes. Use execution-time restrictions or owned/staged
      memory writes; explicitly describe any provider limitation. **Accept:** agent A finishing,
      failing or being cancelled cannot undo B's memory updates, an owner's edit or system-memory
      refresh; unauthorized writes are blocked where supported or reported without erasing other
      writers' data. Update the threat model's enforcement claim.
      **Implementation verified 2026-09-27:** removed the snapshot/restore helpers. Claude receives
      absolute file-tool denials for protected memory roots; every adapter records bounded,
      non-destructive observations in run reports, separate audit files and expandable thread
      cards. Tool attempts remain distinct from changes whose writer is unknown. All four runner
      paths preserve B's updates, owner edits and system-memory refreshes after A succeeds, fails,
      stops, raises or is cancelled. Own memory stays writable; incomplete scans and audit-write
      failures are explicit. Codex's current adapter audits without per-memory isolation;
      shell/MCP limits are documented in `dev/MEMORY_BOUNDARIES.md` and the threat model.
      Full suite: **2,262 passed, 2 skipped** (110.00s). Final Windows-path, memory, capture,
      CLI-argument and documentation checks: **177 passed**. The Docs golden was updated for the
      new memory and safety guidance. Source verified; live UI and scheduler have not been restarted.
- [~] **2.16 · P1 · Commit compaction without losing concurrent history (R6; follows 2.13).**
      Summarize a versioned prefix outside the lock, then validate and preserve the current tail
      when committing. Make summary/log state recoverable across interruption. **Accept:** a turn
      appended during the model call survives; pending turns/events survive; concurrent truncate
      produces an explicit retry/conflict; interruption between writes recovers coherent history.
      **Implementation verified 2026-09-27:** immutable history snapshots; model calls outside the
      lock; prefix/summary/revision validation and preservation of the current tail. Pending and
      interleaved turns remain intact, events survive, and a changed conversation raises an
      explicit retry conflict. Summary/log/revision updates use a checksummed before/after journal;
      every reader and writer recovers prepared commits under the messages lock. Truncation uses
      the same service and advances the revision, including protection against truncate/restore
      races. Independent writers and competing compactors pass; real process exits after journal
      preparation, each replacement and cleanup recover a coherent generation. Unknown external
      edits and corrupt journals are preserved for explicit recovery. Added **36 regression cases**.
      Full suite: **2,298 passed, 2 skipped** (125.28s); **152 final focused checks** include the
      final Unicode JSONL correction. Generated references and the Docs golden are updated;
      recovery and upgrade behavior are documented in `dev/PERSISTENCE.md`. Source verified;
      live UI and scheduler have not been restarted.
- [~] **2.17 · P1 · Bind requests and runs to immutable realm identity (R7).** Pass an explicit
      realm/agent/thread/run context through handlers, title helpers, unread state, content links
      and cancellation. Include realm identity in mutations and reject stale-page mismatches.
      **Accept:** switching A → B during a turn leaves every A side effect in A; identical agent
      and thread IDs in B cannot collide; a stale A form cannot mutate B.
      **Implementation verified 2026-09-27:** immutable request and run contexts capture the
      destination before dispatch. Browser requests carry page identity; missing, conflicting
      and stale mutation identities fail closed. Completion, title generation, unread updates,
      artifacts and normal run telemetry remain in the original realm. Cancellation keys include
      realm/run identity, duplicate active IDs are refused, and each run owns its activity marker.
      Marker removal and ID release are atomic, including reuse while a previous handler finishes.
      Bound content URLs preserve original images, attachments, embeds and mini-site relative assets;
      notification links select their source realm. Eight regression tests include real HTTP
      overlapping A/B turns and the Node browser harness. Full final suite: **2,309 passed,
      2 skipped** (126.90s), including all 20 reviewed page snapshots; generated references updated.
      Protocol and upgrade behavior are documented in `dev/REQUEST_CONTEXT.md`. Source verified;
      live app and scheduler have not been restarted.
- [~] **2.18 · P1 · Supervise CLI processes and enforce terminal outcomes (R8).** Share the
      deadline, pipe draining and cleanup machinery across adapters while keeping protocol parsing
      provider-specific. **Accept:** silent/stderr-flooding children terminate within the deadline;
      missing terminal events, nonzero exit after text and malformed output cannot be successful
      turns; cancellation cleans up the process tree; partial output remains with an error/stopped
      status; callbacks and cleanup failures do not strand active-run markers.
      **Implementation verified 2026-09-27:** Claude JSON/streaming and Codex turns share a
      subprocess supervisor with monotonic deadlines, concurrent stdin/stdout/stderr handling,
      bounded queues/output and bounded cleanup waits. Windows children start suspended and join
      a kill-on-close Job Object before resuming; POSIX uses process groups. Cancellation owns
      ordinary descendants, including when the CLI parent exits first. Provider-specific parsers
      require terminal success plus zero exit and reject malformed JSON/UTF-8, invalid terminal
      fields and contradictory events. Partial output and captured artifacts survive failures;
      chat, streaming chat and agent jobs persist explicit error/stopped outcomes. Valid empty
      successes receive a completion record. Callback failures do not abandon owned processes;
      marker deletion failure falls back to terminal state, ignored by the UI. Added **70 lifecycle
      regressions**, including real child/grandchild processes and cleanup/ownership fault injection.
      Final full suite: **2,381 passed, 2 skipped** (158.29s); all 20 page snapshots pass, and generated
      references are updated. Contract, probe scope and OS/callback limits are documented in
      `dev/PROCESS_LIFECYCLE.md`. Source verified; no paid model turn, live-realm edit or app/scheduler
      restart was performed. Next in order: **2.19**.
- [~] **2.19 · P2 · Remove Claude-only gates from provider-neutral upkeep (R9).** Resolve auth
      for the actual task/recipient provider. Keep Claude keepalive explicitly Claude-specific.
      Normalize every system-job result, including skipped/disabled/error branches. **Accept:**
      Codex inbox work runs with Claude signed out; Claude-only/both/neither-connected cases behave
      predictably; every result includes job identity and a truthful status/reason. Cover the
      Telegram fallback separately from its independent listener.
      **Implementation verified 2026-09-27:** quota cost no longer imposes Claude sign-in.
      Inbox delivery and both Telegram paths check the selected recipient provider; Claude
      keepalive declares its provider explicitly. Signed-out inbox tasks remain pending without
      advancing recipient cadence, and other providers continue. Telegram gives sign-in/retry
      guidance without charging its run allowance. Probe failures fail closed. Every returned
      system-job outcome carries identity, status, reason and distinct skip/error fields; skips
      retain their status in history and do not increment failures or trigger failure notices.
      Added **41 provider-upkeep regressions**, covering all four connection combinations,
      mixed batches, recovery, manual admission, independent listener/fallback and result branches.
      Verification also exposed and fixed empty-lock initialization starvation, with a regression;
      process-cleanup test readiness now publishes the PID atomically and checks the original
      process handle rather than a potentially recycled PID. Final full Windows/Python 3.12 suite:
      **2,425 passed, 2 skipped** (161.60s), including all 20 page snapshots; generated references
      updated. Contract and retry semantics: `dev/PROVIDER_UPKEEP.md`. Source verified; no paid
      model call, live Telegram send, live-realm edit or app/scheduler restart. Next: **2.20**.
- [~] **2.20 · P2 · Make execution contracts explicit (R10).** Introduce typed run context,
      request/result/events and provider capabilities; one coordinator owns turn start, progress,
      terminal persistence and cleanup for HTTP, jobs, inbox and Telegram. Implement in small
      steps alongside 2.12/2.17–2.19, retaining compatibility facades. **Accept:** both adapters pass
      the same lifecycle contract suite; unsupported budgets/fallback/tool policies fail explicitly;
      unknown accounting is represented as unknown; routes do not mutate thread state through
      private rendering helpers. Refresh architecture/provider docs. Full UI mirror removal is D.8.
      **Source verified 2026-09-27:** frozen provider requests/policies, normalized events,
      cancellation handles and declared capabilities now supplement the existing typed context
      and result. `TurnCoordinator` owns admission, progress, terminal history, artifacts and
      reports for chat/HTTP, jobs, inbox and Telegram; `RunSession` owns activity and cancellation.
      Compatibility runner entry points and context/capture helpers remain. Adapters bind grants
      to invocation-local copies; unsupported budget, fallback and tool requirements fail before
      compaction/launch. Thread metadata persistence moved out of private rendering helpers.
      Unknown token counts/cost serialize as null; incomplete totals remain unavailable and charts
      identify missing runs. Added **68 contract cases**, including both adapters across four
      entry points, all terminal outcomes, policy isolation, observer/cleanup failures and accounting.
      Existing concurrency and usage tests now exercise the shared behavior. Full Windows/Python
      3.12 suite: **2,494 passed, 2 skipped** (175.95s), including all 20 page snapshots unchanged.
      JavaScript syntax and diff whitespace checks passed; generated references refreshed.
      Architecture/provider documentation: `dev/EXECUTION_CONTRACTS.md`. No paid model call,
      live-realm edit or app/scheduler restart. Next: **6.5 and remaining feature tickets**;
      the complete 2.21/5.10/8.1 release gate remains queued.
- [~] **2.21 · P2 · Establish a clean, reproducible Windows release gate (R11).** Pin test tools;
      freeze clock, machine context, provider/auth and home state before fixture construction;
      isolate default tests from live network/providers. Add a declared Windows/Python 3.12 CI
      workflow and the boundary/interleaving/process regressions above. **Accept:** all current
      tests pass with no accepted-failure baseline on repeated isolated runs; the two volatile
      goldens are fixed at their inputs, not blindly regenerated; skipped system jobs satisfy the
      result contract; the CI run is required before release. Preserve the separate 5.10 VM gate.
      **Baseline milestone verified 2026-09-27:** system-memory timestamps use the clock seam;
      fixture clock/home/environment are fixed before construction; fixture servers close and
      restore their state; housekeeping tests isolate auth/external jobs; skipped/error results
      retain job identity. Reviewed updates to only the affected memory/context goldens. Added
      regressions for construction inputs, fixture teardown and skipped-result identity. Two
      isolated full runs: **1,999 passed, 1 skipped** (92.78s / 88.91s). Full CI/dependency pinning
      and the post-feature release gate remain open.

---

## Phase 3 — Documentation *(runs alongside Phase 2's tail)* — **Sonnet 5**, design-system doc → Opus

Docs-as-context is the product here: Alexander's quality is capped by these, so they come before
him. Task-first, so an agent can act on them and a human can skim them. Two sections, one
generated part, one test that they don't rot.

- [x] 3.1 *(v0.99.47)* Information architecture: `docs/user/` and `docs/dev/`, each with an index that says
      what to read for which job. Served at `/docs` in-app (the route exists).
- [x] 3.2 → Opus · **Design system doc** first — buttons, pills, dropdowns, tables, the filter bar, the
      widget header, the status vocabulary, the risk tiers, spacing and type. This is Phase
      4's contract and it has to exist before Phase 4 starts. Builds on `DESIGN_TOKENS.md`.
      Done 2026-09-24 (Opus 5.5): [`docs/dev/DESIGN_SYSTEM.md`](dev/DESIGN_SYSTEM.md), from a survey of
      every rendered golden page and the helpers behind them (e.g. 54 distinct button style
      strings for what are really 7 variants × 2 sizes; pill tints at 14/15/16/18% for one idea).
      Each component: canonical spec (always the variant already used most — no new visuals),
      the class it should be (existing or *new* for Phase 4), and the variants that must
      converge. Rules decided: pill = state/judgement, chip = identity/setting; one primary
      button per view; dialog buttons right-aligned Cancel-then-confirm (as `mcConfirm`), page
      forms left-aligned primary-first; native selects in forms, `mc-fdrop` in filter bars.
      **Open for Mihai:** capability risk has two word sets for one scale — Caution/Review/Trusted
      (User tab) vs High/Medium/Low risk (review card).
- [x] 3.3 *(v0.99.47 — awaiting 3.7)* User docs: one page per surface (Overview, Ministers, Goals, Jobs, Inbox, Memory,
      Capabilities, Artefacts, Settings) written as "what this is for / how to do the five
      things you'll actually do / what the badges mean". Plus: concepts (realm, agent, grant,
      job, memory, coordinator), and a troubleshooting page seeded from real failures.
- [x] 3.4 *(v0.99.47)* Developer docs: the architecture doc from 2.10, the realm format (`SCHEMA.md`,
      updated), the engine seam, the extension-point contract from 2.7, how to run tests and
      regold, the release procedure, and the conventions (changelog entries explain *why*;
      commit messages likewise).
- [x] 3.5 *(v0.99.47)* → Haiku · Generated reference: module and function docstrings pulled into `docs/dev/reference/`
      by a script in the release procedure. The docstrings in this codebase explain *why*; use
      that.
- [x] 3.6 *(v0.99.47)* A docs-don't-rot test: every route, CLI command, setting key, and function name a doc
      references must exist. Cheap, and it catches the silent drift.
- [ ] 3.7 **MIHAI** reviews the user docs for voice and for anything that explains the app
      differently from how he thinks about it.
      *Phase 3 done 2026-09-24 (Opus 5.5), ready for this review:* **user docs** — 13 pages in
      [`docs/user/`](../armada/docs/user/index.md) (moved into the package in v0.99.72) (getting started, concepts, one page per surface, staying safe,
      troubleshooting seeded from this month's real failures), rendered in-app at `/docs` with the
      app's own `_md()`, cross-page links that stay in the window, heading anchors, and search across
      every page's text. **Dev docs** — everything developer-facing moved to
      [`docs/dev/`](dev/index.md) (links across the repo rewritten), plus new `TESTING.md`,
      `RELEASING.md`, `CONVENTIONS.md` and a "what to read for which job" index. **Reference** —
      `tools/gen_reference.py` writes `docs/dev/reference/` (82 pages) from the docstrings, part of
      the release procedure. **Rot test** — `tests/test_docs_references.py`: relative links resolve;
      every `file.py:function`, `/api/…` route and `matcap <command>` a doc names exists; the help
      index lists every page and every in-help link and `#anchor` lands; the reference is current.
      Writing the docs caught three of my own wrong guesses about the UI (the widget picker's label,
      where Retire lives, what autonomy a new agent starts with) — a reason 3.7 matters.

---

## Phase 4 — UI polish pass with a Haiku agent *(parallel with 3, after 3.2)* — **Haiku 4.5**, the audit → Opus

The cheap model executes; the expensive one audits. The golden page suite is what makes this
safe. Nothing in this phase changes behaviour.

- [x] 4.1 → Opus · Write the Haiku agent's context files: the design system doc (3.2), the invariants
      from 2.10, the golden-suite procedure (regold only after a diff review), the rule that
      every change is one ticket and one commit, and a "stop and ask" list (anything touching
      data, routes, or JS logic).
      Done 2026-09-24: [`docs/dev/HAIKU_AGENT.md`](dev/HAIKU_AGENT.md) — read-first list, the
      eight-step per-ticket procedure with exact PowerShell commands (record the failing-test
      baseline, syntax check, suite diff against baseline, regold and read every golden line, look
      in light *and* dark mode, one commit per ticket), release procedure, the stop-and-ask list,
      and the things that look like bugs but aren't.
- [x] 4.2 → Opus · The audit (once): a ticket per inconsistency — every button variant,
      every pill style, every dropdown, every table header, spacing and alignment papercuts,
      copy inconsistencies ("Realm" vs "realm", "Add" vs "Add to realm"). Numbered, with the
      page and the fix. This is the backlog Haiku works.
      Done 2026-09-24: [`docs/dev/UI_AUDIT.md`](dev/UI_AUDIT.md) — 38 numbered tickets in eight groups
      (foundation, buttons, icon buttons, pills, type, fields/filters, tabs/tables, copy, narrow
      widths, Phase 2 leftovers), each with pages, fix, size and model (H/S/M). The audit also
      **found and fixed dark mode** (D1/D2): every derived colour token resolved against the light
      ink, so muted text was invisible in dark mode (v0.99.41), and widget title bars / bar tracks
      stayed light (v0.99.42) — both now guarded by `tests/test_dark_tokens.py`. Notable tickets:
      six date formats including US month/day on a European machine (C2); form dialogs order
      their buttons opposite to confirm dialogs (B5); the Inbox calls tasks "messages" (C3);
      horizontal scrollbar on every page at 1000px (R1). **C4 needs Mihai** (the risk words).
- [x] 4.3 Haiku works the backlog: 2.1 and 2.2's leftovers first (they're the most mechanical),
      then the audit tickets, each verified against the golden suite and a screenshot.
      *(2026-09-24: the leftovers below are now tickets L1–L6 in `docs/dev/UI_AUDIT.md`, plus L7 — the
      two drifting golden pages.)*
      Known leftovers so far (from 2.1/2.2 and `ARCHITECTURE.md` §4): (a) externalize
      `webui/_core._WIZ_JS` (61-line new-realm wizard) to `static/js/`; (b) confirm and delete
      `serve.APP_HTML` (dead code); (c) the ~30 `color-mix(` calls in `static/js/*.js`, onto the
      2.2 tokens; (d) lock `routes/agents._save_agent`'s `agent.json` read-modify-write (it races
      `capabilities.py`'s locked grant writes); (e) lock or move out of render the thread
      `meta.json` writes and `_load_dashboard`'s migration write; (f) the effort dropdown lacks
      `xhigh`, which the runner accepts (from the engine audit, C). (d) and (e) are not
      Haiku-shaped — Sonnet, with a test each. *(d) and (e) done in v0.99.45.*
      **Done v0.99.66–v0.99.70 (Opus 5.5, Mihai: "wrap up Phase 4").** Every open ticket in
      `docs/dev/UI_AUDIT.md` closed in four batches except **C4** (a word choice for Mihai: risk as
      "Caution / Review / Trusted" or "High / Medium / Low risk") and **R1–R4**, which the audit
      itself moved to after the beta (the window can't go below 1400px). Buttons (B1–B8), icon
      buttons and closes (I1–I2), pills/chips/counts (P1–P4), headings (T1–T3), tabs and tables
      (TB1–TB2), fields and filters (FI1–FI4: `_FIELD`/`_LBL`/`_TA` deleted), dates (C2:
      `armada/datefmt.py`, one format set, English month names whatever the Windows locale),
      copy (C1, C3) and leftovers (L1–L3, L6). Each batch released and walked in the app.
- [x] 4.4 Dark mode: the `#eee` header and friends are hardcoded light. Once 2.2 has promoted
      styles to tokens, dark mode is a token set, not a rewrite. Decide **MIHAI**: in beta or
      after? (Recommendation: after, unless it's nearly free by then.)
      *Update 2026-09-24:* the premise is stale — dark mode already exists (`.armada-dark` token
      set in `brand.css`, Settings → Appearance), and the only hardcoded colours left in `webui/`
      are `#fff` on filled buttons and chart palettes. The real question is whether it's
      beta-quality; 4.2's audit checks it. **Checked:** it wasn't — muted text was invisible (a token bug,
      fixed v0.99.41) and widget bars stayed light (v0.99.42). After those two fixes every page
      walked reads correctly in dark mode. Recommendation now: **dark mode ships in the beta.**
      v0.99.66 added the white logo artwork for dark backgrounds (Mihai's SVGs) in the menu bar
      and Settings.

---

## Phase 5 — Distribution, updates, and operations *(the launch blocker)* — **Sonnet 5**, threat model → Opus

Strangers will install this on machines we've never seen. Everything above assumes this exists.

- [x] 5.0 **Internal rename `matcap` → `armada`** (v0.99.56, Opus 5.5, decided by Mihai 2026-09-24,
      [ADR-010](adr/ADR-010-internal-rename.md)). Package, CLI, `~/.armada` (moved automatically from
      `~/.matcap`), env vars, loggers, launchers, CSS; realm format v2 rewrites old command jobs and
      the realm cache folder. Done before the public push and the installer, so neither ever
      carries the old name.
- [x] 5.1 **MIHAI**: platform decision confirmed (0.6) and the name locked (0.8) — the
      installer carries both. Both settled: Windows (ADR-006), ARMADA (ADR-008, 2026-09-24).
- [x] 5.2 Installer: a single artefact that installs Python deps (or bundles a runtime), the
      Claude CLI check, the app, the launchers, and a Start-menu / desktop entry. Replaces the
      `.vbs` + `.venv` + `cabinet-up.ps1` arrangement, which is one machine's convenience.
      Also: a logon entry that starts the scheduler (`pythonw -m armada schedule`, no realm
      named) so jobs resume after a reboot without opening the window (moved here from 5.5).
      **Proposed 2026-09-24 (Opus 5.5): [ADR-009](adr/ADR-009-installer.md)** — the python.org
      embeddable Python + app source + pre-installed wheels in a per-user Inno Setup installer
      (no admin; scheduler at logon via HKCU Run; updates swap the `matcap\` folder from a signed
      zip, 5.4). Rejected: PyInstaller (AV false positives, a second code path), MSIX, uv
      bootstrap. Prerequisite done (v0.99.53): the folder picker uses the window's native dialog;
      tkinter is only the browser-mode fallback. **Accepted by Mihai 2026-09-24**: B, unsigned for
      the beta, Inno Setup; Windows Sandbox enabled on his machine for 5.10.
      **Built as v0.99.65 (Opus 5.5).** `tools/build_installer.py` stages the python.org embeddable
      Python 3.12.10 (pinned by SHA-256, checked against python.org's MD5), the pinned packages
      (via `uv pip install --target`), the committed `armada/` package, the Report-an-issue send
      key, every package's licence and `installed.json` (the updater's marker, 5.4). It then
      smoke-tests the staged app from an empty home folder and compiles `installer/armada.iss` with
      Inno Setup 7 into `dist/ARMADA-Setup-<version>.exe` (about 17 MB). The installer is per user
      (`%LOCALAPPDATA%\Programs\ARMADA`, no admin), creates Start menu and optional desktop
      shortcuts carrying the app's AppUserModelID, adds the scheduler at sign-in (HKCU Run,
      optional), stops only this install's own Python processes before replacing or removing
      files, and never touches `~\.armada` or a realm. At the end it notes if Claude Code isn't
      found. Found in the first clean-machine run (Windows Sandbox, `tools/sandbox_test.py`):
      without WebView2, pywebview silently falls back to Internet Explorer's engine and the app
      draws as an unstyled page. So the installer now runs Microsoft's WebView2 bootstrapper when
      the runtime is missing (asking for admin rights only when the machine needs a machine-wide
      install), and the app refuses to open without WebView2, saying where to get it. Also found:
      proxy-tools ships no licence file and is BSD, not MIT as its metadata says (notices
      corrected, text kept in `installer/licenses/`). `tests/test_installer_build.py` guards the
      agreements between the build, the installer script and the app. Inno Setup is free for
      non-commercial use; a commercial ARMADA would be asked to buy a licence. Python 3.12.10 is
      the last 3.12 release with Windows binaries (3.12 now gets source-only security fixes):
      move to a current Python before the public release.
- [x] 5.3 First-run detection: no realm registered → the wizard (Phase 6). The app must not
      show an empty dashboard to a new user.
      Done as v0.99.49 (Opus 5.5). It was worse than an empty dashboard: with nothing to open,
      `matcap app` printed a sentence to a console pythonw doesn't have and exited — the icon did
      nothing. Now the server starts with no realm ("welcome mode": `serve.Handler._route_welcome_*`,
      a whitelist of five routes; every other page is the welcome page, every other API call a
      409). `webui/welcome.py`: (1) choose ARMADA's folder (suggests `~/ARMADA`, created on an
      explicit ask if its parent exists), (2) name + template → `/api/first-realm` puts it in
      `<root>/<name>` (never over an existing folder, no path characters through the name), or
      open an existing realm folder (adopt, so 5.8c's review hold applies). The sign-in bar shows
      from the first minute. `/switch` leaves welcome mode and starts the scheduler (5.5). Also
      covers a remembered/named realm that's gone (a note says so) and several realms with none
      remembered (it lists them). Phase 6's guided setup replaces the middle of the page; the
      mode and hand-over stay. `tests/test_first_run.py` drives a real no-realm server; walked
      through by hand on Windows with a throwaway home folder.
- [x] 5.4 Update path: the app knows its version (it does), checks a release endpoint on a
      cadence (a system job), and updates in place **automatically by default**, with an off
      switch under Settings → Advanced (decided, ADR-005). Realm migration (2.8) runs on first
      start after an update. The release endpoint is GitHub Releases once the repo is pushed —
      which can only happen after 5.9 replaces the licence.
      **Decided 2026-09-24 (Mihai):** the repo goes **public** on GitHub now (source-available,
      ADR-007), as a **fresh start** — one commit of the v0.99.55 tree — because the old history
      holds personal data (an early cockpit render with real finance and health figures) and an
      unlicensed font; the full history stays local (`archive/pre-public` branch + a bundle in
      `MATCAP-private/`). Commits use the GitHub no-reply address. The tree was cleaned first
      (v0.99.55). **Published 2026-09-24:** [github.com/smikees/armada](https://github.com/smikees/armada),
      public, branch `main`, one commit at v0.99.56 (after the internal rename). Locally the old
      history is `archive/private-history` (never pushed) + a bundle in `MATCAP-private/`. Next →
      build 5.4 on GitHub Releases.
      **Done as v0.99.64 (Opus 5.5), [ADR-011](adr/ADR-011-updater.md).** Releases are three
      assets on GitHub Releases (zip, manifest, Ed25519 signature) built by
      `tools/build_release.py` from a clean commit; the key is `MATCAP-private/update-signing.key`,
      the public half is in `armada/updater.py`. Verification is RFC 8032 in plain Python
      (`armada/ed25519.py`: no compiled dependency). The `app-update` system job (12 h) downloads,
      verifies and stages a newer release with the same runtime; a runtime change says "needs the
      new installer" instead. The swap happens only where one process runs the old code: at
      start-up, by the scheduler when the window is closed and idle, or on *Restart to update* (a
      bar under the nav, and Settings). Switch: Settings → App → Advanced (the same setting as the
      system job's). A development checkout never self-updates. `tests/test_updater.py` (34 tests:
      RFC vectors, tampering, re-signing, rollback, zip layout, the swap and its undo, when each
      process may apply, the release builder's output end to end); the folder swap also run on
      Windows against a temporary install. First live run: 5.10.
- [x] 5.5 Scheduler as a service: starts with the app, survives the app closing (it already
      runs separately), one instance only (2.9), restarts after reboot. A status indicator in
      the app when it isn't running — a silent dead scheduler is "my jobs stopped" with no
      explanation.
      Done as v0.99.48 (Opus 5.5), except *restarts after reboot*, which moves to 5.2 (a logon
      entry is the installer's to create — it knows where it put things). `armada/schedsvc.py`:
      running = a live pid in the realm's scheduler lock (2.9), so there's one source of truth
      and no second daemon is possible. The window starts it on launch unless it's already up
      (appconfig `scheduler_autostart`, default on), detached with no console, so it outlives
      the window. A yellow bar under the nav on every page when it's down **and** the realm has
      switched-on scheduled jobs (no nagging about a scheduler nothing needs), with **Start it**.
      Building it found a second silent failure, fixed too: a scheduler started before a realm
      existed never ticked that realm until restarted — the daemon now rescans the registry
      each pass. `tests/test_scheduler_service.py`.
- [x] 5.6 *(v0.99.60)* **Report an issue, through Alexander** (ADR-005). Pulled forward from Phase 6
      because the beta cannot ship without it: the support icon beside the settings gear and
      the Alexander thread it opens are built *here*; Alexander's guidance content lands in
      Phase 6. In this phase Alexander does one thing well: "report an issue". It knows the
      section the user is on, takes their message, assembles the report — section, app
      version, realm schema version, platform, the last N log lines with anything token-shaped
      redacted — **shows it to the user**, and sends it on their confirmation to a dedicated
      address via Resend. Needs from **MIHAI**: the Resend account, the dedicated address, and
      the choice in ADR-005 between a send-only key in the build (fine for five invited users;
      rotate at beta end) and a small relay that holds the key (what a public build needs).
      Recommendation: key for the beta, relay before public.
      **Decided 2026-09-24 (Mihai):** use his domain, **stamih.com** — ARMADA can live on a
      subdomain, and he can create mailboxes. Plan: a dedicated support mailbox on stamih.com
      (not his personal one — reports are untrusted text, and an agent triaging them should see
      nothing else); Resend (free: 3,000 emails/month, 100/day) sends the reports from a
      verified **sending subdomain** so the root domain's mail and reputation are untouched, with
      a *sending-only* API key restricted to that subdomain — the one kind of key that's safe to
      ship in a beta build. **MIHAI**: who hosts stamih.com's mail and DNS; create the mailbox;
      the Resend account.
      Done as v0.99.60 (Opus 5.5), mailbox and domain set up by Mihai the same day. The ix
      `support-ai` icon (Mihai's pick) beside the gear on every page opens *Write → Review →
      Send*: `support.preview` builds the report server-side and keeps it under a one-use token,
      `support.send` sends that exact text — what was shown is what goes. Log tails pass through
      `support.redact` (API keys, bearer/OAuth/Telegram tokens, JWTs, long secret-shaped strings,
      email addresses other than the one typed, the Windows user name). From
      reports@armada.stamih.com to armada@stamih.com, `reply_to` only if an address is given;
      5 per hour per install; any failure saves the report under `~/.armada/reports/` and says
      where. The key: `armada/support_key.txt`, git-ignored, placed by the build (THREAT_MODEL
      T12). **Not yet Alexander**: the icon opens a dialog, not his thread — the thread and his
      guidance arrive with Phase 6, and the dialog becomes his first message.
- [x] 5.7 Beta labelling: the version string, the title bar, and the About page say beta. The
      feedback button is visible on every page.
      Done as v0.99.50 (Opus 5.5), labels only: `brand.CHANNEL = "beta"` drives the window title
      ("ARMADA beta"), a BETA pill beside the logo in the nav on every page, the welcome page, and
      Settings → App beside the version. `__version__` stays numeric (the update check compares
      it). 1.0 is one edit: `CHANNEL = ""`. **The feedback button is 5.6's** — it's the same
      support icon, and a button before 5.6 has nowhere to send the report; it ships with 5.6.
- [x] 5.8 → Opus · Threat model, written: what an agent can read and write, what a capability can reach,
      what the review protocol catches, secrets handling (Telegram token lives outside realms —
      keep it that way), CSRF on the local server (done), what's out of scope. One page in
      `docs/dev/`.
      Done 2026-09-24 (Opus 5.5): [`docs/dev/THREAT_MODEL.md`](dev/THREAT_MODEL.md). Headline: a
      tool turn runs Claude Code with `--dangerously-skip-permissions`, so *an agent with tools is
      the owner* — every threat reduces to "can someone else get words in front of an agent, or
      code into the app's page". Writing it found and **fixed two real holes the same day**:
      DNS rebinding let any web page drive the local API, including starting an agent turn
      (v0.99.43, Host allowlist); and ~40 `onclick="f('{E(x)}')"` sites let a quote in a
      capability name or model-written thread title run as script (v0.99.44, `_base._J`). Open
      findings are the tickets below; T7 (no login on the local port) is accepted for the beta.
- [x] 5.8a *(v0.99.58)* **Approved by Mihai 2026-09-24 (option 2, second port)** → Sonnet · Untrusted HTML on the app's origin (THREAT_MODEL T3): section
      mini-sites, mirrored external pages and `.html` attachments run scripts that can call the
      whole API. Options: (1) send `Content-Security-Policy: sandbox allow-scripts allow-forms
      allow-popups` on those responses — small change, but a sandboxed page can't use
      `localStorage`, so a mini-site's own theme toggle may stop remembering; (2) serve them from a
      second local port (a different origin) — nothing breaks, more work. Recommendation: (2).
      Done as v0.99.58 (Opus 5.5): option 2, with option 1 as the fallback when the second port
      can't bind. `origins.py` + `serve.ContentHandler` (port + 1, falls back to any free port
      after a restart hand-over). Found on the way: GETs that change state (`/switch`,
      `/api/chat-stop`) were reachable from any page by `<img src>` — the app now refuses
      cross-site GETs outright. `tests/test_content_origin.py` drives both servers over HTTP.
- [x] 5.8b *(v0.99.57)* **Approved by Mihai 2026-09-24** → Sonnet · Bring-a-link reviews run with full tools on untrusted content
      (T4). Recommendation: run the review turn with only read/fetch tools (deny Bash, Write,
      Edit, NotebookEdit, Task…) and accept a shallower review; a reviewer that can be told to
      run commands by the thing it's reviewing is the worst place for that risk.
      Done as v0.99.57 (Opus 5.5): an engine-level *sealed turn* (`only_tools`) rather than a deny
      list — a deny list has to name everything dangerous, an allow list only what's needed.
      WebFetch + WebSearch only (Read was left out too: file reading plus fetching is an exfil
      path). Flags checked against Claude Code 2.1.263. `tests/test_sealed_review_turn.py`.
- [x] 5.8c *(v0.99.46)* → Sonnet · Adopting a realm holds its scheduler until the owner has seen what it will run
      (every command job verbatim, agent jobs by name) and released it (T5).
- [x] 5.8d *(v0.99.46)* → Sonnet · `/api/delete-artefact` and `/api/open-file` act only on paths under the app
      root / the realm's workspace (T6). With tests.
- [x] 5.8e *(v0.99.46)* → Sonnet · Telegram: refuse non-private chats when linking and answering; the link step
      confirms the name before saving (T8).
- [x] 5.8f *(v0.99.46)* → Sonnet · Export leaves out `.mcp.json`, `.env` and similar secret-bearing files by default,
      and says so (T9).
- [x] 5.8g *(v0.99.46)* → Sonnet · Audit `static/js/*.js` `innerHTML` sinks fed by API data; escape or switch to
      `textContent` (T10).
- [x] 5.9 Licence and third-party notices in the installer. **MIHAI**: depends on 0.7.
      Done as v0.99.51 (Opus 5.5) for the repo and the app; the installer (5.2) copies both files
      in. `LICENSE` now names PolyForm Noncommercial 1.0.0 by its canonical URL (which the
      licence's own Notices clause accepts in place of the text) with the `Required Notice:`
      copyright line; README and Settings → App → About say source-available, never "open source"
      (ADR-007). `THIRD_PARTY_NOTICES.md`: the eight Python packages actually in `.venv` with
      licences read from their metadata, Python, Barlow (OFL), the ten icon sets, and Claude Code
      as not-bundled with a trademark/no-affiliation line. Removed `Heavitas.ttf`: unused since
      the wordmark became a bitmap, and a font of unverified licence has no business in a
      distributed build. `LICENSE` then got the full official text, verbatim and unmodified (the
      PolyForm repo licenses reuse of its texts on that condition), under the `Required Notice:`
      line — 2026-09-24, at Mihai's request. **MIHAI**: ADR-007's "have someone qualified read it
      once" still stands; the CLA/DCO choice before the first outside pull request.
- [ ] 5.10 A clean-machine test: install on a VM that has never seen the app, run the wizard,
      run one job. This is the launch gate for Phase 5 and it is repeated before every beta
      build.

---

## Phase 6 — Alexander-the-guide and the setup wizard *(built together)* — **Sonnet 5**, Alexander's prompt → Opus

One guides the other. Alexander's knowledge is the docs (Phase 3); the wizard's pieces are
`preflight`/`doctor`, `templates.py`, and the mirrored sources.

- [x] 6.1 → Opus · Alexander's identity and rules: bundled with the app, not a realm agent; has the docs
      and the app's logs as context; can read realm state; **cannot write realm state or code**
      in v1 — it explains and it guides. Its system prompt is a document in `docs/dev/` so
      it's reviewable.
      **Done 2026-09-25 (Opus 5.5) from Mihai's brief:** a specialist in how ARMADA works (CX first,
      developer second), a builder of add-ons, and the best support professional — explain, fix,
      or report — the one agent the owner can't change, and ARMADA's own voice. The prompt is
      [`armada/alexander/PROMPT.md`](../armada/alexander/PROMPT.md) (shipped with the app), the design
      [`docs/dev/ALEXANDER.md`](dev/ALEXANDER.md), the widened scope
      [ADR-012](adr/ADR-012-alexander-scope.md): he proposes, the owner confirms, the app acts
      (remedies from a fixed list, data-only add-ons, reports). Scripted in the wizard; **Opus 5.5 at
      High** for support, fixed; his usage counts as **System** in cost reports. Threat model T13.
- [x] 6.2 Alexander's guidance, in the thread 5.6 already opened: with the docs (Phase 3) as
      context it answers "how do I", explains what a page is for, and points at settings. The
      button and the thread exist from 5.6; this phase makes him knowledgeable.
      **Done 2026-09-25 (v0.99.73):** his portrait replaces the support icon beside the gear and
      opens a drawer (`static/js/alexander.js`); each turn is sealed Opus 5.5 High with every help
      page, a realm snapshot, the page, the remedies and the add-on contract
      (`alexander/support.py`); fixes, dashboard widgets and reports come back as cards with one
      button each. Dashboard widgets are the add-on surface's first consumer. Report an issue is
      in the drawer and pre-filled from his report card. Needs Claude Code 2.1.280+.
- [x] 6.3 "Why did this fail": Alexander can be summoned from a failed job or run with its log
      attached, and answers from the log and the docs.
      **Done 2026-09-25:** "Ask Alexander" beside every failed run (job page, Jobs list); he gets
      the run and ARMADA's log lines within ten minutes of it, redacted.
- [x] 6.4 The wizard, five to seven steps, each producing a real artefact, Alexander narrating:
      (1) dependency check — Claude CLI, subscription, `doctor`; (2) name your realm and pick
      a workspace folder; (3) appoint the coordinator and two to four ministers from templates
      — **MIHAI** decides which templates ship and reviews their text; (4) add the safe
      capabilities — from the mirrored marketplace and Anthropic skills, with the review
      report shown; (5) one real job, scheduled and run while you watch; (6) where things are
      — a one-screen tour of memory, grants, and the Capabilities page; (7) done, with
      Alexander's button pointed out.
      **Done 2026-09-25 (v0.99.73), eight steps:** welcome · checks (Claude Code installed, current
      and signed in, with Install / Update / Sign in buttons) · folder and names · team (all four
      templates, as they are) · recommended capabilities (`armada/recommended.py`: nine Anthropic
      skills, all Low risk, none needing an account) · a real first brief from the coordinator,
      streamed · tour · done. Everything Alexander says is `alexander/wizard_script.py`. Two
      halves (welcome mode, then `/setup` in the new realm), resumable from `realm.json`.
      **Provider follow-up, source implemented 2026-09-28:** shared setup/App connection controls
      for Claude, Codex or both; official browser sign-in, disconnect/reconnect, and connected-provider
      model choices. Codex-only setup applies executable defaults and reruns preflight. Alexander's
      app-wide model/effort controls live under App → Advanced; Automatic prefers Opus 5.5/Medium with
      Claude, otherwise GPT-6 Sol/Medium. Isolated browser checks verified connection combinations,
      reconnect/model refresh, and saved overrides after reload. Real OAuth callbacks and the fresh
      installer remain acceptance work. Final suite: **2,519 passed / 2 skipped** (183.23s), with
      all 20 rendered-page goldens passing. See [Provider onboarding](dev/PROVIDER_ONBOARDING.md).
      **September 28 refinement:** Mihai selected Medium for Alexander's Claude default and approved
      the isolated-profile → fresh-Sandbox testing plan. Both dropdowns mark Automatic as `(default)`;
      the panel explains Alexander's role instead of listing its model defaults. Installed acceptance
      remains pending; this approval does not mark the test execution complete.
      Refinement verification: **156 passed**, covering Alexander, provider preferences, all 20 page
      goldens and documentation references; provider JavaScript syntax check passed.
      **Immediate CX walkthrough prepared 2026-09-28:** current-source test installer compiled,
      bundled-runtime smoke checks passed, and fresh Windows Sandbox launched at the interactive
      installer. Run: `build/setup-cx-5xfga7nt`; real provider login and user walkthrough pending.
      This lets Mihai assess the current end-to-end CX before the first-artifact refinement.
      Sandbox reached the desktop but did not auto-launch the installer. Supplied the manual
      installer entry point and opened an empty-profile native test copy; welcome page verified
      on port 57641. Wizard walkthrough is ready; installer acceptance is still unverified.
      **First walkthrough feedback:** missing test-profile Desktop and CODEX_HOME folders blocked
      the folder picker and Codex login. Corrected the launcher and app error paths; added optional
      installer CLI tasks, in-app install/update before sign-in, explicit installed/signed-in states,
      login cancellation/reopen/failure handling, existing-realm adoption, and the minimal welcome
      screen. Regression suite: **2,539 passed / 2 skipped**, then **290 focused checks passed**.
      Installer rebuilt at `build/setup-cx-xd45lydh`; packaged welcome/provider screens verified.
      Real vendor installation and login acceptance remain pending; see the provider onboarding log.
      **Second CX feedback:** Claude update failure reproduced (`Get-FileHash` unavailable under
      inherited PowerShell module paths) and fixed; official installation of 2.1.283 verified in the
      isolated profile. Removed the cp1252 stdout failure after realm creation. Greeting and unboxed
      layout refined; names moved to Team and made required; Folder owns existing-realm adoption.
      Team now offers the approved prepared Cabinet roster, full profile dialogs, drag/Add selection,
      custom profiles, personalized owner references and Alexander-aligned model/effort defaults.
      Check lists both CLI versions and bundled/runtime dependencies. Browser creation reached
      Capabilities; 68 focused checks passed. Updated regression/build evidence follows in the
      provider onboarding log. First-artifact/time-to-first-value acceptance is still open.
- [ ] 6.5 Time-to-first-value measured: the wizard is done when a new user has watched one
      real job produce one real artefact. Everything else is Alexander's job later.
- [x] 6.6 Alexander's answers are grounded: every answer cites the doc page or the log line it
      came from, so a wrong answer is traceable to a wrong doc.
      **Done 2026-09-25:** the prompt requires `[help: …]`, `[realm: …]`, `[log: …]` citations; the
      drawer turns help citations into links to the page.

---

## Phase 7 — The Council *(v1 differentiator; dedicated design session first)* — design → **Opus 5.5**, build → Sonnet 5

Plan-only. Output is proposals through the existing approve/dismiss machinery. The design session
comes before any code.

- [ ] 7.1 → Opus · **MIHAI** + agent: design session. Decides the turn model (sequential, visible),
      participant cap, how the coordinator invites (the "raised hands"), how much context each
      participant gets (cost is the real constraint — the subscription-limits header exists for
      a reason), how the coordinator summarises, and what a "council thread" looks like next
      to an ordinary one. Output: a design doc in `docs/dev/` and a UI sketch.
- [ ] 7.2 Data model: a council is a thread with a roster and a phase (convened → in session →
      summarised → actions). Reuses thread storage.
- [ ] 7.3 The coordinator's invite step: reads the prompt, picks participants with a one-line
      reason each, adds framing context. The user can add or remove before it starts.
- [ ] 7.4 Turn-taking: each participant answers in order with the prior turns visible;
      progress shown; a hard cap on turns and tokens per council.
- [ ] 7.5 Summary and actions: the coordinator produces proposals — job proposals and inbox
      delegations, the two types that already exist — and the user approves or dismisses each.
      No new action type; no execution from inside a council.
- [ ] 7.6 The UI iteration the design session anticipated: at least two rounds on the real
      thing with **MIHAI** before it's called done.
- [ ] 7.7 Cost guard: the pre-flight shows the estimated tokens before convening, and refuses
      if it would cross the weekly limit.

---

## Phase 8 — Beta launch — **Sonnet 5**

- [ ] 8.1 Release procedure written and rehearsed: version bump, changelog, full suite, regold
      review, clean-machine test (5.10), build, tag, publish, announce.
      **Prerequisites:** the 2026-09-26 review's 2.11–2.21 acceptance gates and 5.10 pass; no
      security/data-loss finding is waived by the historic test baseline or earlier phase sign-off.
- [ ] 8.2 **MIHAI**: the invite list and the message.
- [ ] 8.3 Beta build shipped to the invited group.
- [ ] 8.4 Feedback triage loop: reports from 5.6 land somewhere Mihai reads daily; each becomes
      a ticket or a "won't fix, here's why". Two weeks minimum.
- [ ] 8.5 **MIHAI** decides: another beta round, or v1.

---

## DEFERRED — after beta, in this order

Listed so we never have to work out what comes next.

- [ ] D.1 **Alexander-the-developer**, through the extension points from 2.7 only: writes
      widgets, filters, themes, job templates, dashboard layouts as add-ons (2.7); never
      patches the app. Runs as a separate process with its own checkout. Reverting is deleting
      an add-on's folder. Requires: the add-on surface proven by at least one built-in feature
      using it.
- [~] D.2 **Second engine (OpenAI) — promoted into current work by Mihai, 2026-09-26.**
      No longer deferred until beta demand: the Codex adapter and cross-provider model selection
      are implemented in the working tree. Remaining provider hardening is tracked in 2.12 and
      2.18–2.21; scope/limitations are in [Codex integration](dev/CODEX_INTEGRATION.md).
- [ ] D.3 **Dark mode** (if not done in 4.4).
- [ ] D.4 **Second platform** (if 0.6 named one).
- [ ] D.5 **Council v2**: whatever 7.6's iterations couldn't fit — async councils, standing
      councils on a schedule, councils that read a document.
- [ ] D.6 **Capabilities**: automatic re-review when a capability updates (the update check
      exists); a "what changed" diff of a skill between versions.
- [ ] D.7 **Public launch**, with whatever the beta taught us.
- [ ] D.8 **Complete explicit UI module boundaries (review R10).** Replace remaining
      `globals().update` namespace mirrors with explicit imports/exports, preserve the public
      renderer facade, and enforce import directions in checks. Migrate module by module with
      deterministic goldens; do not make a frontend rewrite a prerequisite. Execution ownership
      and moving state mutations out of renderers are already required before beta in 2.20.

---

## Where things stand *(update this block as we go)*

October 4 restart fix: v0.99.78 is published. Windows re-exec now quotes each argument, fixing exits after Restart to update when realm or installation paths contain spaces. Native app/scheduler tests and a packaged ARMADA.exe probe cover these paths, apostrophes and Unicode. The isolated gate passed 3,071 tests with five skips; exact-commit Windows/PHP CI and packaged startup/recovery checks passed. Public update signatures and artifact hashes were verified. The first restart from an affected older version may still require one manual launch. The website points to 0.99.78; unsigned-installation and clean-Sandbox limitations remain unchanged. See [verification](dev/RELEASE_0_99_78.md). No acceptance checkbox changes.

October 4 follow-up: v0.99.77 corrects Gemini dropping an explicitly approved ancestor realm/workspace root. Native fixture requests failed before and succeed after; outside-scope access remains denied. Windows environment probing no longer uses Python's shell fallback; other background launch paths share hidden startup settings. The specific intermittent console on the other PC remains unconfirmed. The isolated gate passed 3,065 tests with five skips, exact-commit Windows/PHP CI passed, and package startup/recovery and public downloads were verified. Compatible 0.99.75/0.99.76 installs update in-app. The website points to the unsigned 0.99.77 installer; signing and clean-Sandbox acceptance remain open. See [verification](dev/RELEASE_0_99_77.md). No acceptance checkbox changes.

October 4 follow-up: v0.99.76 is published with connected-engine team defaults and hidden Windows background checks. Setup now uses a release-owned model policy independent of Alexander, with provider-default fallbacks for unfamiliar catalogues. Existing choices are preserved. Gemini's missing cwd context was also reproduced live: it guessed /workspace and hit a read permission denial; the same test passes after explicit Windows task-folder context is supplied. Regression tests include all provider combinations and a real Windows no-console probe; the final default suite passed 3,055 tests with five skips. Packaged startup and recovery checks and exact-commit Windows/PHP CI passed. The signed update is compatible with 0.99.75; the website points to the 0.99.76 unsigned installer. Publisher signing and clean-Sandbox GUI acceptance remain open; see dev/RELEASE_0_99_76.md for the recorded distribution deviation. No launch acceptance checkbox changes.

October 4: version 0.99.75 is installed on Mihai's machine, preserving the realm registry, settings and active realm; the scheduler and authenticated API were verified after restart. The public-readiness refactoring is tracked in [the original review](dev/PUBLIC_READINESS_REVIEW_2026-10-03.md). R1–R6 are implemented and verified: the live report relay, authenticated local API, recoverable updates, command-tree ownership, timezone data/validation and strict registry persistence. The final isolated suite passed 3,020 tests with five skips, and 23 PHP assertions passed without network. R7's release gates are implemented; [Windows/PHP CI passed for source commit c2be696](https://github.com/smikees/armada/actions/runs/37197850193). Mihai explicitly authorized publishing the unsigned beta, and [v0.99.75](https://github.com/smikees/armada/releases/tag/v0.99.75) is now the website download. The release uses the exact locally verified installer and an Ed25519-signed update manifest for that source commit. The website explains that unsigned installation can still be blocked with error 4551. Trusted publisher signing and clean-VM GUI acceptance remain open (Microsoft's WebView2 installer fails in Sandbox). This one-release exception does not change the general release gates or any launch acceptance checkbox. Users upgrading from earlier betas must run the full installer once.

October 3 release: v0.99.74 collects the three-engine integration, job result and
retry behavior, standalone desktop lifecycle, provider discovery, setup and UI changes since
v0.99.73. README, GitHub metadata and release documentation are up to date.
Full Windows verification: 2,923 passed, 2 skipped; 41 changed JavaScript files passed syntax
checks. Golden changes were reviewed against the requested UI updates. Validation also corrected
ad-hoc task classification and kept newer-schema realm adoption read-only. The Windows installer
and signed update artifacts are published in GitHub release v0.99.74; the installer download
returns HTTP 200. Installer smoke checks and 18 packaging tests passed, including the correction
for Windows PowerShell security-module discovery. The armada.stamih.com
landing page was approved by Mihai and published on October 3; HTTPS assets and the installer link are verified.
No launch-plan acceptance checkbox is changed by this release preparation.

October 3 Check spacing: plan guidance follows the disconnect note beneath the engine cards.
Cards now collapse empty feedback/login regions and size to actual content, keeping the three
status groups and bottom actions aligned. Real sign-in links/errors can expand the shared row.
Focused checks passed and native Check view verified. The refreshed Windows status now also
reports Claude signed in on Claude Pro; all three engines are connected in the review window.

October 3 Check follow-up: signed-in engines show Subscription type below authentication.
Reported plans are normalized; absent plans explicitly say "Not reported by CLI". Card/button
alignment is retained. Native Windows metadata confirms Claude's current engine-login record has
no access or refresh token (expiry zero); why it was cleared is not established. 111 focused
checks passed, including subscription clearing on sign-out/check failure. User acceptance remains open.

October 3 setup polish: supplied welcome/tagline and subscription guidance are in place.
Check has three aligned compact engine cards, original provider colors and separate CLI/auth
status pills. The review launcher now isolates only Armada data and preserves real Windows
vendor homes: its previous empty credential directories caused the false Claude/Codex sign-outs.
Probe failures remain distinct from a confirmed sign-out. User walkthrough acceptance remains open.
Installed changes and native Check layout verified: Codex and Gemini are signed in; Claude's own
Windows CLI and the live app currently both report signed out. Read-only diagnostics confirmed the
real Windows home/launchers. Provider/review/docs checks: 112 passed; provider/auth checks: 24 passed.

October 3 setup review: onboarding and the optional Windows installer tasks now name
Claude, Codex and Gemini through Antigravity consistently. Gemini-only team creation
now passes the server's provider check. The wizard uses the current support portrait
with cache busting; its tour explains current job outcomes, retry/model overrides,
engine limits, Documentation search and tray scheduling. `tools/review_setup.py`
opens current source under Explorer with a fresh isolated profile and real provider
connections. Focused checks: **150 passed**; installer compilation passed. A fresh
native review window is open at Start setup; user walkthrough acceptance remains open.

October 3 startup correction: the loading artwork is now a child panel in the main
window. Server preparation runs after that window is created, and the panel stays
until the dashboard paints; the temporary splash process/window has been removed.

October 3 icon polish: model and connected provider icon shadows have been removed;
further treatment is deferred to a separate design task.

October 3 reliability fixes: Windows app launches detach through Explorer before realm
selection, avoiding Codex's process lifetime and MSIX filesystem view. Provider discovery
retains the installed Gemini executable path; the native splash covers early startup.
Agent-job retries now have a validated 0–3 dropdown, durable backoff and per-attempt
results, with uncertain delivery held for reconciliation. Focused verification and the
October 3 Digest recovery are recorded in this work session; release acceptance remains open.

September 29 second wizard review: Welcome says setup takes about ten minutes. The State roster
names Wedgwood's agent Josiah and uses the supplied portrait. Wikipedia links have no underline; the
coordinator checkbox has no optional suffix; profile-preview guidance leads the modal. Done offers
Open realm or Open and connect Telegram now, the latter opening App settings scrolled to Telegram.
The folder error came from a completed test realm still displaying a stale wizard page. Completed
setup now redirects to the app and rejects step rewrites; unfinished setup can relocate the realm,
then resumes at Naming. Its Folder step again lists other registered realms, which were never
deleted. A fresh isolated Setup CX profile is open for the next walkthrough; the earlier profile
and its realms remain intact. Full suite: **2,569 passed, 2 skipped**; the Windows process-cleanup
test now waits for its fixture descendant before measuring cleanup under load. The real first task
and user acceptance remain open.

September 29 wizard review: Folder and Naming are separate steps; Team opens with its realm types
and roster visible. The create-profile form labels optional inputs explicitly, and custom profiles
can be deleted from the team. Prepared State profiles now show Benjamin and David with the supplied
portraits and Wikipedia links; Company adds a CPO and all Company/Ship starter roles have full
generic profiles. Signed-in provider status is green with a check; Capabilities has tighter Enable/Add
labels and the requested secondary action; First task reveals stable Markdown blocks progressively,
word by word. Done recommends connecting Telegram through App settings. Browser fixtures exercised
the team, capabilities, streamed reply and Done; the full suite passed **2,568 tests, 2 skipped**.
The refreshed native Setup CX test window preserves the existing isolated profile. A real
authenticated first task and user walkthrough remain open.

September 28 latest wizard review: the login adapter drains output without waiting for a newline,
publishing only validated provider authorization URLs after output settles. The pending card shows
the full clickable/copyable URL, and says it is preparing the link until one is available; cancellation
and completion clear it. Recheck buttons have fixed widths and feedback lines reserve their full
height, including the formerly hidden empty Check-again paragraph. Browser measurements confirm
identical positions/sizes before and after both refresh actions.

Alexander's wizard subtitle is YOUR GUIDE. Realm types and profiles are hidden together until both
names are present, then fade in over 320 ms. The avatar picker expands over 280 ms (both respect
reduced motion); the placeholder is "e.g. Warren". Governing document previews put the note first,
then the icon beside the title. First task reuses the thread message renderer without action/sidebar
controls; output is buffered and rendered as sanitized Markdown before becoming visible, with a
working indicator meanwhile. Capability inclusion and enabled state are separate: all recommendations
start checked, unchecking disables the toggle, rechecking restores its prior state, and disabled
choices are still added to Capabilities > User. Add and continue advances after successful additions
in one action; retries preserve successful additions. Planned connections retain their authentication
requirement even if enabled. The header support icon is 18 px, uses the standard icon colour and has
no ring; the drawer's New conversation action is removed.

Full suite: **2,567 passed, 2 skipped**. Browser validation used disposable provider/first-reply
fixtures, including an 11-capability realm with 7 enabled and 4 disabled. JavaScript syntax and diff
checks passed. The final CSS reservation correction was verified in a fresh browser after the suite.
Fresh installer `build/setup-cx-n5c1nf8f/bundle/ARMADA-CX-Setup.exe` passed embedded-runtime smoke;
the isolated review window is reopened with its existing test profile. Main app reloaded only after
agents were confirmed idle, to keep its Python markup and updated JavaScript in sync. User acceptance
and a real authenticated first-task walkthrough remain open.

September 28 provider Settings follow-up: the main app was still serving pre-onboarding Python
markup alongside the updated JavaScript, leaving obsolete sign-in/recheck handlers disconnected.
Shared setup/Settings provider cards now include provider icons, CLI versions, explicit Signed-in
or Not signed in status, Sign in with an external-link icon, and Recheck with progress/completion
feedback. Status requests have a deadline and an actionable failure state. Removed the static
provider/subscription badge from the header; retained the wizard support icon and reduced/lowered
the beta pill. The main app was reloaded through its own Restart control after checking agents idle.
Browser checks confirmed real Codex sign-in/status refresh and the isolated sign-in action; the
main profile currently has no Claude CLI, correctly presented as Install Claude CLI. Full suite:
**2,565 passed, 2 skipped**; the focused suite passed 86 tests. Fresh package:
`build/setup-cx-4_nv3dnl/bundle/ARMADA-CX-Setup.exe` (embedded-runtime smoke passed).
Telegram recommendation: offer an optional connection after the first task, with Skip for now,
reusing App Settings controls; do not make it a prerequisite. This recommendation is recorded for
the next setup decision, not implemented as an extra step in this pass.

September 28 fifth setup CX pass: Welcome, Check and Capabilities use the requested copy with
wider introductory text. Check again waits for any current refresh, then runs a fresh check with
an animated icon and completion feedback. Team profiles stay hidden until both names are given;
profile notes appear at the top, capability fields are omitted, and custom agents can become the
coordinator. State/Company/Ship/Blank show The Constitution/The Memorandum/The Code/The Covenant,
with adapted read-only previews; the same names are used in Memory, agent pages and Realm settings,
where the document can now also be read and edited. Enabled capabilities sort first within each
type; secondary actions sit beside the primary action. Added the requested info/Telegram icons,
smaller lower beta pill and provider icons beside Week/Session rows.

Returning to Folder can move the unfinished realm to a new or empty location, preserving the team
and work. Moves verify copied contents, update registration/preferences and roll back failures;
active turns/scheduler leases block relocation. With other registered realms, the destination must
remain inside the existing Armada root; a sole new realm can move to a different root. Unfinished
setup realms are excluded from scheduler startup/enumeration until setup completes. Browser checks
confirmed folder relocation, preserved team, coordinator selection, document previews, capability
ordering, footer placement and the Overview/Settings changes. Full suite: **2,565 passed, 2 skipped**;
JavaScript syntax and diff checks passed. The earlier scheduler contention test passed in this full
run; its intermittent failure remains a test-stability observation, not a scheduler fix in this pass.
Isolated installer `build/setup-cx-1nty4fcm/bundle/ARMADA-CX-Setup.exe` passed runtime smoke checks;
the refreshed **ARMADA — Setup CX test** window preserves the existing test login profile.
User walkthrough/acceptance remains pending.

Previous fourth-pass record (folder relocation above supersedes its fixed-location behavior):

September 28 fourth setup CX pass: every numbered step has Back; realm-mode setup includes the
opening steps and an editable, prefilled Team builder. Saving updates the current realm label,
owner and roster; removed agents are retired, restored profiles keep their history, and existing
capabilities/model settings remain. Folder shows the committed location after creation (renaming
a realm changes its label, not its on-disk path). Active turns block team mutation; failed writes
roll back, including exact Windows line endings. Added regression coverage for persistence,
custom-agent identities, retirement/restoration, and rollback. "First task" replaces the visible
"First job" label (internal progress ID retained); capability cards are tighter; Tour and the app
header share the ix/support-ai icon and requested copy. Browser walkthrough verified edits,
restoration, Back through all steps, reload/resume, and the main header. Full suite: 2,560 passed,
2 skipped, one scheduler concurrency test failed; all 26 tests in that module passed on rerun.
Isolated installer `build/setup-cx-n3ens0rv/bundle/ARMADA-CX-Setup.exe` passed embedded-runtime
smoke checks; test app reopened with its existing test login profile. User CX acceptance pending.


September 28 setup CX: source changes restore Alexander’s numbered Welcome after the unlisted
splash, show runtime health/version/repair links, refine the roster and read-only/create dialogs,
and share capability cards and persistence with Capabilities > User. Browser/backend validation
passed (2,558 tests, 2 skipped); isolated packaged app refreshed with its test sign-ins preserved. Community Google connector shortlist is documented in
`docs/dev/STARTER_CAPABILITIES.md`; automated connector installation/OAuth remains open.


| Phase | State | Model | Notes |
|---|---|---|---|
| Codex provider (2026-09-26) | `[~]` | Codex | Requested by Mihai: combined per-agent model picker, Codex CLI adapter and automatic provider routing. Subscription limits shows Codex left and Claude right, each with an icon beside Week/Session bars; unavailable readings stay gray without percentage/reset text. Claude sign-out is a dismissible notice once per app session. See `docs/dev/CODEX_INTEGRATION.md` for behavior, verification and remaining Claude-specific features. |
| 0 Decisions | `[x]` | Opus 5.5 (ADRs written on Fable 5.1) | ADR-001…007 **accepted** 2026-09-21. ADR-008 (the name: ARMADA) accepted 2026-09-24. |
| 1 Catalogue reframe | `[x]` | Sonnet 5 | Shipped as v0.99.25, then four polish rounds (v0.99.26–v0.99.29) from Mihai's real use of Bring a link against the live Claude CLI — spinner/timer split, results-area spinner, risk-bucketed assessment (now floored to the mechanical worst-case, one pill instead of two), full-review paragraph breaks (incl. a compound-label fix), inline Runs/Can-touch icons, animated full-review caret, matched icon sizes. Full suite clean each time (regolds reviewed). Bring a link has now run for real, not just against the test fake. Closed: Mihai read 1.5's copy and signed off 2026-09-21. |
| 2 Architecture | `[~]` | Prior phase: Sonnet/Opus; Sept-26 review: Codex | Earlier 2.1–2.10 deliveries remain recorded above. The current working-tree review found 8 P1 and 3 P2 findings: content/policy boundaries, write and scheduler races, destructive memory rollback, compaction loss, realm identity, CLI lifecycle, provider gating, contracts and test reproducibility. Source implementations for 2.11–2.20 and the 2.21 baseline are verified; final suite: 2,494 passed / 2 skipped. Next: 6.5 and remaining feature tickets, then the complete release gate. These are beta prerequisites; broader UI namespace cleanup is D.8. Evidence: `docs/dev/ARCHITECTURE_REVIEW_2026-09-26.md`. No new implementation is marked complete. |
| 3 Docs | `[~]` — 3.7 (Mihai's review) left | Sonnet 5 (3.2 → Opus, 3.5 → Haiku) | 3.2 done (`DESIGN_SYSTEM.md`). Seeds: `SPEC.md`, `SCHEMA.md`, `DESIGN_TOKENS.md`, plus Phase 2's `ARCHITECTURE.md`, `ENGINE_SEAM_AUDIT.md`, `EXTENSION_POINTS.md`. |
| 4 Polish (Haiku) | `[~]` | Haiku 4.5 (4.1, 4.2 → Opus) | 3.2, 4.1, 4.2 done 2026-09-24. Backlog: `docs/dev/UI_AUDIT.md` (38 tickets; F1 first). Dark mode fixed (v0.99.41–42). C4 needs Mihai. |
| 5 Distribution | `[ ]` | Sonnet 5 (5.8 → Opus) | Name settled (ADR-008) — unblocked. 5.6 now includes the support button + Alexander thread shell. Needs Mihai's Resend setup. |
| 6 Alexander + wizard | `[~]` | Prior: Sonnet/Opus; provider follow-up: Codex | Setup now supports Claude, Codex or both; App settings manage connections and Advanced controls Alexander's model/effort. CX feedback fixes and rebuilt package verified: optional CLI installation, explicit install/login states, minimal welcome screen and folder-picker fixes. Second feedback: full prepared Cabinet roster, mandatory owner/realm names, drag/Add selection, profile dialogs and custom agents; Claude installer and cp1252 creation failures fixed. Claude 2.1.283 installation and browser progression to Capabilities verified; 2,551 tests passed / 2 skipped. Refreshed test window preserves Codex login. Full first-artifact/time-to-first-value acceptance remains open. See `docs/dev/PROVIDER_ONBOARDING.md`. |
| 7 Council | `[ ]` | Opus 5.5 design, Sonnet 5 build | Blocked on the design session (7.1). |
| 8 Beta | `[ ]` | Sonnet 5 | |

**Baseline at the time of writing (2026-09-21):** v0.99.24 · ~23,900 lines Python · ~2,600
lines JS · 104 test files, 1,488 tests, all green · 292 changelog entries · golden suite of 20
pages pinned to a frozen clock.

**Review baseline (2026-09-26):** working tree based on `4e834fd`, v0.99.73, including Codex work;
Windows/Python 3.12 full suite: **1,991 passed, 3 failed, 1 skipped**. Failures are the `memory`
and `agent_threads` goldens and `test_one_broken_job_does_not_stop_the_others`. Isolated probes
confirmed the review's concrete race, boundary and lifecycle failures. This is evidence to fix,
not an accepted release-failure allowance; see 2.21.
