# 0.99.112 verification

The owner reported text results without spoken replies after 0.99.111. Short baseline tests
played audio in Chrome and WebView2; the exact reported instance was not reproduced. The prior
proof checked transcript text and an unmuted element, without measuring audio at the output.
This change hardens playback and makes any missing output visible and recoverable.

## Changes

- Unlock AudioContext inside the initiating click and route remote speech through a gain-controlled
  output analyser. Keep a permanently muted media sink attached: a real WebView2 test showed that
  removing it stopped remote audio samples. Unsolicited native speech remains silent and unsaved.
- Retire a saved reply only after transcript completion and measured audio drain, replacing the
  two-second transcript timer. Paused or missing audio exposes Enable sound. Retry is scoped to the
  current saved reply; it never executes the underlying agent request again.
- Voice chat and Dictation share the same microphone/peer and normal task runner. Mode switching
  preserves input and work; Dictation drops spoken output and returns text. Switching back affects
  subsequent results without replaying earlier text-only answers. This explicitly replaces the old
  draft-only Dictate behavior; typed drafts remain unchanged.
- Connecting copy describes enabling the selected mode. Permission copy appears only for a reported
  microphone permission prompt; denied access and disconnected devices have explicit recovery.

## Validation

- Real Codex CLI with synthetic audio in native WebView2: voice → dictation → voice, one input stream
  and one peer, six saved messages and no JS errors. Post-gain signal sample counts were 16 / 0 / 16.
  No owner microphone or conversation was recorded.
- Focused tests cover mode admission, retained partial speech, no historical replay, readback drain,
  scoped retry and failure isolation. The browser harness covers output gating, paused sound,
  missing audio, permission cancellation, muted switching and independent work lifetime.
- All twelve UI captures cover connecting/voice/dictation in main 1280×900 and detached 480×760
  views, light/dark, without overflow. Fresh finish reviewer disposition: ship, no material fixes.
- Final release gates and public download verification passed, as recorded below.
  Runtime compatibility is unchanged.

Voice remains experimental. Measuring signal at the app output does not prove the user's chosen
Windows output device is audible or unmuted. The approved maintenance installer is unsigned;
the compatible update remains Ed25519-signed. Publishing does not restart the owner's app.

## Publication evidence

Published 2026-10-24 as normal/latest
[v0.99.112](https://github.com/smikees/armada/releases/tag/v0.99.112) from source `8f76954415491165ceacf2376008a86d17207252` through
`tools/publish_release.py --maintenance-unsigned`.

- Pinned isolated full release gate: **3726 passed, 5 skipped**.
- [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/40108968422) passed before artifact staging.
- Mandatory staged native launcher recovery and WebView2 multi-window session checks passed.
- The native detached-thread synchronization, Stop, sizing and shadow probe passed all 76 checks.
- The bounded UI finish review and documentation handoffs passed for connecting, voice and dictation states in main/detached light and dark views.
- Signed compatible upgrade from 0.99.111 passed all 69 native checks.
- All four public downloads match their local sizes and SHA-256 values; the update signature
  verifies, and its package contains exactly 430 tracked application files,
  byte for byte. It is the latest normal GitHub release.
- [armada.stamih.com](https://armada.stamih.com/) deployed with certificate-verified FTPS,
  backup, verified temporary upload and rename. Public HTTPS content and installer download
  match the release. Website SHA-256: `8a2d02fccdfcc147812dab0036dc8c61cc5ff61fb5be55ea59541b760e69d9f8`.
- Release defaults retain the same-day 0.99.111 provider-catalogue review: each primary release default is listed. Gemini no longer lists the
  secondary 3.7 fallback on this account; existing connected-provider filtering and provider-default
  fallback remain in place. No agent/job model or account settings were changed.
- The owner's running application was not restarted. Windows publisher signing remains pending;
  the maintenance installer is unsigned and the update manifest is Ed25519-signed.

| Public artifact | SHA-256 |
| --- | --- |
| `armada-0.99.112.zip` | `091c55e942bf3819f930f4e29c86926424b5059a8bd9a1424d1d33e5b1faaaec` |
| `ARMADA-Setup-0.99.112.exe` | `a84dee6cfe94d236a1f563e90a01d7d58d75da43b91ede301ee2b466a6c7df53` |
| `armada-update.json` | `e731b68e6ca59d5429f3ce2e2c15f77ccdfca4a34b0662db5dc6333061d7c2dd` |
| `armada-update.json.sig` | `894af13942d651fecfde266787290ad83cc5dd90987b8774ed694af8fbeaa6e9` |
