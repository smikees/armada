# Conventions

Short rules, each with its reason. The reasons are the point: a rule you understand you can apply
to a case this page doesn't mention.

## Writing

- **Comments, docstrings, commit messages and changelog entries explain *why*.** The code says
  what. This codebase's docstrings are unusually long because each one records a bug or a decision
  that would otherwise be re-made; keep that up, and keep them true when the code changes.
- **Changelog entries are for the owner** (RELEASING.md §2). Commit messages are for the next
  developer.
- **One name per concept** (DESIGN_SYSTEM §9). In code as in copy: "add-on" is ARMADA's extension
  unit, "plugin" is a Claude Code plugin — never swap them.

## Code

- **The realm folder is the truth** (ARCHITECTURE 4.1). New state goes in the realm, in JSON or
  Markdown, described in SCHEMA.md — unless it's genuinely about this machine (`~/.armada/`).
- **A non-additive change to a realm file is a migration** (SCHEMA.md → Format versioning).
- **Read-modify-write of a shared file holds `util.file_lock`; every write is atomic**
  (`util.write_json_atomic` / `write_text_atomic`).
- **A broad `except` logs before it falls back** — `util.swallowed(log, "<func>: <fallback>")`,
  or `log.debug(..., exc_info=True)` where failure is the expected path. A test enforces it.
- **Rendering never waits on the network.** Fetch from the page (`/api/…`) or read a cache a
  system job keeps fresh.
- **Time comes from `clock.now()` / `clock.today()`**, so the goldens can freeze it.
- **Anything that talks to Claude goes through `engine/`**; don't import `engine.claude`
  elsewhere, don't write a new `engine="claude"` literal — pass `engine` down
  (ENGINE_SEAM_AUDIT.md).
- **Who may use a capability is asked of `capabilities.py`**, never re-derived.

## Web UI

- **JavaScript lives in `webui/static/js/`**, loaded with `assets.js(name)`; Python emits data
  shims only.
- **Escaping.** Text into HTML: `E(x)`. A value inside an event attribute's JavaScript:
  `onclick="f({_J(x)})"` — never `'{E(x)}'` (a test enforces it). In JS, text into `innerHTML`
  goes through an escaper that handles quotes, or use `textContent`.
- **Components are classes; tokens, never values** (DESIGN_SYSTEM.md, DESIGN_TOKENS.md). A colour
  token built from another `var()` is declared on `:root,.armada-dark`.
- **Dialogs** use `.mc-modal-ov` / `.mc-modal-box`; confirmations use `mcConfirm` / `mcAlert`,
  never the browser's `confirm` / `alert`.

## Work

- **One ticket, one commit.** Small commits are what make a golden diff readable.
- **Record decisions where the next session will look:** a step's "done" note in LAUNCH_PLAN.md,
  an ADR for anything that settles a question, THREAT_MODEL.md for anything security-relevant.
- **A deviation from the plan is fine; an unexplained one isn't.** Say what you did differently
  and why, in the plan's done-note and the commit.
