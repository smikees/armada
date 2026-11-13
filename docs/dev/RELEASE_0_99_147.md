# v0.99.147 release validation

Publication is in progress. This release preserves update-blocked composer drafts,
drains queued inbox work during update preparation, distinguishes live system-job
status, adds queued Activity portraits and shows system work in every calendar view.
See [the implementation and regression contract](UPDATE_ACTIVITY.md).

Pre-release functional validation passed 4,564 tests with 6 skips, 98 native owner
workflows, 52 dedicated calendar/layout checks and three 163-check thread-window
cycles. The final versioned release source will repeat the mandatory publisher,
exact-source Windows CI, stabilization, staged-runtime and signed-upgrade gates.

The first release candidate was withheld after Python 3.14.10 CI reproduced a
concurrent snapshot-write failure: Windows `Path.resolve()` retained `\\?\` for
the destination while the base used ordinary drive syntax. The containment check
mistook those equivalent paths for an escape. Namespace-only comparison now
handles drive and UNC forms while preserving traversal and reparse rejection.
Twelve deterministic cases and 300 real concurrent snapshot repetitions cover the
fix; the focused snapshot/capture suite passed 77 tests before the final gates.

Provider preference selection was reviewed: only connected providers and models
reported available may be selected; an unavailable preference falls back to the
provider default. This release does not change provider preferences or runtime.

This continues the owner-authorized unsigned maintenance beta distribution.
Update assets are Ed25519-signed. Trusted Windows publisher signing and
clean-machine Sandbox acceptance remain unverified. No owner app restart,
live realm mutation, real provider call or temporary test-account cleanup is
part of publication.
