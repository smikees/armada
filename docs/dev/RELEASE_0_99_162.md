# v0.99.162 — thread clocks, copying, navigation and live input

Published on 18 November 2026 from `11d03eadb889e8f6ec331d0eb0216c4eb5adb624`.
[GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.162) and
[website](https://armada.stamih.com/) offer the matching installer.

Agent conversations show a live work clock and persist their final duration.
Timing starts after run-slot admission, excludes queue time, survives navigation
and uses a monotonic clock for the saved total. Older records remain valid and
do not display invented times. Code/prompt blocks have individual copy controls;
whole-answer copying preserves raw text. Clipboard acknowledgement and fallback
failures are handled explicitly.

Opening a thread shows its latest messages, including when old presentation-state
records exist. In-page updates preserve reading position. A circular down-arrow
above the composer returns to the bottom. These shared controls cover main,
widget and detached agent conversations. The native confirmation journey passed
193 checks, including exact whitespace, timer continuity, saved duration, jump
geometry and reading position while a follow-up arrives. Light/wide and compact
dark screenshots were reviewed in a bounded visual pass.

Live input now uses each provider's native transport: existing Codex app-server
`turn/steer`, Claude's streaming human-priority input on Code 2.1.286+, and
Antigravity ACP `session/prompt` on CLI 1.5.0+. Version/runtime availability gates
the composer. Gemini configurations whose per-tool connector filters or partial
native-write denials cannot be preserved by ACP retain print mode. Older transports retain their existing execution path and editable
drafts. Instructions remain bound to the original realm/run with durable receipts,
idempotent retries, bounded input, Stop and no automatic replay. Native provider
turn boundaries can differ; accepted input is not a claim that work is already
finished. See [provider research and implementation](THREAD_USABILITY.md).

Harmless native Claude protocol tests incorporated their follow-up. Its later
production-adapter retest hit the account's five-hour limit and kept an uncertain
receipt. Native Antigravity protocol and production-adapter tests incorporated
the follow-up and retained token accounting. No business data or credentials are
committed. The provider's internal task ledger remains available on Gemini as
before; strict sealed review turns remain unsupported. ACP may omit individual
tool-result content; that omission is explicit rather than fabricated. Background
jobs/inspectors retain their prior print-mode result capture.

Native ACP ignored its project write fence during a synthetic canary. Armada
therefore replaces native writes with its checked invocation-local writer. The
final native test wrote the approved file, refused and audited the outside path,
and created no forbidden file. Approved connectors passed a separate native echo
test; ACP permissions select one call only to an already-selected server. Stop
expires the writer before provider cleanup. Current write policies are rechecked
on each call. Read permissions remain unchanged.

Provider metadata confirms the configured preferred defaults remain available.
Python 3.14.10 remains current in the supported 3.14 branch, checked against the
[official Windows release list](https://www.python.org/downloads/windows/) on
18 November. The runtime and provider defaults do not change. This follows the
established unsigned maintenance beta: update packages are Ed25519-signed;
Windows publisher signing and clean Sandbox acceptance remain outside the verified
boundary. Publication does not restart the owner's running app.

Evidence: `build/thread-window-162-final.json`, `build/thread-provider-162-final.log`,
`build/providers-162-ready.log`, `build/claude-input-now-research.json`,
`build/claude-adapter-followup-162.json`, `build/gemini-acp-high-research-162.json`,
`build/gemini-adapter-followup-162.json`, `build/gemini-no-tools-inside-162.json`,
`build/gemini-mcp-162.json`, `build/gemini-guarded-write-162.json`,
`build/providers-policy-162-elevated.log`, `build/design-162.json`, `build/release-defaults-0.99.162.json`.
Final release results follow below.


The full isolated local suite passed **4,864 tests with 6 skips** in
**1040.77 seconds**. [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/44363789308) passed
both Python jobs and relay checks. The final-source stabilization gate passed
its fault matrix, 30-round concurrent soak, history performance budgets, three
native shared-thread runs, page-work and owner workflows. Its unique evidence
directory is `build/stabilization-20261118-185415-062072`.

Packaged launcher recovery, DLL isolation, session, tray, three restart cases and
presentation recovery passed. The staged runtime passed **124
owner-workflow checks**, **32 page/loading checks** and
**11 navigation checks**. The staged thread journey passed
**193 checks** for main/detached timing, exact copying, latest-message
entry, jump geometry, preserved reading position, native input receipts and Stop.
The signed previous-release upgrade
rehearsal passed **72 checks**. Packaged warm visits
with 3,000 archived messages measured **103.07 ms**
for Artefacts and **342.41 ms** for Capabilities. Packaged main and
companion recovery screenshots were reviewed in light and dark modes.

Public verification checked the Ed25519 signature, exact source commit, all
**517 tracked package files**, installer hash and
website links. Installer: **23,531,200 bytes**, SHA-256
`e3b9d565056d1e09a79a6cb920dc21d9bfbb258146835ca10af21258caab1da3`.
Package SHA-256: `05b7bf486d63bf18ad0d7d3b4916ae619ba3a7d97b8dc25a65a77cb690908eca`.

Evidence: `build/release-evidence-0.99.162.json`,
`build/public-verification-0.99.162.json`, `build/website-0.99.162-publication.json`,
`build/stabilization-0.99.162.json`, `build/owner-staged-0.99.162.json`,
`build/loading-staged-0.99.162.json`, `build/navigation-staged-0.99.162.json`,
`build/thread-staged-0.99.162.json`, `build/thread-window-162-final.json`,
`build/gemini-guarded-write-162.json`, `build/gemini-mcp-162.json`,
`build/golden-review-162.diff`, `build/design-162.json`,
`build/release-defaults-0.99.162.json` and `build/publish-0.99.162.log`.
