# ADR-010 — The internals are renamed `armada` too

**Status:** Accepted · 2026-09-24 · decided by Mihai · supersedes ADR-008's internals policy
(ADR-008's decision on the product name stands)

## Context

ADR-008 kept the name ARMADA and recommended leaving the internal identifiers as `matcap` (the
package, the CLI verb, the `~/.matcap` folder) for the beta, on the grounds that renaming them was
work with no visible benefit yet.

Three things changed that calculation on the same day:

- **The repo goes public** (launch plan 5.4) as a fresh single-commit history. A rename done now
  never appears in public history; done later, it's a large diff everyone reading the code sees,
  and the name mismatch is the first thing a reader of the source meets.
- **The installer bakes the names in** (ADR-009): install paths, the logon entry
  (`pythonw -m <package> schedule`), the updater's swap folder, the data folder. After beta users
  install, every rename needs a migration on every machine, forever.
- **Beta users would see the old name**: a `.matcap` folder in their home, `matcap.log`, "matcap"
  processes in Task Manager.

Nobody but the owner has ARMADA installed yet. This is the cheapest the rename will ever be.

## Decision

Rename everything to `armada` in one release (v0.99.56), before the first public push and the
first installer build:

- the Python package `matcap` → `armada` (`python -m armada …`, the `armada` CLI verb);
- the per-machine folder `~/.matcap` → `~/.armada`, through one function, `util.data_dir()`. It
  stays a dot-folder in the home directory, like Claude Code's `~/.claude`, rather than
  `%APPDATA%`: one path on every platform, and the one the people who use ARMADA already look in;
- environment variables `MATCAP_*` → `ARMADA_*`, loggers `matcap.*` → `armada.*`, the log file
  `matcap.log` → `armada.log`, the CSS dark-mode class, the launchers (`ARMADA.vbs`, `armada.cmd`);
- the Windows app ID `Anthropic.ARMADA.Cockpit` → `Stamih.ARMADA.App` (ARMADA isn't Anthropic's).

Historical records keep the words they were written in: the ADRs, `docs/dev/DEV_LOG.md`, and the
in-app changelog's past entries. The development folder on the owner's machine (`…\MATCAP`) is
local only and isn't renamed here.

## Consequences

- **Nothing set up under the old name is lost.** `util.data_dir()` moves `~/.matcap` to
  `~/.armada` the first time it runs (a copy if the rename is refused). Realms go through
  realm-format migration **1 → 2** (`realmformat._m1_to_2`): command jobs calling `-m matcap` now
  call `-m armada`, the realm cache `.matcap/` becomes `.armada/`, and the environment block agents
  see says ARMADA.
- Anything outside the repo that starts the old module has to change with it. On the owner's
  machine that was `D:\Work\Hand\ops\resilience\cabinet-up.ps1`, updated the same day.
- `realmformat.CURRENT` is 2. An older build that opens a migrated realm sees a newer format and
  leaves it alone (2.8's rule), so the only way back is the old history, not an old build.
