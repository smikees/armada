# 0.99.127 — Isolate damaged records and preserve repair evidence

M5 candidate, prepared on 5 November 2026. Publication and final release gates are
pending. Maintainer acceptance remains separate.

Healthy agents and core realm pages remain usable when another agent/job contains
malformed JSON, duplicate keys, invalid encoding or invalid field types. Damaged
records show repair information and cannot authorize model/command execution.
Automatic inbox dispatch holds damaged recipients without consuming their messages.

The owner can review complete replacement configuration on the affected detail page.
Authenticated, realm-bound repair checks the original digest, validates the new
configuration and preserves exact original bytes plus an owner receipt before
atomic replacement. Ordinary editors cannot silently reset damaged input.

Malformed history rows are excluded from presentation with an incomplete-data
warning. That agent's scheduled jobs are held to avoid repeating uncertain work;
healthy agents remain eligible. History repair requires verified evidence, and no
repair replays work. See [the record-health contract](RECORD_HEALTH.md).

## Validation

Focused synthetic checks cover all core sibling pages, provider admission, command
refusal, scheduler/inbox isolation, evidence preservation, stale reviews, failed
replacement and authenticated HTTP repair. Full pinned suite, exact-source Windows
CI, packaged native/upgrade gates and public artifact verification are pending.

No live realm or provider is used for validation. The owner's app is not restarted.
The runtime/launcher remain compatible with 0.99.125 and newer. Older clients still
need the full installer once. This release retains the authorized unsigned Windows
maintenance distribution, separately signed update manifests, and the existing
unverified clean-machine WebView2/publisher-signing acceptance boundary.

Provider defaults are unchanged from the official metadata review recorded in
[0.99.126](RELEASE_0_99_126.md) earlier on 5 November 2026.
