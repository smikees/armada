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

The existing unsigned-maintenance installer and unverified clean-Sandbox acceptance
boundaries remain. Exact publication evidence is retained under build/.
