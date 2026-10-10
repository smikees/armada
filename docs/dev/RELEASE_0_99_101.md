# 0.99.101 verification

Polish after the owner reviewed 0.99.100 ([plan follow-up](CAPABILITIES_UPGRADE.md#099101-follow-up)).
ARMADA still never signs in or out for the owner and never copies credentials between engines.

## Behavior and boundaries

- **One place to add.** Add a capability searches the engine connectors (Google Drive, Gmail, Google
  Calendar, Slack, GitHub, Notion) together with the MCP registry, plugin marketplaces and skills. Engine
  connector cards lead the results and offer Add for Claude / Add for Codex; Gemini is shown as not
  available. A card shows which engines already have the service (including a `claude.ai <service>`
  import). Works with = Any engine excludes per-engine services; Claude or Codex includes them.
- **Other ways to add**, below the results: an MCP server by its https address (one row, any engine),
  Bring in Claude's connectors (the former refresh/import, `/api/refresh-connectors`), Bring a link, and
  links to Claude's directory and ChatGPT apps. Neither provider publishes a searchable directory.
- The User tab's Add a connector button, refresh icon and the multi-mode dialog are removed. Link existing
  connection remains in a row's Setup details, as a link-only dialog for that row's engine.
- A connector imported from Claude is Claude only unless another engine has a binding of its own.
- Connect on an unbound "<service> · Claude" row links Claude's `claude.ai <service>` registration when it
  exists, otherwise opens Claude's connector settings as before.
- Adding a service twice for one engine, or a second row for the same MCP address, is refused.
- New Codex rows are "<service> · Codex" (realm migration v4 also uses this name for future splits).
  Mixing errors name the engine to add the service for.
- User tab filters: search on line 1; the engine switcher then agent, type, source and risk on line 2.
  Add a capability uses the same layout.
- Settings → App → Fonts: no trial note; each option, and the closed field, is set in its own face.

## Checks

- `tests/test_capreach.py`: per-engine duplicates and address duplicates refused; a Claude import counts
  as added for Claude; engine connector cards with per-engine Add, Added and not-available states, and the
  Works with filter; updated names and messages.
- `tests/test_cap_ui_cleanup.py`: the User tab has no add or import controls; the Add a capability tab has
  the address form and Claude import.
- `tests/test_codex_native_apps.py`: the engine-centric mixing message.
- Node harnesses for connector controls, badges and settings dropdowns pass with the reduced dialog
  script and the font preview.
- Goldens regenerated after the version and changelog; diffs reviewed.
- Visual review (headless Chrome, rendered from a COPY of the owner's realm): User tab filters, Add a
  capability results for "mail" and "drive", the Other ways to add section, and the open Fonts list.

## Results

Full Windows suite with the release changes: one failure on the first run (the settings dropdown
harness passes options without a `style`), fixed with optional chaining in `fdrop.js` and re-run green.
Publication evidence is recorded below when the maintenance publisher completes.
