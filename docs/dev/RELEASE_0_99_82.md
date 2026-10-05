# ARMADA 0.99.82 verification

This release implements [the update reliability contract](UPDATE_RELIABILITY.md):
Windows token-profile instance scope, native entry-point guarding, signed minimum
bootstrap compatibility, bounded preparation retries and cleanup, real-browser
startup acknowledgement, delayed job admission, journaled startup rollback,
release quarantine and page/thread/draft/window continuity.

Targeted checks cover concurrent launch/crash release, interrupted installation,
interrupted rollback at each rename, exact-package health acknowledgement, damaged
rollback refusal, low disk space, incompatible bootstrap, quarantined release,
bounded network retries, profile overrides and helper retention. The targeted
updater/lifecycle/release checks were followed by the mandatory final-source gate.

## Final verification

[Release v0.99.82](https://github.com/smikees/armada/releases/tag/v0.99.82) was published
from commit `135889128bf569e2338616a64048d3bac07340fa` on 2026-10-05.

- Final isolated local suite: **3,139 passed, five skipped**, 429.92 seconds.
- [Exact-source Windows/PHP CI](https://github.com/smikees/armada/actions/runs/37327809615): passed.
- Staged native launcher: all five interrupted-replacement recovery cases passed.
- Actual staged WebView2: 16 session checks passed, including two companion cycles,
  Usage continuity and deliberate loss of a delivery acknowledgement without duplicate requests.
- Signed-asset packaged upgrade: 28 real-page/restart checks passed for the previous
  0.99.81 payload and 0.99.82 candidate, including Settings, Documentation, threads,
  Usage, the production companion opener, startup health commit and monitor completion.
- Separate native Windows account check: profile overrides preserved the account
  identity; a live owner remained unchanged and blocked a competing kernel lock.
- Thirty synchronized system-job process races each dispatched once, skipped the
  contender and prevented replay. A delayed-initialization fault is also covered.
- Real HTTP checks verify a successor's changed port/data folder and reject an
  unrelated nonce. Rollback checks preserve realm data and exact failure evidence.

Installer SHA-256: `ea4bbd48c838c09dacba9201156b0b7734fa4286ac274dd5cc984453031e6193`.
Update package SHA-256: `6c088e8af9fa296f01ffbd736011058f2e3351fa2d97f0c193da362a519a23eb`.
The downloaded published update assets passed signature, size, hash, bootstrap and
source-commit verification. GitHub's installer digest matches the built installer.

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
