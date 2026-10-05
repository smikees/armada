# Update reliability contract (0.99.82)

One desktop/server owner is enforced using the Windows token's profile directory,
independent of realm, installation path, port, ARMADA_DATA_DIR, HOME and USERPROFILE.
Native library launches claim the same guard as the CLI. A second launch requests
activation and exits; companion windows belong to that owner. Test tooling explicitly
patches the account directory inside an isolated child; production has no override.

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

The protocol change requires a full installer from 0.99.81 and earlier. Existing
clients recognize the changed runtime tag and direct users to the installer. A
clean-machine installer rehearsal remains required for signed distribution; an
explicit unsigned maintenance release records that unresolved acceptance boundary.
