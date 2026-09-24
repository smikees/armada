# ARMADA — code & design review (2026-09-07, pre-V1)

Snapshot at v0.45.2. Purpose: catch structural debt now, before the native-app + wizard + stress-test push, so we don't hit a forced refactor right before launch. Grouped by priority. Nothing here blocks tomorrow's feature work — but the **Do now** items get cheaper the sooner they're done and dangerous if deferred past V1.

## Facts (measured, not felt)
- `webui.py` = **3,464 lines**; `serve.py` = **1,219**; everything else ≤ ~290. Two files hold ~68% of the code.
- **19 inline JS blocks** live as triple-quoted strings inside `webui.py` (`_CHAT_JS`, `_DASH_JS`, `_LAYOUT_JS`, `_JOBCAL_JS`, …). No JS linting/formatting reaches them.
- **0 automated tests.** No `tests/` dir, no `test_*.py`.
- Icons maintained **twice**: 64 server-side `ICONS` entries + ~25 JS icon blobs (`MC_ACT`, `MC_MI`, `MC_DOTS`, `MC_STEP_ICONS`, `MC_GRIP`), in two different SVG syntaxes.
- `serve.py` has **39** broad `except`; request params (`agent`, `thread`, `job`, `slug`, avatar `aid`) go **directly** into `Path(realm)/"agents"/<param>/…` with no validation.

---

## Do now (this week, before/at V1)

**1. A thin test net around the non-UI core.** This is the biggest gap. The north-star is "migrate the live Cabinet and run it unattended" — that's an integration guarantee with no safety net today. We don't need UI tests; we need ~15–20 fast unit/integration tests over the pure logic that's most likely to break silently:
- `scheduler`: `parse_schedule`, `parse_days`, `cron_match`, `due_now` (incl. the Vixie DOM/DOW OR cases the Cabinet actually uses).
- `runner._cli_model` / `_resolve_model` (the model-mapping bug that hit prod).
- `webui._jobcal_events` (status resolution, missed vs scheduled, run matching).
- `reader.read` + `validate` on `Hand-realm` (a golden-file test: "export still parses, N agents / M jobs").
- `threads` truncate/append round-trip.
These would have caught the model-selector bug and will catch export/schedule regressions during the stress test. Cheap, high leverage.

**2. Harden the filesystem boundary (path traversal).** Every write endpoint does `Path(self.realm)/"agents"/str(body.get("agent"))/…`. A value like `../../…` escapes the realm. It's a local single-user app so the blast radius is small, but the fix is a one-liner utility used everywhere: `_safe_seg(x)` that rejects anything not matching `^[a-z0-9][a-z0-9_-]*$` (agent ids, slugs, job ids all already follow this), plus a `resolve().is_relative_to(realm_root)` assertion. Do it once now while the endpoints are fresh in our heads.

**3. Atomic JSON writes.** 24 `write_text`/`json.dump` calls persist `realm.json`, `agent.json`, `meta.json`, run reports. A crash or a race with the scheduler daemon mid-write corrupts realm state — the one thing that must never break. Wrap in one helper: write to `*.tmp` then `os.replace()`. ~10 lines, protects the whole realm.

**4. Decide the dashboard-persistence model before the wizard.** Layout, widget visibility, and thread widgets live in **per-browser localStorage**. That contradicts ARMADA's core premise (the realm is a portable, Git-versioned folder) and will behave differently inside a native webview. Decide now: is the dashboard realm state (`dashboard.json`, versioned, portable) or genuinely per-device? If realm state, moving it is far cheaper before the wizard starts generating dashboards than after.

## Soon (right after V1 features settle)

**5. Split `webui.py`.** It's a monolith. A low-risk split along seams that already exist: `webui/icons.py` (ICONS + `_icon`), `webui/components.py` (`_wid_header`, `_portrait`, `_mini_pill`, `_turn`…), `webui/pages/` (dashboard, agent, jobs, memory, settings), and pull the 19 JS blocks into `webui/static/*.js` served as files (they're already isolated strings; this also gets them JS-lintable and out of the Python diff noise). Do it as pure moves, one module at a time, no behavior change.

**6. Single source of truth for icons.** Generate the JS icon map from the server `ICONS` dict (emit a `<script>window.ICONS=…</script>` once) instead of hand-maintaining `MC_*` blobs in a second syntax. This is exactly what caused the invisible-dots and self-closing-`<circle/>` bugs — two hand-kept copies drift. One definition, both sides consume it.

**7. Route table instead of if/elif.** `do_GET`/`do_POST` are long chains. A `{path: method}` dict (or two) makes routing declarative, removes the risk of a missed `elif`, and is trivially unit-testable. Mechanical change.

**8. Centralize status vocabulary.** Run-status normalization exists in at least three places (`_jc_norm`, `reader`'s token/status handling, `_STATUS_COLOR`/`_dot`). One `status.py` with the canonical set {success, failed, warn, missed, scheduled, quiet} + color map, imported everywhere.

**9. CSRF/Origin check on POST.** A local server is reachable by *any* page in the browser (classic CSRF-to-localhost). One `if not self._same_origin(): 403` guard on mutating endpoints closes it. Low effort, real class of bug, worth it once we ship to other people.

## Later (post-launch hygiene)

**10. Concurrency.** `ThreadingHTTPServer` + the scheduler daemon both write realm JSON with no locking → lost updates (e.g., `meta.json` reorder vs a `unread` flip). A per-file lock or a small serialized write queue. Not urgent while it's one user + one browser tab, but note it before multi-tab/daemon overlap becomes common.

**11. Inline-style duplication.** `color-mix(in srgb,var(--color-text) 55%,transparent)` and friends are repeated hundreds of times inline. Promote the recurring ones to utility classes / CSS custom props (`--text-muted`, `--text-faint`) — smaller payloads, one place to tune, and it makes dark-mode real.

**12. Version single-sourcing.** Every release edits the version in 3 spots (`__init__.py`, `cli.py` description, `_CHANGELOG`). Read `__version__` in the CLI description and surface the changelog from one place, so they can't desync.

**13. Logging over silent excepts.** The 39 broad excepts swallow failures. At least `import logging` and log the exception in the `except` before returning the error JSON — invaluable during the stress test.

## Explicitly fine as-is (don't over-engineer)
- Zero-build, stdlib `http.server`, server-rendered HTML — right call for a local single-user app; keep it.
- No auth on localhost single-user — fine (the CSRF guard is the only web-exposure concern).
- Per-turn ephemeral step chips (not persisted) — acceptable product choice.
- The iframe approach for thread widgets — pragmatic and correct given the chat JS; the real fix is #6 + scoping JS by container, not removing iframes.

## Suggested order for tomorrow's 1–2 hour review slot
Do **#2, #3** immediately (tiny, protective, touch code we just wrote). Stand up **#1** as we build the stress test (write the scheduler + export tests first — they double as the parity-validation checklist for milestone 1). Make the **#4** call before the wizard work. Everything else is scheduled debt, not launch debt.
