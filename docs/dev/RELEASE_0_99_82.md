# ARMADA 0.99.82 verification

This candidate implements [the update reliability contract](UPDATE_RELIABILITY.md):
Windows token-profile instance scope, native entry-point guarding, signed minimum
bootstrap compatibility, bounded preparation retries and cleanup, real-browser
startup acknowledgement, delayed job admission, journaled startup rollback,
release quarantine and page/thread/draft/window continuity.

Targeted checks cover concurrent launch/crash release, interrupted installation,
interrupted rollback at each rename, exact-package health acknowledgement, damaged
rollback refusal, low disk space, incompatible bootstrap, quarantined release,
bounded network retries, profile overrides and helper retention. The targeted
updater/lifecycle/release pass completed 104 tests before the final admission check
was added. Final release results will be recorded after the mandatory gate.

The publication command now enforces exact-source CI and an isolated packaged
previous-application-payload -> candidate update through the production API, in
addition to native interrupted-replacement and multi-window cookie tests. Both
signed and authorized unsigned maintenance paths use this gate. Evidence binds
the source commit and signed package hashes to that specific run.

## Distribution and compatibility boundary

Bootstrap protocol 2 requires the full installer once from 0.99.81 and earlier.
Later compatible releases use package updates. The packaged upgrade gate uses
the current staged runtime/bootstrap with the last published application payload;
it does not claim to test an older installer's full runtime transition.

The continuing maintainer-authorized unsigned beta distribution is explicit in
the release notes. Update metadata remains Ed25519-signed. Windows publisher
signing and clean Windows Sandbox GUI acceptance remain unresolved, as in prior
maintenance releases. No new service or runtime dependency was introduced. This
release adds no realm-format migration; automatic rollback restores code only.
