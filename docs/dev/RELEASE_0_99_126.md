# 0.99.126 — Bound local requests and provider refreshes

Published on GitHub and armada.stamih.com on 5 November 2026 from
`d853dd04b481a4651ac5e2cd3a62ac71ba166961`. M4 of the stabilization plan is
implemented and verified; maintainer acceptance remains pending.

The cockpit and content-origin servers now bound incomplete headers, input size,
input time and concurrent handlers. Health/stop controls have separate admission
capacity from ordinary work and conversations. Malformed JSON is rejected before
mutation dispatch. Refused uploads receive a bounded drain period so unread input
does not discard their error response with a Windows TCP reset.

Provider status and the older auth-status endpoint share in-flight observations.
Unchanged observations skip configuration writes; Disconnect stays authoritative
during a refresh. No mutation or agent work is automatically replayed.
See [the HTTP contract](HTTP_LIMITS.md) for exact limits and connection semantics.

## Verified release evidence

| Check | Result |
|---|---|
| Mandatory pinned local suite | **4,040 passed, six skipped** |
| Exact-source Windows CI, Python 3.14 | **4,042 passed, four skipped** |
| Exact-source Windows CI, Python 3.14.10 | **4,042 passed, four skipped** |
| PHP relay CI | Passed |
| Native launcher | Five recovery interruption points; DLL isolation with clean and legacy parents |
| Packaged WebView2 session / tray | 16 / 68 checks passed |
| Packaged visible / tray / busy restart | 69 checks each passed |
| Signed compatible-runtime upgrade | **72 checks passed**, 0.99.125 to 0.99.126 |
| Final native thread-window probe | **79 checks passed**, including sender/observer Stop, stale run IDs, disconnect and reopening during work |
| Exact-installer Sandbox | **26 passed; one WebView2 prerequisite failure** — see boundary below |
| Public downloads and website | Manifest signature, package size/hash/source bytes, installer hash and HTTPS release/download links verified |

[Windows CI 42080120878](https://github.com/smikees/armada/actions/runs/42080120878).
CI retains the pre-existing Python 3.14 warning in `voice_turns.py`; its cleanup is
tracked for M8. No live realm or provider was used. The owner's app was not restarted.

Installer SHA-256:
`e50f075a1c81b1bd16918eb6bd8945a5d3bf80de0888c948c07cb1a6f16f7ce3`

Package SHA-256:
`4680d6fdcb46633c2efca88cdf84be9966a29eadce89846fdb4edec7cb33bf74`

Runtime remains `py3.14.10-7bc0018406bbe195`, compatible with 0.99.125.
Versions through 0.99.124 still require the full installer once. Finish jobs and
quit ARMADA before installing; realms and settings are preserved.

## Validation findings and boundaries

The full gate caught a Windows reset when oversized headers left unread input.
A related delayed-upload probe reproduced 30/30 handler-error connection aborts.
Gate refusals and handler errors now share bounded, worker-free draining. Regression
cases cover late input after 400, 401 and 413 responses, oversized headers, drain
expiry and continued control admission. Failed candidates were not published as releases.

The first auxiliary native Stop run timed out while the full suite was running.
Its cause was not conclusively established. The 0.99.125 baseline and four
instrumented M4 runs passed 76 checks each. The readiness check could match text
from an earlier turn; it now additionally requires the current turn's text and
an enabled Stop button, with failure diagnostics. Three sequential strengthened
runs passed 79 checks each, and the final corrected source passed all 79 again.
No production cancellation fix is claimed from that investigation.

The exact public installer passed locked-file refusal/preservation, payload-hash
verification, normal installation, imports, timezone, actionable missing-WebView2
recovery, uninstall, user-data preservation and reinstall. Both WebView2 installers
returned `-2147219198` in Sandbox. **Clean-machine GUI acceptance remains unverified.**
The authorized unsigned-maintenance distribution continues; ARMADA publisher signing
is not configured. Update manifests are separately Ed25519-signed.

Resource limits do not guarantee availability against continuous local flooding.
The control reserve is server-side; browser connection pools and renderer
responsiveness are separate. Slow response readers can occupy their lane until a
write times out. Execution admission remains a separate M8 concern.

## Retained evidence

Local ignored records: `build/release-evidence-0.99.126.json`,
`build/publish-0.99.126-all-refusals.log`, `build/thread-window-m4-all-refusals.json`,
`build/sandbox-runs/20261105-191649/`, `build/public-0.99.126/verification.json`
and `build/website-0.99.126.log`. Earlier failed and diagnostic probes are retained.

Provider defaults are unchanged after reviewing official metadata on 5 November:
[Claude](https://platform.claude.com/docs/en/models/opus-5-5/overview),
[Codex](https://developers.openai.com/api/docs/models/gpt-6.1-sol),
[Gemini](https://aistudio.google.com/docs/models/gemini-3.8-flash).
Connected-provider catalogues remain authoritative.
