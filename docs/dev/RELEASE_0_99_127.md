# 0.99.127 — Isolate damaged records and preserve repair evidence

Published on GitHub and armada.stamih.com on 6 November 2026 from
`719de6390ccd4c802f3adf387f62bd210470361b`. M5 is implemented, verified and
released. Maintainer acceptance remains separate and pending.

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

## Final release evidence

| Check | Result |
|---|---|
| Mandatory pinned local suite | **4,091 passed, six skipped** |
| Exact-source Windows CI, Python 3.14 | **4,093 passed, four skipped** |
| Exact-source Windows CI, Python 3.14.10 | **4,093 passed, four skipped** |
| PHP relay CI | Passed |
| Native launcher | Five recovery interruption points; DLL isolation with clean and legacy parents |
| Packaged WebView2 session / tray | 16 / 68 checks passed |
| Packaged visible / tray / busy restart | 69 checks each passed |
| Signed compatible-runtime upgrade | **72 checks passed**, 0.99.126 to 0.99.127 |
| Public downloads and website | Manifest signature, package size/hash/source bytes, installer hash and HTTPS release/download links verified |

[Windows CI 42214079514](https://github.com/smikees/armada/actions/runs/42214079514).
Both CI jobs retain the existing Python 3.14 warning in `voice_turns.py`; its cleanup
is tracked for M8. No live realm or provider was used. The owner's app was not restarted.

Installer SHA-256:
`d50a97074b123726449f094a4e05e0f4af91fc4d5ff87bfce4624f2ffe63f20d`

Package SHA-256:
`ebd5d0f4ebb7fba4a61271a3dff068ad69ebda86b802946ecc56c84edf048fe7`

The website deployment backed up replaced files, verified upload hashes and published
index.html last. The public verification independently downloaded both release artifacts.
Runtime remains `py3.14.10-7bc0018406bbe195`, compatible with 0.99.125 and newer.
Older clients still require the full installer once.

## Development findings and boundaries

The initial pinned implementation gate passed 4,087 tests with six skips. Final review
reproduced an invalid retry-count detail-page failure: four new cases failed first,
and shared retry validation then routed them to repair. The follow-up passed 383
focused checks before the final mandatory gate above. Earlier combined final
page/state/reference checks passed 401 tests. Snapshot changes only add repair help
text and the changelog; repair-form JavaScript syntax was checked.

Synthetic checks cover core sibling pages, provider admission, command refusal,
scheduler/inbox isolation, exact evidence bytes, stale reviews, replacement failures,
authenticated HTTP repair, origin refusal and immutable realm binding.

A warm reader observation with 40 agents / 120 jobs and 12 interleaved iterations
measured 50.2 ms before / 68.3 ms after. This ran under concurrent test load and is
not an end-to-end navigation or acceptance benchmark; retained for M9.

Automatic approval review initially blocked publication. The owner explicitly
approved pushing this candidate and releasing 0.99.127 on 6 November; publication
then used the mandatory maintenance publisher without bypassing its checks.

Packaging, launcher and runtime dependencies are unchanged. Windows Sandbox was not
rerun for this app-only release. **Clean-machine GUI acceptance and ARMADA publisher
signing remain unverified**, with the existing WebView2 prerequisite boundary retained
from [0.99.126](RELEASE_0_99_126.md). The approved unsigned Windows maintenance
installer and separately Ed25519-signed update manifests remain distinct guarantees.

Provider defaults are unchanged from the official metadata review recorded in
[0.99.126](RELEASE_0_99_126.md) on 5 November 2026.

## Retained evidence

Ignored local records: `build/publish-0.99.127.log`,
`build/release-evidence-0.99.127.json`, `build/upgrade-0.99.127.json`,
`build/public-0.99.127/verification.json` and `build/website-0.99.127.log`.
Development evidence: `build/m5-pinned-gate.log`, `build/m5-final-focused.log`,
`build/m5-retry-red.log`, `build/m5-retry-final.log` and `build/m5-reader-timing.json`.
