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
- Final full suite, exact-source CI, native recovery/session/upgrade and public asset/website
  verification must pass before publication completes. Runtime compatibility is unchanged.

Voice remains an experimental Codex-only feature using existing sign-in and separate audio/agent
accounting. The continuing authorized maintenance release uses an unsigned Windows installer and
an Ed25519-signed update. Publishing does not restart the owner's running application.
