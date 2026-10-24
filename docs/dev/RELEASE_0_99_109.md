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

## Publication evidence

Published 2026-10-24 as normal/latest
[v0.99.109](https://github.com/smikees/armada/releases/tag/v0.99.109) from source `277f9dc8adc84f6c0e87e4248e34fbc918afa46d` through
`tools/publish_release.py --maintenance-unsigned`.

- Pinned isolated full release gate: **3702 passed, 5 skipped**.
- [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/40095275917) passed before artifact staging.
- Mandatory staged native launcher recovery and WebView2 multi-window session checks passed.
- Signed compatible upgrade from 0.99.108 passed all 69 native checks.
- All four public downloads match their local sizes and SHA-256 values; the update signature
  verifies, and its package contains exactly 429 tracked application files,
  byte for byte. It is the latest normal GitHub release.
- [armada.stamih.com](https://armada.stamih.com/) deployed with certificate-verified FTPS,
  backup, verified temporary upload and rename. Public HTTPS content and installer download
  match the release. Website SHA-256: `64df5579cc180123b822179e4734e789604bdde26630527ee915da7d353ddc70`.
- Provider catalogues still list each primary release default. Gemini no longer lists the
  secondary 3.7 fallback on this account; existing connected-provider filtering and provider-default
  fallback remain in place. No agent/job model or account settings were changed.
- The owner's running application was not restarted. Windows publisher signing remains pending;
  the maintenance installer is unsigned and the update manifest is Ed25519-signed.

| Public artifact | SHA-256 |
| --- | --- |
| `armada-0.99.109.zip` | `4472e50cbba7afd575a08c584d21411bd0225bb29588b3c4417ae69087a75480` |
| `ARMADA-Setup-0.99.109.exe` | `9b0dd8f1e7543ff54799cd75099e77c4ea961a6434ba93556939e8fd12953627` |
| `armada-update.json` | `3dff4bcc95f7ce662123b87e72397ef099ea258af9d6fa2edfd4fbef27cad2be` |
| `armada-update.json.sig` | `b3c51e583011710d2934e4bd4b8a5cb6f541d9de35872a0bde1a5041dae1afd8` |
