# ADR-008 — The name is ARMADA

**Status:** Accepted · 2026-09-24 · decided by Mihai (the name). The internal-identifier policy below
is a recommendation awaiting his confirmation.

## Context

0.8 time-boxed the naming question to 2026-09-22 and said `brand.py` is the only file a new name
would touch. The app has shipped as ARMADA throughout September (v0.99.34 brought the mark and
wordmark; v0.99.35 the window/taskbar icon). The question was whether the beta installer should
carry a different name. Separately, the code still uses the project's working name, **matcap**:
the Python package, the `matcap` CLI verb, `~/.matcap/` for machine-local state, `MATCAP.vbs` /
`matcap.cmd` launchers, and the `.matcap-dark` CSS class.

## Decision

**The product is ARMADA.** `brand.py` already says so; nothing changes there.

**Recommended — internal identifiers stay `matcap` for the beta; user-facing surfaces say
ARMADA.** Concretely:

- *Stays `matcap`* (invisible, or visible only to someone reading code or logs): the Python
  package, module names, `python -m matcap`, the `.matcap-dark` class, `~/.matcap/` (moving a
  data folder under an installed base is a migration with nothing to gain for five users).
- *Says ARMADA* (what a beta user sees): the installer, install folder, Start-menu and desktop
  entries, the launcher filenames the installer lays down, window title, About, docs, error
  dialogs. Phase 5's installer (5.2) is where the launcher `.vbs`/`.cmd` names change; the repo's
  own dev launchers can keep theirs.

## Consequences

- 5.1's prerequisite is met: platform (ADR-006) and name are both settled. The installer is
  unblocked.
- User docs (3.3) say ARMADA and never tell a user to type `matcap` except where a CLI command is
  genuinely the instruction; the developer docs explain the split once.
- Renaming the internals remains possible later as its own step (a data-folder migration plus an
  alias for the old CLI verb); this ADR doesn't foreclose it, it declines to do it before the beta.
