# 0.99.144 - Native questions, Activity monitor polish and missing limits

Released on 12 November 2026 from `a3c6ad0277e7c81f31e5e09b0327f2cb7eb33009`.
The [GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.144)
and [website](https://armada.stamih.com/) both offer v0.99.144.

Missing subscription readings again show a dashed track and **Not reported**.
The dashed style previously lived only in Armada II, leaving other themes with a
faint solid track; the live renderer also used Unavailable for absent readings.
The common style now preserves readable labels and dashed tracks in every theme.
Provider-specific reasons remain in tooltips and accessible descriptions. Stale
percentages remain explicitly marked as last readings, disconnected engines retain
their own label, and loading never invents a zero-percent reading.

Activity monitor has a manual refresh icon and rows of circular agent portraits
with the shared status dots, including pulsing gray for working agents. Each row
deduplicates agents with multiple threads or requests. Needs attention stays open
at the end. Full snapshots refresh every five minutes while visible; the existing
lightweight status poll triggers updates on activity changes. Failed refreshes
retain the last reading and show it is stale. Keyboard focus survives updates,
including when a focused agent leaves a row. Viewing does not mark replies read.

Detached model and effort badges update through the existing realm-bound thread
snapshot, without replacing the composer or changing its draft and selection.
See [the desktop/session contract](WINDOW_SESSIONS.md).

Claude and Codex native questions now appear above the composer in both views.
Single choices, multiple selections and permitted free text continue the same run;
reopening a view restores a pending question. Answers are journaled before delivery,
scoped to the exact realm/thread/run/request, and idempotent across views. Skip does
not invent an answer, Stop remains effective, and question/answer receipts remain
in history. Waiting questions appear under Needs input. Dedicated tool-approval
requests remain denied, including MCP approvals using the user-input RPC. Background
and Inbox turns stay noninteractive. Claude's stream waits for the SDK idle signal
and delegated-agent continuations. Real neutral question round trips passed on
both verified subscription logins, with API keys/fallback disabled and no side-effect
tools; evidence is in `build/native-question-claude.json`, `build/native-question-codex.json`
and `build/claude-question-initialize.json`. Synthetic duplex tests cover permission
denials, failed persistence, stale and duplicate answers, realm switching and cancellation.

The final enforced publisher passed **4,495 tests with 6 skips** in 1052.23 seconds.
Both exact-source Windows Python jobs passed **4,497 tests with 4 skips** each
(782.25 and 793.34 seconds), and relay passed. The publisher verified the
explicit manual selector and recorded its actual trigger in
`build/release-evidence-0.99.144.json`.
[Windows CI](https://github.com/smikees/armada/actions/runs/43282559263).

Final-source stabilization passed in **353.25 seconds**, including
three **163-check** native thread/window cycles and **28 owner-workflow checks**.
Evidence is in `build/stabilization-20261112-194933-087780`.
The freshly bundled Python 3.14.10 runtime separately passed all **163 native
thread checks** in `build/widget-model-bundled-0.99.144.json`.
The probes cover manual and timed refreshes, completion transitions, failure
recovery, keyboard focus, light/dark dashed tracks and a 150-percent layout.
Light/dark dashboard and main/companion presentation captures were reviewed.

Native validation caught a late pywebview callback during Python/CLR teardown
after all assertions had completed. The probe now drains its own bridge workers
before interpreter shutdown; the final-source cycles must exit cleanly as well
as passing their assertions. Earlier failed evidence remains in
`build/stabilization-20261112-192938-574384`.
The first final-source stability attempt also hit the previously recorded Windows
snapshot path-resolution race during an atomic write. The safety check rejected the concurrent
read; its evidence remains in
`build/stabilization-20261112-194224-907423`. No path safety check was weakened.
The complete stability gate was repeated unchanged; that limitation remains known.

The final installer passed launcher recovery, DLL isolation, WebView2 sessions,
tray lifecycle, all three restart cases and presentation recovery. The signed
upgrade from v0.99.143 passed **72 checks** against these assets.

Public verification confirmed the update signature, tag/manifest commit, ZIP hash,
all **496 packaged files**, matching website links and the downloaded installer hash.
The **23,423,801-byte** installer has SHA-256
`b4ff7f735b0cd743c7d66bd4afc89d33200f12c408381e45d4922cef0e44a453`.
The update ZIP has SHA-256
`4009e547ecc08f513873d2f99990ba789fb7693a27e66afd6e683c9fb05651a0`.
Evidence: `build/public-release-0.99.144.json`, `build/upgrade-0.99.144.json` and
`build/release-evidence-0.99.144.json`.

This continues the owner-authorized unsigned maintenance beta distribution.
Ed25519 update signing passed; trusted Windows publisher signing and clean-machine
Sandbox acceptance remain unverified. Hardware KVM switching and mixed-DPI removal
remain unverified. The owner app was not restarted, live realms were not modified
and the temporary worker account was left in place as requested.
