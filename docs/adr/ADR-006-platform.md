# ADR-006 — Windows for the beta; macOS in scope after

**Status:** Accepted · 2026-09-21 · decided by Mihai

## Context

ARMADA has only ever run on Windows. That is visible in the code: `.vbs` launchers, a
`cabinet-up.ps1` resilience script, `CREATE_NO_WINDOW` flags around the Claude CLI subprocess,
the Claude Desktop extension path pattern (`Claude Extensions\<bundle-id>`), and `pythonw.exe`
for a console-less process. None of it is wrong; all of it is one platform's shape.

macOS is a real target — Claude Desktop and Claude Code both run there, and the kind of user
ARMADA is for is well represented on it. But a second platform before the first has shipped
doubles the installer work, the clean-machine testing and the support surface, for a beta whose
job is to find out what breaks for other people at all.

## Decision

**The beta is Windows-only.** The installer, the scheduler-as-a-service work, the clean-machine
test and the support expectations in Phase 5 target Windows and nothing else.

**macOS is in scope after the beta** (DEFERRED D.4). It is not "if"; it is "after".

## Consequences

Because macOS is coming, new code from here on must not add Windows-only shortcuts that will
have to be undone:

- Paths go through `pathlib`, never string concatenation with backslashes. (Largely already
  true.)
- Anything platform-specific — process spawning, launchers, the extension-directory pattern,
  where app data lives — sits behind one small module (`matcap/platform.py` or the existing
  `approot.py`), so the macOS port is one file's worth of branches, not a grep across the tree.
- The installer (5.2) is built so that a second installer can share its steps: dependency
  checks, first-run detection, the update path are platform-neutral; only packaging differs.
- The `Claude Extensions` regex already accepts either slash direction; on macOS the directory
  lives under `~/Library/Application Support/Claude/`. Note it now, port it then.
- The scheduler service (5.5) will need a launchd equivalent of whatever Windows mechanism is
  chosen. Choosing something with an obvious macOS counterpart (a per-user startup entry
  rather than a Windows Service) keeps D.4 small.
- We give up, for the beta: Mac users, and any beta feedback from them.
