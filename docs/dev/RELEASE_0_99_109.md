# 0.99.109 verification

This release adds the owner's requested Codex voice proof of concept and fixes shared thread
rendering and interaction problems. It preserves the normal typed-message execution path.

## Changes

- Separate Dictate and Voice chat composer controls in the app and detached windows. Dictate
  inserts an editable unsent draft at the original selection; Done finalizes it and Cancel
  discards it. Voice chat plays replies with Mute and End controls and shares final transcripts
  through the existing Thread store. Codex CLI 0.157.1's actual experimental WebRTC V3 protocol
  was exercised with synthetic speech. Both modes consume voice usage, not a separate local
  transcription service. Other providers are not silently switched to Codex.
- Native voice sessions are owned by RunSession, use an empty read-only workspace, exclude
  tools/connectors/actions and reject approval requests. Scoped authenticated signaling,
  single microphone ownership, leases, timeouts and process cancellation bound the lifecycle.
  Dictation receives no thread history or agent profile. Its draft is owner-only and in memory;
  assistant audio/text is discarded. Voice transcripts persist; raw audio and SDP do not.
- Bundled KaTeX renders inline and display math after protected Markdown parsing. Trust is
  disabled; code and literal text remain escaped. Third-party license notices are included.
- User message rendering preserves line breaks and recognizes Unicode bullets without changing
  ordinary document wrapping. Main, detached and streamed views use the same renderer.
- Existing sidebar rows receive live plain-text previews without replacing open menus or rename
  controls. All menu actions are native buttons with shared hover and keyboard-focus styling;
  Delete keeps its danger color and existing shortcuts remain available.

## Validation before packaging

- Full pinned isolated implementation suite: **3,700 passed, 5 skipped**.
- Focused rendering, voice ownership, cancellation, draft and thread tests: **59 passed**.
- Real browser/native synthetic audio checks: dictation without playback or auto-send, draft
  preservation, remote Cancel, voice playback, Mute, shared transcript and microphone cleanup.
- Native detached-thread probe: **76 checks passed**.
- Light/dark and narrow/main-window screenshots reviewed; UI finish review disposition: ship.
- Actual microphone quality and future experimental provider compatibility remain limitations;
  this is an explicitly labelled voice preview. See [protocol and evidence](VOICE_POC.md).

Publication follows the continuing owner-authorized unsigned Windows beta maintenance path.
The update is Ed25519-signed; Windows publisher signing and clean-Sandbox acceptance remain
unverified. Exact-source full tests/Windows CI, staged native session/recovery, signed packaged
upgrade and public website/download verification remain mandatory. Publishing does not restart
the owner's running app. Final evidence is recorded after the enforced release succeeds.
