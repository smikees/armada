# Update reliability contract (0.99.82)

One desktop/server owner is enforced using the Windows token's profile directory,
independent of realm, installation path, port, ARMADA_DATA_DIR, HOME and USERPROFILE.
Native library launches claim the same guard as the CLI. A second launch requests
activation and exits; companion windows belong to that owner. Test tooling explicitly
patches the account directory inside an isolated child; production has no override.
Fresh kernel lock initialization has a bounded one-second grace period for a
descheduled creator; contenders cannot enter without its marker. Interrupted or
unrecognized lock files are preserved and refused.

The updater verifies signed version, runtime, minimum bootstrap protocol, size and
SHA-256 before staging. Staging checks the expanded package budget and available
disk space and uses a writable temporary sibling. Temporary network errors retry
three times; transient sharing violations have bounded exponential backoff.
New work is refused during handover and active jobs are drained, never killed.

Bootstrap protocol 2 writes a durable health transaction after swapping code. The
main browser must load the app page and fetch the instance API using its actual
cookie, matching version and process nonce. Only then is health committed and the
owned scheduler started. Provider connectivity, quotas and findings are not startup
health conditions. A local refusal during initial navigation gets one explicit
reauthentication attempt; authentication errors are not silently hidden.
The monitor follows the successor's owned endpoint if the original port became
occupied, using its new protected credential and checking the instance nonce.

On unacknowledged startup failure, the monitor asks that successor to exit. It waits
for its kernel-held leases and restores the verified previous code through another
durable journal. If it cannot establish an idle installation or verify previous code,
it reports the specific error and leaves files intact. It never kills active work.
The failed release is quarantined to prevent an automatic retry loop. A subsequent
ordinary launch also recovers an abandoned, attempted health transaction.

Rollback restores code only. All automatic startup migrations must remain readable
by the previous version. A future destructive migration must add a targeted backup
and recovery procedure before it ships; restoring whole realms automatically would
risk losing work. This release adds no realm-format migration.

Restart saves page/thread, text draft and window bounds outside the replaceable
package. Chat drafts are keyed by realm and thread in the protected browser profile.
Staging leftovers older than one day are cleaned under the installation lock.
Restart helpers retain at most five recent attempts and expire after thirty days,
excluding a running monitor. The updater remains on-demand, with no new service.

Both signed and maintainer-authorized unsigned publication paths require the full
isolated suite, exact-source successful CI, installer native recovery/session checks
and a packaged previous-payload -> candidate update through the production API.
The native upgrade gate uses the current installed runtime/bootstrap: protocol 2's
one-time installer transition is separate from a compatible code update. Its real
Settings, Documentation, Usage, companion and thread checks use browser cookies.
Evidence is tied to signed package hashes and source commit, not an earlier run.
The source commit is captured before local validation and checked again afterwards;
changes during validation invalidate that run. Companion request IDs prevent a
lost native acknowledgement from sending the same support request twice.

The protocol change requires a full installer from 0.99.81 and earlier. Existing
clients recognize the changed runtime tag and direct users to the installer. A
clean-machine installer rehearsal remains required for signed distribution; an
explicit unsigned maintenance release records that unresolved acceptance boundary.

## Remaining improvements (reviewed 2026-10-05)

The existing lightweight updater already verifies signatures/hashes, serializes
replacement, drains work, monitors restart, tests real browser sessions and can
recover unacknowledged startup. The following gaps remain, in priority order:

1. **Graceful full-installer handover.** `installer/armada.iss` currently calls
   `StopArmada` from `PrepareToInstall`; it force-stops processes within the chosen
   installation's Python directory. Scope is constrained, but active work is not
   drained. The full installer should request authenticated cooperative shutdown,
   wait for work and process leases to finish, and postpone installation when it
   cannot safely close the app. It should never replace files while an owner is
   still using them. This differs from the compatible in-app update path.
   [Inno Setup guidance](https://jrsoftware.org/ishelp/topic_setup_closeapplications.htm)
   explicitly warns that forced closure can lose unsaved work.
2. **A single startup commit covering the required scheduler.** `app._page_loaded`
   calls `confirm_health` after browser authentication, before starting the
   scheduler. The monitor subsequently checks scheduler readiness, but by then
   the health transaction has been removed. A required scheduler startup failure
   can therefore be reported without remaining eligible for automatic startup
   rollback. Keep rollback eligibility until both the browser and required
   scheduler acknowledge readiness. Paused/autostart-disabled/setup cases should
   remain deliberate exceptions; provider outages are not startup failures.
3. **Full-installer interruption tests.** The production packaged upgrade gate
   exercises app-payload replacement in the current runtime. Add real previous-
   installer-to-candidate rehearsal on an ordinary Windows account, including
   active work, antivirus file locks, sleep/resume, low disk space and interrupted
   runtime replacement. Preserve the prior usable runtime until installation is
   committed, with explicit recovery. Microsoft's
   [rollback model](https://learn.microsoft.com/en-us/windows/win32/msi/rollback-installation)
   is a useful behavior reference, not a proposal to migrate the app to MSI.

These are review findings and proposed work, not shipped guarantees in 0.99.84.
They can reuse the existing supervisor, leases and release tests. No persistent
update service or additional client framework is necessary.
