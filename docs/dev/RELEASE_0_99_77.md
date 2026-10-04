# ARMADA 0.99.77 release verification

Follow-up to the owner's 0.99.76 report: Gemini still denied the approved realm
folder, and a terminal still appeared briefly while idle. Published as the next maintenance beta; compatible installed copies can update in-app.

## Gemini: reproduced and corrected

The runner supplies approved realm/workspace roots to every adapter. Gemini removed
an approved root when it was an ancestor of its cwd. Since cwd is agents/<id>, this
removed the realm itself. A grant on the agent directory does not grant its parent.
The adapter now retains every existing root supplied by ExecutionPolicy, deduplicated,
and uses the same roots for project permission rules, --add-dir and task context.
No global permissions, wildcard filesystem rules or skip-permissions flags are added.

Using the real installed Google CLI and an isolated fixture whose name contains a
space and apostrophe, the exact realm-listing request failed before and succeeded
after the fix. A neighboring unapproved test directory remains denied after the fix.
This is a policy-mapping error, independent of the user's folder name.

## Brief Windows terminal: additional paths addressed

- Environment refresh called Python platform helpers. Forcing WMI unavailable
  reproduced a subprocess call to `ver`, with neither creation flags nor startup
  window settings. Native Windows version/registry/hostname APIs now replace these
  probes; a regression test prohibits any subprocess during system-memory refresh.
- The stream/RPC supervisor now supplies SW_HIDE as well as CREATE_NO_WINDOW,
  preserving suspended startup and Job Object assignment.
- Scheduler startup no longer combines DETACHED_PROCESS with CREATE_NO_WINDOW
  (Windows ignores the latter in that combination). Scheduler cleanup and desktop
  notification helpers also use the shared hidden-window policy.
- Real local provider status/quota checks were watched for newly visible console
  windows; none appeared. The specific process flashing on the other machine is
  not identified. These changes close verified gaps; remote confirmation remains
  necessary before claiming that every reported popup is resolved.

## Verification

- Focused Gemini, background, process lifecycle and system-memory checks: 121 passed.
- Scheduler-service and notification checks: 46 passed.
- Full isolated release-gate suite: 3,065 passed, five skipped.
- Exact-commit Windows CI passed on Python 3.12.10 and current 3.12; PHP relay passed.
  https://github.com/smikees/armada/actions/runs/37211097161
- Packaged imports/startup, timezone support and all five launcher recovery checks passed.
- Public update manifest signature, runtime compatibility, ZIP size/hash and installer hash verified.
- Source commit: `271bc57e469f0bfb3d5f93dc48cedd7c9b94fddd`.
- Installer SHA-256: `8bc111f5d2a3ae874579037a1cdb188798081dcb520e7e173f3a90d0729fe650`.
- No live user realm, scheduled job or global CLI policy was modified.

## Distribution

The runtime is unchanged from 0.99.75/0.99.76, permitting a signed package update.
The Windows installer remains an unsigned beta under the existing owner-requested
no-fee distribution. Trusted publisher signing and clean-Sandbox GUI acceptance are
still unverified. This follow-up does not fix Application Control error 4551 or the
previous Sandbox WebView2 prerequisite failure. Standard release gates and launch
acceptance checkboxes are unchanged; any manual distribution is recorded separately.

Published manually as a continuation of the requested unsigned maintenance beta,
with signing and clean-Sandbox limitations retained in the release notes. The
standard public gate was not represented as passed. The later metadata commit
changes documentation and website links only. Landing-page-only FTPS publication
retains a backup and does not touch the report relay.
