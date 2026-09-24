# Extension points — the add-on contract

*Phase 2, step 2.7 — ADR-002's homework. Contract v1, written 2026-09-24. Loader: `armada/addons.py`.
Tests: `tests/test_addons.py`. **Designed and stubbed: nothing in the app reads add-ons yet.***

ADR-002 decided that when Alexander-the-developer arrives (DEFERRED D.1), it changes a user's ARMADA
only by writing into a defined surface — never by patching the app. The user keeps running the
official build plus their own files; updates keep applying; undoing a change is deleting a folder.
This document is that surface. It is written for three readers: whoever builds the first consumer,
Alexander (whose prompt will point here), and a person writing an add-on by hand.

## The shape of it

**An add-on is a folder with one file, `addon.json`. It is data, never code.** It can contribute
five kinds of thing. Each is validated against a closed schema, and — when something renders it —
rendered by the app's own code. No add-on ships HTML, CSS, JavaScript, Python or a shell command.

| Kind | What it is | Consumer, when built | Scope |
|---|---|---|---|
| `widgets` | a dashboard card: static markdown, or a list of links | Overview dashboard + widget picker | app or realm |
| `filters` | a saved view over a list | Jobs list, Capabilities page | app or realm |
| `themes` | a named pair of brand colours | Settings → Appearance (`vtheme`) | **app only** |
| `job_templates` | a pre-filled *agent* job | New-job form | app or realm |
| `layouts` | a dashboard arrangement | Overview dashboard | app or realm |

**Why "add-on" and not "plugin".** The app already has four capability kinds — connectors,
extensions, skills, plugins — and two of them are the words this would otherwise use. A plugin on
the Capabilities page is a Claude Code plugin; an add-on is ARMADA's own. Keep the words apart.

## Where add-ons live

```
<realm>/addons/<id>/addon.json        travels with the realm — export, Git, another machine
~/.armada/addons/<id>/addon.json      this install's, for every realm
```

- **The folder name is the add-on's id**, and the loader refuses a mismatch. That is what makes
  "undo is deleting the folder" true without a registry to keep in step.
- **Themes are app-scope only**, because the chosen theme is a per-install setting
  (`~/.armada/config.json`), not a realm's. A realm add-on that offers one has it skipped, with a
  reason; the rest of the add-on loads.
- **Same id in both places: the realm's wins**, and the app's is reported as shadowed.
- **Contributions are addressed by qualified id**, `<addon-id>/<contribution-id>`, so two add-ons
  can never collide. A layout refers to another add-on's widget as `addon:<addon-id>/<widget-id>`.
- **Symlinked folders are not loaded.** An add-on is something you (or Alexander) put there, not a
  pointer to somewhere else on the disk.

## The manifest

<!-- example:addon.json -->
```json
{
  "armada_addon": 1,
  "id": "morning-desk",
  "name": "Morning desk",
  "version": "1.0.0",
  "description": "A calmer Overview for the first hour of the day.",
  "provides": {
    "widgets": [
      {"id": "note", "title": "Before you start", "kind": "markdown",
       "body": "**Three things.** Check the red squares, read the inbox, then decide.", "default_span": 8},
      {"id": "links", "title": "Daily links", "kind": "links",
       "links": [{"label": "Jobs", "url": "/jobs"}, {"label": "Status page", "url": "https://status.anthropic.com"}]}
    ],
    "filters": [
      {"id": "needs-attention", "label": "Needs attention", "applies_to": "jobs",
       "match": {"status": ["failed", "warning", "none"]}},
      {"id": "connectors", "label": "Connectors only", "applies_to": "capabilities",
       "match": {"kind": ["connectors"]}}
    ],
    "themes": [
      {"id": "dawn", "name": "Dawn", "accent": "#7a3e9d", "accent2": "#e39b3b"}
    ],
    "job_templates": [
      {"id": "weekly-review", "name": "Weekly review", "summary": "Monday 9am recap of last week",
       "prompt": "Summarise what the realm did last week: jobs run, what failed and why, and what needs a decision.",
       "cron": "0 9 * * 1", "allow_tools": true}
    ],
    "layouts": [
      {"id": "focus", "name": "Focus", "order": ["addon:morning-desk/note", "register", "jobcal"],
       "spans": {"addon:morning-desk/note": 8, "register": 12, "jobcal": 20},
       "heights": {"register": 420}}
    ]
  }
}
```

That example is loaded by the test suite, so it can't drift from what the loader accepts.

| Field | Rule |
|---|---|
| `armada_addon` | integer contract version. This build understands **1**. A higher number is skipped whole ("update ARMADA") rather than half-read. |
| `id` | `[a-z0-9][a-z0-9-]{0,63}`, equal to the folder name. |
| `name`, `version`, `description` | optional display fields (≤120, free-form, ≤500 chars). |
| `provides` | object; keys are the five kinds, each a list of ≤ 50 contributions. Unknown kinds are reported and ignored. |
| every contribution | an object with an `id` (same pattern), unique within its kind in this add-on. Unknown keys are ignored — forward compatibility. |

