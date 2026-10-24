# 0.99.110 verification

The owner reported that voice connected, briefly replied, then ended with an action error.
ARMADA incorrectly treated every native `turn/started` as a tool action. The protocol's
`clientManagedHandoffs` setting governs backend response forwarding, not incoming delegation.

## Changes

- Admit thread-scoped reasoning turns under the existing disabled-tool/read-only configuration,
  return their replies to voice, and retain rejection of external tool items and approval requests.
  Backend-specific context distinguishes answering a delegated question from launching an agent.
  Dictation keeps separate instructions. Ambient completion notifications are disabled.
- Measure actual microphone input locally with Web Audio, with quiet, detected-sound and muted
  states. Recognition is independently demonstrated by live text. End closes the analyser and
  AudioContext and clears its timer; there is no synthetic listening animation or audio recording.
- Render provisional native speech in the canonical shared thread view. Final speech replaces
  the preview without duplicating saved messages. On interruption, remaining native text is
  retained with an explicit incomplete-transcription label. Live/incomplete assistant speech
  never displays Done. Unsent dictation remains private and is never saved by this mechanism.

## Validation

- Focused voice, rendering and synchronization regressions: **61 passed**.
- Real Codex CLI with synthetic speech: connected, displayed live recognized text in both views,
  performed an actual voice-to-reasoning handoff, spoke the calculated answer, stayed connected,
  measured input, zeroed the meter when muted, and retained every segment after reload.
- The reload assertion trims presentation whitespace, as the normal message renderer does;
  the original native transcript remains saved unchanged. No owner microphone was recorded.
- Light/dark main and narrow detached captures reviewed against the incumbent UI.
- Final full suite, exact-source CI, native recovery/session/upgrade and public asset/website
  verification must pass before publication completes. Runtime compatibility is unchanged.

The continuing authorized maintenance release uses an unsigned Windows installer and an
Ed25519-signed update. Windows publisher signing and clean-Sandbox acceptance remain unverified.
Publishing does not restart the owner's app. Voice remains an experimental Codex-only preview.
