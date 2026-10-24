# 0.99.111 verification

The owner reported that voice acknowledged research but did not perform it, then showed Done.
The previous preview shared the transcript with the thread but used a separate restricted
responder. This release makes speech an input/output layer for the ordinary agent runner.

## Changes

- Final user transcripts enter a server-owned FIFO per realm/agent/thread, with durable user
  messages and queued progress before execution. They use the same TurnCoordinator, model,
  effort, grants, core context, tools, progress and results as typed chat. Pending future requests
  stay out of the current prompt; earlier completed results stay in it. Existing typed work
  finishes before queued speech starts. Missing/answered/archived queued requests are not replayed.
- Audio and normal work have independent RunSessions. End call, page closure and microphone
  lease expiry stop audio; accepted requests continue. Stop work cancels active and queued work.
  There is no automatic side-effect replay after application shutdown.
- Only actual normal-runner answers receive completion status. Native acknowledgements are
  neither saved as answers nor played. The owning browser unmutes for an identified saved reply
  before appendSpeech sends it. Interrupted transcription stays explicitly incomplete and is
  not executed. Old voice-only responses say no task execution was recorded instead of Done.
- Connecting uses the existing spinner, accessible status and wait-until-Listening copy;
  microphone tracks are disabled until connected. Voice can reopen during ongoing work.
- Locked metadata reads prevent a Windows sharing race between the voice watcher and unread
  writes at task completion from unexpectedly closing audio.

## Validation

- Real Codex CLI 0.157.1 with synthetic speech: requested a five-second wait, creation and
  verification of a file; ended the call during work; Stop work remained available; the newly
  written file contained exactly the requested text and the normal final reply persisted.
- Real shared-history/readback test: normal agent returned the seeded code word, saved exactly
  one user request and one answer, and spoke the real reply while remaining connected. The
  frontend's independent guess stayed muted. No real owner microphone was recorded.
- Focused lifecycle regressions cover duplicate native formats, queued fragments, existing typed
  work, independent cancellation, provider errors, removed/archived requests, playback handshake,
  reopened audio, metadata contention, legacy status and unsent dictation. Browser harness covers
  pre-connection mute/spinner, actual reply playback and End call preserving work state.
- Native companion synchronization, Stop, sizing and shadow probe: all 76 checks passed.
- Required UI captures cover connecting and work in main/detached views, light/dark, at 1280/480
  widths; no horizontal overflow. User docs, module reference and intentional goldens updated.
- The UI finish reviewer found a clipped progress label in the detached view. Measured composer
  clearance and an explicit foreign-window work status resolve it; the verdict pass scored that
  fix resolved, with approximately 36 px between the pending label and overlay in both themes.
- Final release gates and public download verification passed, as recorded below.
  Runtime compatibility is unchanged.

Voice remains an experimental Codex-only feature using existing sign-in and separate audio/agent
accounting. The continuing authorized maintenance release uses an unsigned Windows installer and
an Ed25519-signed update. Publishing does not restart the owner's running application.

## Publication evidence

Published 2026-10-24 as normal/latest
[v0.99.111](https://github.com/smikees/armada/releases/tag/v0.99.111) from source `0e97eea7b42166854a970ec7dbc97fdd54c5d9aa` through
`tools/publish_release.py --maintenance-unsigned`.

- Pinned isolated full release gate: **3722 passed, 5 skipped**.
- [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/40105430458) passed before artifact staging.
- Mandatory staged native launcher recovery and WebView2 multi-window session checks passed.
- The native detached-thread synchronization, Stop, sizing and shadow probe passed all 76 checks.
- The bounded UI finish review and documentation handoffs passed for connecting and working states in main/detached light and dark views.
- Signed compatible upgrade from 0.99.110 passed all 69 native checks.
- All four public downloads match their local sizes and SHA-256 values; the update signature
  verifies, and its package contains exactly 430 tracked application files,
  byte for byte. It is the latest normal GitHub release.
- [armada.stamih.com](https://armada.stamih.com/) deployed with certificate-verified FTPS,
  backup, verified temporary upload and rename. Public HTTPS content and installer download
  match the release. Website SHA-256: `40af8e01c036b07e0acdd85eecf06b8901711b444f190b1752a1df8d62e162c6`.
- Release defaults retain the same-day 0.99.110 provider-catalogue review: each primary release default is listed. Gemini no longer lists the
  secondary 3.7 fallback on this account; existing connected-provider filtering and provider-default
  fallback remain in place. No agent/job model or account settings were changed.
- The owner's running application was not restarted. Windows publisher signing remains pending;
  the maintenance installer is unsigned and the update manifest is Ed25519-signed.

| Public artifact | SHA-256 |
| --- | --- |
| `armada-0.99.111.zip` | `53d49e189c04888223cc8d279eb0fe48b31ae6a6bf9255dcacd40225543e3518` |
| `ARMADA-Setup-0.99.111.exe` | `bdaeb1336c475195472c11d0ab5f26d63f7a61737b215a97f4339e2049572303` |
| `armada-update.json` | `e56bdf9816b81bbe1aadfca9900be824632933ecb82bf025b0f4121a762a1703` |
| `armada-update.json.sig` | `68005e8f71d7470d0e236ac028329b4b1454162bc244d7338a5e2bd2e7f9bd97` |