The whole file is capped at **256 KB**.

## The five kinds

### widgets
| Field | Rule |
|---|---|
| `title` | 1–120 chars |
| `kind` | `"markdown"` or `"links"` |
| `body` | markdown widgets: 1–20,000 chars, rendered by the app's own escaped markdown (`webui/_base.py:_md` — raw HTML never passes) |
| `links` | links widgets: 1–50 `{label, url}`; `url` is `http(s)://…` or app-local `/…` (not `//…`, not `javascript:`) |
| `default_span` | optional, integer 4–20 (the dashboard's 20-column grid) |

*Not in v1, on purpose:* widgets that query realm data. The natural next kind is `"stat"` naming a
source from a **closed** list the app implements (`jobs.failed_today`, `goals.open`, …) — the
add-on picks, the app computes. Anything an add-on could express as a query language would be code.

### filters
| Field | Rule |
|---|---|
| `label` | 1–120 chars |
| `applies_to` | `"jobs"` or `"capabilities"` |
| `match` for jobs | any of `status` ⊆ {success, running, warning, failed, none}, `cadence` ⊆ {daily, weekly, monthly, quarterly, other}, `agent` (list of agent ids), `text` (substring) |
| `match` for capabilities | any of `kind` ⊆ {connectors, extensions, skills, plugins}, `text` |

The vocabularies are the ones the Jobs list and Capabilities page already filter by
(`webui/schedfmt.py`, `capabilities.KINDS`); a test fails if they drift. Keys within a filter are
ANDed; values within a key are ORed — the consumer must implement exactly that.

### themes
`name` (1–120), `accent` and `accent2` as `#rrggbb` — the same shape as `vtheme.THEMES`, from which
`vtheme._scale` derives the full token ramp. Fonts are not part of v1.

### job_templates
| Field | Rule |
|---|---|
| `name` | 1–120 chars |
| `kind` | optional; if present must be `"agent"`. **Command jobs are refused**: a command job runs a shell command on the owner's machine on a schedule, and an add-on that could ship one would be code by the back door. |
| `prompt` | 1–20,000 chars |
| `cron` | optional 5-field cron (`scheduler.is_cron`); absent = on demand |
| `summary` | optional, ≤300 chars |
| `allow_tools` | optional boolean |

A template fills in the New-job form; it never creates a job by itself. The owner picks the agent
and saves — so a template can't schedule anything the owner didn't look at.

### layouts
`name`, `order` (1–50 widget ids, no repeats), optional `spans` (4–20), `heights` (120–3000 px) and
`single` (booleans), each keyed only by widgets in `order`. Widget ids are the built-ins
(`register`, `usage`, `jobcal`) or `addon:<addon-id>/<widget-id>`. **Thread widgets are refused**:
they name a specific agent's thread, which belongs to one realm's `dashboard.json`, not a portable
layout. The clamps are the ones `routes/dashboard.py:_save_dashboard` applies; a test fails if they
drift. Applying a layout means writing those fields into the realm's `dashboard.json`, keeping its
thread widgets.

## Failing safe

`addons.load(realm_root=None)` returns a `Registry` — `addons`, `items[kind]`, `problems` — and
never raises.

- A malformed **add-on** (bad JSON, not an object, missing or newer contract, bad or mismatched id,
  oversized, symlinked, no manifest) is skipped whole.
- A malformed **contribution** is skipped alone; its neighbours and the rest of the add-on load.
- A bug in the loader itself costs the one add-on it was reading, not the app.
- Every skip lands in `Registry.problems` as `{scope, addon, where, reason}` — a sentence meant for
  the owner — and in the log at WARNING. The first consumer should surface `problems` somewhere
  the owner will see it (Settings, or Alexander's context); a silent skip is a support ticket.

## What the first consumer must do (and what "done" means for D.1)

ADR-002 set the test of this design: **a built-in feature uses the surface before Alexander does**.
Nothing does yet. The cheapest honest first consumer is themes — move `vtheme.THEMES`' built-in
alternates into a bundled app-scope add-on and have the Appearance picker list `load().get("themes")`
alongside the default. Then, for each kind as it gets a consumer:

1. Call `addons.load(realm_root)` off the render hot path, or memoise it on the add-on folders'
   mtimes — it reads files.
2. Render contributions with the app's existing code for that surface (the widget chrome,
   `_md`, the dashboard grid, the New-job form). Never interpolate add-on strings unescaped.
3. Show where each came from (`scope`, `addon`) — "from Morning desk" — so a user can find the
   folder to delete.
4. Bump `CONTRACT` only for a change an older loader would misread; additive fields don't need it.
   Record each bump here with what changed.

## Changelog of the contract

| Contract | Date | Change |
|---|---|---|
| 1 | 2026-09-24 | First version: widgets (markdown, links), filters (jobs, capabilities), themes, job templates (agent only), layouts. |
