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
stale retry intervals and system-job admission. Final focused lifecycle/reference checks: 138 passed.

Full isolated suite on the final source: **3,105 passed, five skipped**. Packaged startup and
all five native interrupted-update recovery checks passed. A separate probe using the actual
branded embedded runtime verified copied-helper resolution despite its isolated module path.
Local manifest signature, source commit, ZIP size/hash and runtime compatibility were verified.
Release-owned model preferences and the live-catalogue/provider-default fallback were reviewed;
existing explicit model choices remain unchanged.

[Exact-commit Windows/PHP CI](https://github.com/smikees/armada/actions/runs/37300845363)
passed on Python 3.12.10 and current 3.12, plus the PHP relay checks. The public latest-release
manifest signature, source commit, ZIP size/hash and installer hash were verified after publication.

## Distribution boundaries

The stable bootstrap and runtime are unchanged, preserving package updates from 0.99.75+.
The first upgrade from an older version still uses that version's restart path; a full tray quit
and manual launch can be needed once. The monitored path applies to subsequent updates.
This is an owner-authorized unsigned maintenance beta. Authenticode and clean-Sandbox GUI
acceptance remain unverified; Windows Application Control error 4551 is not resolved. Existing
public acceptance gates remain open. No live realm, scheduled job or running desktop was changed
to publish this release.

## Published metadata

Release: [v0.99.80](https://github.com/smikees/armada/releases/tag/v0.99.80).
Installer and update source: `f13ea4bbde4b1b1fe6a88767228ca66cc72e0a61`.
Runtime: `py3.12-abe4061a3fa70426`. Subsequent metadata edits change documentation only.
Installer SHA-256: `5c55cdf739901d7c7fb74eea3938b6337c8102392eb92c97f14b1e888d7ab285`.
Update ZIP SHA-256: `03a8cb0df5bd1658ea7f107431643f2bd99e60112b526b2139b344554d951718`.

The website index was updated through certificate-validated FTPS, with its previous copy backed
up; the report relay and other files were unchanged. Live HTTPS version and download links were
verified. GitHub About metadata was reviewed and continues to describe equal provider choices.
