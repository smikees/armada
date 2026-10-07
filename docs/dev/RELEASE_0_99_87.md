# ARMADA 0.99.87 verification

The reported 0.99.86 desktop and its scheduler were inspected through the authenticated
local endpoints: version 0.99.86, scheduler running, 11 scheduled jobs. The warning was
a startup race: the banner requested status as soon as HTML loaded, but autostart ran
only after browser readiness, and the next banner check waited a minute. Startup was
also a one-shot launch without continued supervision. A successful Popen response
did not prove a live scheduler lease; update health was acknowledged before autostart.

The desktop now starts one lightweight supervisor before navigating to its app page.
It considers every ready, unarchived realm rather than only the visible realm, starts
the windowless daemon automatically and checks real lease ownership. It polls every
two seconds during recovery and every fifteen seconds when settled, including in the
tray. Three recovery attempts with twenty-second grace intervals bound a failed cycle.
A live child is not duplicated; concurrent launch callers are serialized. An exhausted
cycle requires manual retry, while a late successful lease clears its warning. Exact
launch errors or the child exit code remain visible, with scheduler.log for diagnostics.

The status contract adds recovery state and action_required. Startup, recovery and
update shutdown do not display warnings. Recovery failure offers Retry, while explicitly
disabled autostart offers Start it. Legacy unmanaged status retains its visible warning.
The UI checks pending recovery quickly and does not hide recorded errors. Supervision
pauses while an update drains and stops before full quit can launch another child.

The browser marks desktop readiness separately from update acknowledgement. The latter
waits for real eligible scheduler leases; work admission remains paused meanwhile.
Readiness failure preserves the pending health marker so the independent restart monitor
can recover or roll back. The monitor also checks that acknowledgement before declaring
an update complete. Existing durable attempt records prevent uncertain work replay.

Regression coverage includes delayed startup, process exit and missing leases, multiple
realms, bounded launch failures with exact errors, concurrent launch calls, a live hung
child, update draining, explicit disable, setup/archive exclusions, state errors, manual
retry, quiet UI polling and both successful and failed update health acknowledgement.
Native tests use a real daemon with disabled upkeep and a never-due synthetic agent job;
provider probes, personal realms and outbound notifications are isolated. The packaged
upgrade gate exercises real scheduler startup and forced exit/recovery in hidden windows.

Enabling the real daemon exposed a native test isolation gap: Windows account discovery
intentionally ignores HOME overrides, so the GUI-only account override was insufficient
for its scheduler child to find the isolated update endpoint. That gate timed out and
blocked publication. The test now wraps the real daemon/bootstrap with the same explicit
account override as the GUI, preserving the production account guard. The isolated native
upgrade then passed all 63 checks; a regression test verifies that child boundary.

The existing unsigned-maintenance installer and unverified clean-Sandbox acceptance
boundaries remain. Exact publication evidence is retained under build/.

## Published evidence

- Source commit: `a10869231311c2a874468d77faa117b1dd0af1ba`.
- Isolated full suite: **3,204 passed, 5 skipped in 461.09 seconds**.
- Targeted scheduler, restart, installer, updater and overview regressions:
  **141 passed in 7.92 seconds**.
- [Windows CI for the published source](https://github.com/smikees/armada/actions/runs/37625889613): passed.
- Native launcher recovery: all **5 interruption points** passed.
- Native WebView2 session gate: **16 checks** passed.
- Packaged 0.99.86 to 0.99.87 upgrade: **63 checks** passed, including actual
  scheduler leases in two realms, quiet recovery after forced child exit, health
  acknowledgement, authenticated navigation and complete test-process cleanup.
- Installer SHA-256:
  `fd05328b4e7c5edc2d2c67c80c9c9a7601c6c7c55acbb1e05f02c940eae6cdad`.
- Update archive SHA-256:
  `109999f16db0eb5550a62c80679b151f6b225c9732c97bb95f6c35b43845c132`.
- [Published release](https://github.com/smikees/armada/releases/tag/v0.99.87)
  includes the installer, update archive, signed manifest and manifest signature.
- [Public website](https://armada.stamih.com/) returned HTTP 200 with the 0.99.87
  version, installer URL and release-notes link after its authorized FTPS update.

The installed user desktop was not restarted merely to publish this release.
The installer remains an unsigned maintenance beta; clean Windows Sandbox
installer acceptance remains unverified, as recorded by the release evidence.
