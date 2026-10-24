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
are consumed once in order from the owned, non-replayed stdio connection. Deltas and browser
transcript fragments are never durable. The alternative schema's canonical
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

### Conversation ownership

- Domain ownership: `voice.py`; provider protocol: `engine/codex_voice.py`; authenticated local
  signaling: `routes/voice.py`; microphone lifecycle: `thread_voice.js`.
- The existing `RunSession` registry owns the native process and cross-window Stop. A voice
  call excludes typed runs in its thread; only one voice call may own a microphone app-wide.
- No tool execution, general RPC proxy or client-authored transcript endpoint. Ambient MCP,
  apps, plugins, hooks, shell, web, computer/browser tools and images are disabled. Provider
  requests for tools/approval are refused; normal action turns abort the preview. The native
  thread is read-only in an empty directory. `clientManagedHandoffs` is enabled, and transcript
  tail forwarding is disabled. The live voice model is separate from the configured text model.
- Only final transcript text is appended atomically through the shared Thread store. Audio,
  SDP and raw provider events are not persisted. Reports record duration, final-part count and
  unknown usage, rather than inventing token/cost figures.
- Consecutive final fragments on each side share a spoken-exchange ID. The Thread store groups
  those parts for pending-turn detection and compaction, so an answered fragment is not later
  presented as an unanswered question.
- The owning page renews a 15-second lease; connection setup allows 60 seconds. Archive, realm
  unavailability, timeout (ten minutes), application shutdown or Stop cancel the owned process.
  The browser stops its tracks immediately on local End/page leave and on the next state poll
  after remote Stop. Server snapshots are shared by main and detached views.
- Signaling and transcripts are bounded. Errors use the existing credential/URL redaction.

## Reproduce

`tools/voice_preview.py --window` opens only the synthetic Voice Lab realm under `build/voice-poc`.
It starts no scheduler and changes no production realm. Existing Codex sign-in is used only when
Voice is selected; native microphone permission is required. A headless test used an artificial
spoken question, “What is the code word from our earlier conversation?”, and the seeded text
history. Codex replied “Cobalt”; native final transcripts and incoming audio packets were observed.
No real owner microphone was recorded for that test.

Unit coverage includes protocol sealing, native transcript formats, scoped cancellation,
archive/disconnect cleanup, turn exclusion and safe signaling validation. Native detached-thread
and browser UI checks supplement these; successful synthetic tests do not certify every account,
microphone driver or future CLI version. The owner should assess audio quality in the local POC.

Provider references: [app-server](https://learn.chatgpt.com/docs/app-server),
[Codex voice](https://learn.chatgpt.com/docs/features/voice),
[Claude dictation](https://code.claude.com/docs/en/voice-dictation).
