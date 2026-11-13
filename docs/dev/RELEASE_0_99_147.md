# v0.99.147 - reliable updates and visible background work

Published on 13 November 2026 from `4722d3849ab63fedd382ed0d718297aa99da95cb`.
The [GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.147)
and [website](https://armada.stamih.com/) both offer this version.

Update-blocked chat sends retain their text and attachments in main and detached
threads. Update preparation drains queued inbox waits without interrupting running
work. Owned live-run markers distinguish active work from abandoned state without
expiring healthy long runs. Activity shows queued agents and system work, while
all calendar views have a live System jobs section including Inbox and Telegram
processing. See [the implementation and regression contract](UPDATE_ACTIVITY.md).

The first release candidate was withheld after Python 3.14.10 CI reproduced a
concurrent snapshot-write failure: Windows `Path.resolve()` retained its extended
namespace prefix for the destination while the base used ordinary drive syntax.
The containment check mistook equivalent paths for an escape. Namespace-only
comparison now handles drive and UNC forms while preserving traversal and reparse
rejection. Twelve deterministic cases and 300 real concurrent snapshot repetitions
cover the fix; the focused snapshot/capture suite passed 77 tests. This resolves
the snapshot path-resolution limitation recorded in v0.99.146.

The final publisher passed **4,578 tests with 6 skips** in **930.01 seconds**.
[Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/43495505651)
was triggered by the final source push and passed both Python jobs and relay:
**4,580 tests with 4 skips** each, in 856.54 seconds on Python 3.14.10 and
926.29 seconds on current Python 3.14. No failed check was waived.

Clean-source stabilization passed in **382.39 seconds**, including faults, soak,
history, page work, three **163-check** native thread/window cycles and **98 owner
workflows**. Evidence: `build/stabilization-0.99.147-final.json` and
`build/stabilization-20261113-204747-291550`.

The freshly staged runtime separately passed all **98 owner-workflow checks**,
including system-job geometry, every calendar view, queued/running/idle status
changes, subscription bars, Activity refresh and scaled dark mode. Evidence:
`build/owner-workflows-bundled-0.99.147-final.json`. The feature's dedicated native
calendar/layout probe also passed 52 checks before release preparation. Calendar
and packaged presentation-recovery captures were reviewed in light and dark mode.

Installer gates passed launcher recovery at five interruption points, DLL
isolation, 16 WebView2 session checks, 69 tray checks, 70 checks for each of three
restart scenarios and 87 presentation-recovery checks. The signed upgrade from
v0.99.146 to v0.99.147 passed **72 checks** with the normal close-to-tray setting.

Public verification checked the Ed25519 signature, tag/manifest commit, ZIP hash,
all **500 packaged files**, installer hash and website links. The **23,450,389-byte**
installer has SHA-256
`d5c023eb338caaac620eb8d1447e757dc4543e418fbdc670fe85894f8e4ef4a2`;
the update ZIP has SHA-256
`e5633afcb89319db0d2cb0317b825700622bde5c07a0abf642005e09b502d93b`.
Evidence: `build/release-evidence-0.99.147.json`, `build/upgrade-0.99.147.json`
and `build/public-release-0.99.147.json`.

Provider preference selection was reviewed: only connected providers and models
reported available may be selected; an unavailable preference falls back to the
provider default. This release does not change provider preferences or runtime.

This continues the owner-authorized unsigned maintenance beta distribution.
Update assets are Ed25519-signed. Trusted Windows publisher signing and
clean-machine Sandbox acceptance remain unverified. Hardware KVM/mixed-DPI removal
remains an earlier documented limitation. The owner app was not installed or
restarted; live realms, jobs, keys and provider billing settings were not changed.
The temporary Windows test account, profile and tasks remain untouched.
