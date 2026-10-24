# Codex-native voice proof of concept — 2026-10-24

The owner requested hands-free calls with Mute and End controls in the existing thread composer.
This is a narrow extension of that surface, including detached windows, not a second conversation
store. Claude Code 2.1.289's documented dictation does not provide the same spoken-response path.

## Verified provider contract

Generated experimental JSON/TypeScript schemas from installed Codex CLI 0.157.1 and exercised
real `app-server` requests. `initialize` enables `experimentalApi`; `thread/start` creates an
ephemeral read-only thread in an empty temporary directory. `thread/realtime/start` selects V3,
audio output and the browser's WebRTC SDP. The CLI emits `thread/realtime/started` and
`thread/realtime/sdp`. The browser's native peer carries media, without an audio proxy.

WebRTC works with the existing signed-in Codex account on the tested machine. The WebSocket
transport refused that sign-in with “realtime conversation requires API key auth”; ARMADA does
not fall back to it or read credential stores. No undocumented provider HTTP endpoint is called
by ARMADA. Future protocol/account changes can make this experimental feature unavailable.

In an actual V3 call, the CLI emitted `thread/realtime/transcript/delta` and
`thread/realtime/transcript/done` (`threadId`, `role`, `text`). Final parts lack item IDs; they
are consumed once in order from the owned, non-replayed stdio connection. Native deltas are
provisional shared UI text; if interrupted, their remaining text is saved with an explicit
incomplete-transcription marker. Browser-authored transcript fragments are never accepted.
The alternative schema's canonical
`thread/realtime/item/completed` / `transcriptSegment` is also supported with native-session
validation and item deduplication. A call consumes only one final protocol, avoiding double saves.

## Boundaries and lifecycle

### Dictation extension

The composer distinguishes **Dictate** (microphone) from **Voice chat** (waveform). Both
use the same owned Codex WebRTC transport; `mode` is validated as `dictation` or `voice`.
The installed CLI has no separate app-server transcription method. Actual probes rejected
V3 text output with “text realtime output modality requires realtime v2”, then rejected V2
WebRTC with “AVAS realtime calls require realtime v1 or v3”. Therefore dictation uses the
verified V3 audio session, with incoming audio never attached to a player. It still consumes
voice usage and is not represented as a dedicated transcription service.

Dictation starts without agent core or thread history. Native user transcript deltas enter
an in-memory, explicitly editable draft; final segments replace their provisional text. V3 can
delay final events until the session closes, so draft previews cannot depend on them. Assistant
segments are ignored, including the short acknowledgement requested to delimit utterances.
Shared thread snapshots expose status,
not draft text. The scoped owner state endpoint returns the draft. No dictated text enters
the Thread store or report; reports retain only mode, counts and duration. Done silences the
microphone and allows a bounded 3–8 second finalization interval before closing the transport
and inserting at the original composer selection. Cancel discards the in-memory draft even
when invoked from the other view. A disconnect preserves already received text as an unsent
draft. The usual Send path then uses the configured text model and normal grants.

The native synthetic dictation probe returned the spoken question verbatim without changing
the two seeded messages. Browser validation additionally checks no audio playback, existing
draft preservation, explicit Send, Cancel, and shared-window controls.

### Conversation ownership — corrected in 0.99.111

- `voice.py` owns audio and native transcript admission; `voice_turns.py` owns a server-side
  FIFO queue per immutable realm/agent/thread. Final user parts are batched after one second
  without further speech, atomically appended to the shared Thread store, and assigned a normal
  RunSession before the worker starts. Call termination flushes accepted final parts.
- Every request uses the existing TurnCoordinator with the same engine selection, model,
  effort, core context, grants, tool execution, progress, output evidence and accounting as
  normal chat. An admitted-turn identity avoids duplicating the user message. Pending queued
  speech is excluded from the current prompt, while completed earlier results remain visible.
  Missing, answered or archived queued requests are not executed or recreated.
- Audio has its own RunSession, kind `voice_audio`. End call, lost lease or leaving the view
  closes only that process. Stop work cancels active and queued normal sessions, not audio.
  One microphone call remains allowed app-wide. A call may open while normal work is active.
  This is in-process durability across view/call closure, not an app-restart task replay system.
- The native speech thread remains ephemeral/read-only with shell, web, MCP, apps, plugins,
  images and notifications disabled. It has no agent core or history. It acknowledges only
  receipt; native assistant transcript text is never persisted as a task answer. Only the normal
  runner persists actual replies and terminal status. Old saved voice-only responses have an
  explicit no-task-execution caption instead of Done.
- `clientManagedHandoffs=true` prevents automatic backend response forwarding. The normal
  runner's saved reply is sent with verified `thread/realtime/appendSpeech` (`threadId`, `text`).
  Audio readback failure cannot change or erase a successful normal task. Reply text is bounded
  to 3,500 characters for speech; the full reply remains saved. Ending audio suppresses further
  playback while allowing work to finish. The audio frontend requests a short Received
  acknowledgement because V3 may not finalize user text while instructed to wait silently.
- The native frontend can still disregard its acknowledgement-only prompt. Its audio player
  therefore stays muted independently of the prompt. Saved replies wait until the native
  acknowledgement ends; the owning browser unmutes and acknowledges a server-generated reply ID
  through the scoped state route before appendSpeech is sent. Duplicate or invented reply IDs
  cannot submit speech. User speech interrupts readback. A reopened call can receive work that
  started under the previous call. The normal runner and saved transcript remain authoritative.
- The audio watcher and queue share the metadata file lock with unread-status writers. This
  prevents a Windows replacement/read sharing race from ending audio when normal work completes.
- Deltas remain provisional UI text. Interrupted user text is saved as explicitly incomplete,
  never automatically executed. Dictation remains a private unsent draft. Audio, SDP and raw
  provider events are not persisted; audio reports retain mode, duration, count and unknown usage.
- The browser shows a connecting spinner and keeps microphone tracks disabled until WebRTC
  reports connected. A local Web Audio analyser measures sound without recording or playing it.
  Mute/finish shows zero; End disconnects the analyser and closes its AudioContext.
- The owning page renews a 15-second lease; setup allows 60 seconds, and a call is limited to ten
  minutes. Archive, unavailable realm and application shutdown also end audio. Shared canonical
  snapshots keep normal work and speech visible in main and detached windows.

The 0.99.109/110 implementation shared only transcripts: its restricted responder could promise
an action without running tools, and Done misleadingly labelled that acknowledgement. The new
split keeps the restricted transport as speech input/output and uses the normal runner for work.

## Reproduce

`tools/voice_preview.py --window` opens only the synthetic Voice Lab realm under `build/voice-poc`.
It starts no scheduler and changes no production realm. Existing Codex sign-in is used only when
Voice is selected; native microphone permission is required. A headless test used an artificial
spoken question, “What is the code word from our earlier conversation?”, and the seeded text
history. Codex replied “Cobalt”; native final transcripts and incoming audio packets were observed.
No real owner microphone was recorded for that test.

Unit coverage includes protocol sealing, native transcript formats, scoped cancellation,
archive/disconnect cleanup, independent cancellation, FIFO admission and safe signaling validation. Native detached-thread
and browser UI checks supplement these; successful synthetic tests do not certify every account,
microphone driver or future CLI version. The owner should assess audio quality in the local POC.

Provider references: [app-server](https://learn.chatgpt.com/docs/app-server),
[Codex voice](https://learn.chatgpt.com/docs/features/voice),
[Claude dictation](https://code.claude.com/docs/en/voice-dictation).
