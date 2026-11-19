# v0.99.163 — fresh memory and readable agent questions

Published on 19 November 2026 from `154a57c6a0ec84ecfae83d86d9371e8d3da09bce`.
[GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.163) and
[website](https://armada.stamih.com/) offer the matching installer.

System memory now honors saved Environment settings and free-text notes. Saves,
startup and run preparation regenerate the digest; agents see its regeneration
time. New replies and job results retain the exact memory inventory supplied to
that run. UTF-8 settings are read strictly, with errors preserving existing data.
See [memory freshness and provenance](MEMORY_FRESHNESS.md) for the storage and
failure boundaries. Receipts describe supplied context, not proof of attention.

Identical provider reply/error messages are displayed once. Distinct errors,
partial replies and interruption details are preserved. Agent questions use the
shared safe Markdown renderer, so paragraphs, line breaks, lists, emphasis and
code render consistently in the live panel and saved conversation. Body text is
normal weight. Question IDs, answer choices and delivery semantics are unchanged.
Raw HTML is escaped and unsafe link schemes remain inert.

The release retains runtime compatibility and the standing unsigned maintenance
beta boundary. Update packages are Ed25519-signed; Windows publisher signing and
clean Sandbox acceptance are not claimed. The owner requested both publication
and updating the installed app. The installed copy was updated through the
authenticated in-app path, which waits for active work and restarts through the
update bootstrap.

Python's official Windows release list was checked on 19 November 2026:
[3.14.10](https://www.python.org/downloads/windows/) remains the current patch in
the supported 3.14 branch. The packaged runtime is unchanged. Provider metadata confirmed all first-choice release preferences remain
available; existing model settings and defaults are unchanged.

The full isolated local suite passed **4,899 tests with 6 skips** in
**945.23 seconds**. [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/44588173365) passed
both Python jobs and relay checks. The stabilization gate passed fault recovery,
30-round concurrent soak, history performance budgets, three native shared-thread
runs, page-work and owner workflows. Evidence is retained in
`build/stabilization-20261119-192834-240834`.

The first CI attempt hit the existing dispatch stress test's 15-second cleanup
deadline on one runner. The other matrix job and an immediate local recheck
passed. Only the failed CI job was rerun, on unchanged source; the final run
passed. The timeout and retry are retained in `build/ci-retry-163.json`.

The freshly staged runtime passed **124 owner-workflow checks**,
**197 thread-window checks** and **11 inbox-timing checks**.
Question rendering was reviewed in light and dark native windows, including a
compact companion. Safe question Markdown and the saved answer receipt have
regression coverage; a read-only check of the reported saved question confirmed
five rendered numbered items. No private question content is committed.

Packaged launcher recovery, DLL isolation, session, tray, restart and presentation
recovery checks passed. The signed previous-release upgrade rehearsal passed
**72 checks**. Public verification checked the
Ed25519 manifest signature, exact source commit, all **518
tracked package files**, installer hash and matching website download links.
Installer: **23,538,558 bytes**, SHA-256
`a9cd8b5268b72149ab0c287cab1bb672a9ffe7ca01bdd23c3604fa9e1bce0ba8`.
Package SHA-256: `cc3154667ea19d433e3dca33223001bb073a11e68f354df079f5d9ee50a072a8`.

The installed app reports **0.99.163** through its authenticated version endpoint.
Its startup refreshed System memory, and every nonblank saved environment field
checked is present in the generated digest. The release does
not rewrite historical duplicate error messages; existing saved questions use
the corrected renderer without changing their stored source.

Evidence: `build/release-evidence-0.99.163.json`,
`build/public-verification-0.99.163.json`, `build/website-0.99.163-publication.json`,
`build/installed-verification-0.99.163.json`, `build/stabilization-0.99.163.json`,
`build/owner-staged-0.99.163.json`, `build/thread-staged-0.99.163.json`,
`build/inbox-staged-0.99.163.json`, `build/questions-native-163.json`,
`build/question-history-shape-163.json`, `build/release-defaults-0.99.163.json`,
`build/golden-review-163.diff` and `build/publish-0.99.163.log`.
