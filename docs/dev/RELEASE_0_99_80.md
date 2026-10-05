# ARMADA 0.99.80 verification

## Update handover

The previous update path could close the app without confirming that a successor or scheduler
returned. A leftover legacy process could retain its installation lease, preventing replacement.
Before shutdown, the desktop now starts and receives acknowledgement from a standalone monitor
copied outside the replaceable package. After the owner exits, the monitor launches the stable
bootstrap through Explorer and checks the expected version, rendered desktop and scheduler when
autostart is required. The monitor holds no installation lease and logs startup failures.

Preflight reads kernel-held leases and identifies blocking older instances by PID. It never
terminates active work. Postpone update clears the admission pause, retains the staged package and
starts the scheduler if needed. Launch/authentication recovery allows only the public bootstrap
GET across origins; authenticated mutations and realm pages remain protected.

## Limits and Settings

The current live Claude usage API returned a fresh reading despite an older screenshot showing
last-reading fallback. Browser limits caches are now scoped to each server launch. Fresh results
cache for five minutes, failed/stale results retry after 30 seconds. Expired Claude usage tokens
request the enabled CLI keepalive with account-wide renewal locking and cooldown; disabled or
uncertain jobs are not replayed. ARMADA does not rotate provider credentials itself. Settings tabs
are App, Realm, User; App is initially selected; links and the remembered tab can select another.

## Verification

Focused checks: 89 passed, including real child-process bootstrap handover, native lease release,
expected-version/desktop/scheduler readiness, failed monitor launch, per-launch browser cache,
stale retry intervals and system-job admission. Full-suite and published asset results are
recorded below after release verification.

## Distribution boundaries

The stable bootstrap and runtime are unchanged, preserving package updates from 0.99.75+.
The first upgrade from an older version still uses that version's restart path; a full tray quit
and manual launch can be needed once. The monitored path applies to subsequent updates.
This is an owner-authorized unsigned maintenance beta. Authenticode and clean-Sandbox GUI
acceptance remain unverified; Windows Application Control error 4551 is not resolved. Existing
public acceptance gates remain open. No live realm, scheduled job or running desktop was changed
to publish this release.
