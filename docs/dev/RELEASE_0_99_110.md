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
- Final release gates and public download verification passed, as recorded below.
  Runtime compatibility is unchanged.

The continuing authorized maintenance release uses an unsigned Windows installer and an
Ed25519-signed update. Windows publisher signing and clean-Sandbox acceptance remain unverified.
Publishing does not restart the owner's app. Voice remains an experimental Codex-only preview.

## Publication evidence

Published 2026-10-24 as normal/latest
[v0.99.110](https://github.com/smikees/armada/releases/tag/v0.99.110) from source `c7bf1ebfd35f64891766bfd53e3b532d95c8d9ad` through
`tools/publish_release.py --maintenance-unsigned`.

- Pinned isolated full release gate: **3706 passed, 5 skipped**.
- [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/40099554013) passed before artifact staging.
- Mandatory staged native launcher recovery and WebView2 multi-window session checks passed.
- The native detached-thread synchronization, Stop, sizing and shadow probe passed all 76 checks.
- The bounded UI finish review and documentation handoffs passed after improving recognition-caption contrast. Light/dark caption contrast is approximately 5.79:1 and 7.72:1.
- Signed compatible upgrade from 0.99.109 passed all 69 native checks.
- All four public downloads match their local sizes and SHA-256 values; the update signature
  verifies, and its package contains exactly 429 tracked application files,
  byte for byte. It is the latest normal GitHub release.
- [armada.stamih.com](https://armada.stamih.com/) deployed with certificate-verified FTPS,
  backup, verified temporary upload and rename. Public HTTPS content and installer download
  match the release. Website SHA-256: `44f32feb6114c4e7761a385b2a3fa7dda6a40fc8e180888165d4cc9d75381b8e`.
- Release defaults retain the same-day 0.99.109 provider-catalogue review: each primary release default is listed. Gemini no longer lists the
  secondary 3.7 fallback on this account; existing connected-provider filtering and provider-default
  fallback remain in place. No agent/job model or account settings were changed.
- The owner's running application was not restarted. Windows publisher signing remains pending;
  the maintenance installer is unsigned and the update manifest is Ed25519-signed.

| Public artifact | SHA-256 |
| --- | --- |
| `armada-0.99.110.zip` | `747758af88f34f254d28137e50d2ee03c94bbab91be598ae4af0a56d9a315e1f` |
| `ARMADA-Setup-0.99.110.exe` | `04c71df76cbbd66b0f0b0ac1caf5f51363d368cbd4915eb12e7af4439cca29d9` |
| `armada-update.json` | `74dae01d40869cbec0ab0473c475ede05f46955873c22509b163b9ae8829f343` |
| `armada-update.json.sig` | `85fa7ab77c878e46e21adb8059db284c9f589f0f65ed4e68e9d95cc879e0a60e` |
