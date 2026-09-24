# `armada/addons.py`

Add-ons: the extension surface (Phase 2, 2.7 — ADR-002's homework). Designed and stubbed; nothing
in the app reads it yet.

ADR-002 says Alexander-the-developer, when it comes, changes a user's ARMADA only by writing into a
defined surface — never by patching the app — so the user keeps running the official build plus
their own files, updates keep applying, and undoing a change is deleting a folder. This module is
that surface's contract and loader. The full contract, with examples, is docs/dev/EXTENSION_POINTS.md.

Why "add-on" and not "plugin": the app already has four capability kinds — connectors, extensions,
skills, plugins — and two of them are exactly the words this would otherwise use. A third meaning
of "plugin" on the Capabilities page would be a bug report waiting to happen.

**An add-on is data, never code.** A folder holding one `addon.json`. It can contribute five kinds
of thing, each validated against a closed schema and rendered, when something renders it, by the
app's own code:

  widgets        dashboard cards — static markdown, or a list of links
  filters        saved views over a list (the Jobs list, the Capabilities page)
  themes         a named pair of brand colours (the same shape vtheme.THEMES uses)
  job_templates  a pre-filled *agent* job — never a command job, which would be code by the back door
  layouts        a dashboard arrangement (the same shape dashboard.json uses)

**Where they live.** `<realm>/addons/<id>/addon.json` travels with the realm (export, Git, another
machine); `~/.armada/addons/<id>/addon.json` is this install's, for every realm. Themes are app-scope
only, because the chosen theme is a per-install setting (appconfig). The same add-on id in both
places: the realm's copy wins, and the app's is reported as shadowed.

**Fail safe, always.** `load()` never raises. A malformed add-on is skipped whole; a malformed
contribution inside a good add-on is skipped alone; either way the reason goes into
`Registry.problems` (and the log), which is what a Settings page — or Alexander — shows the user.
Unknown keys are ignored so an add-on written for a later contract still loads what it can; an
add-on that declares a NEWER contract than this build knows is skipped rather than half-read.

### `app_dir()`

—

### `realm_dir(realm_root)`

—

### class `Registry`

Everything loaded, plus why anything wasn't. Contributions carry a qualified id, `<addon-id>/<id>`, so two add-ons can never collide.

- `Registry.get(self, kind: str)` — —
- `Registry.find(self, kind: str, qid: str)` — —

### `_text(v, limit=MAX_LABEL)`

—

### `_widget(d: dict)`

—

### `_filter(d: dict)`

—

### `_theme(d: dict)`

—

### `_job_template(d: dict)`

—

### `_widget_ref_ok(wid)`

—

### `_layout(d: dict)`

—

### `_read_manifest(folder: Path)`

(manifest dict, None) or (None, reason).

### `_load_one(folder: Path, scope: str, reg: Registry)`

—

### `_scan(root: Path, scope: str, reg: Registry)`

—

### `load(realm_root=None)`

Load the app's add-ons, then the realm's (which win on an id clash). Never raises.
