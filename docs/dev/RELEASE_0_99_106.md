# 0.99.106 — Armada II and quiet desktop readiness

October 11, 2026. Adds the owner's supplied visual direction as a selectable theme, rather
than changing every user's current appearance. Existing themes retain their original palette.

## Implementation

- Theme registry includes Armada II, with natural-width IBM Plex Sans for both font roles,
  a 15 px starting and Ctrl+0 size, and IBM Plex Mono for code, times, counts and paths.
  Self-hosted subset WOFF2 files and the original OFL notices ship with the app.
- Theme selection previews its CSS and starting typography. Save persists the theme's initial
  typography together; subsequent custom fonts and size choices are retained, including
  legacy default faces. Cancel reloads saved preferences. The sample includes all five states.
- Six-pixel control corners, muted status fills, dashed Scheduled outlines and separate
  light/dark palettes. A dedicated running-status token separates job meaning from brand
  accent color. Calendar events, legends, health strips and live system-job updates share
  status attributes. Wider navigation wraps on narrow windows.
- The desktop-ready hook plays the supplied newlocknew MP3 at 12% track volume once per
  process. Windows MCI playback runs in a daemon thread, sets device-specific volume and
  closes the device. Playback failure cannot fail startup. No system volume is changed.
  Headless runs, detached windows, navigation and tray activation do not trigger another cue.
  Settings can disable it for subsequent launches; isolated tests suppress external audio.
- The audio's CC BY-NC 4.0 credit and separate noncommercial restriction are documented
  in THIRD_PARTY_NOTICES.md. Commercial redistribution requires replacement or permission.

## Validation

Browser checks use synthetic data and cover real font loading, 6 px corners, status colors,
dashed Scheduled borders, light/dark/narrow layouts, persistence, custom font overrides and
Cancel. No browser script errors. Native audio device setup is checked without playback.
Release-owned provider preferences were reviewed; availability filtering and provider-default
fallbacks remain intact. Release gates and publication evidence are recorded after completion.

The maintenance beta continues the existing recorded unsigned-installer distribution;
Ed25519 update signing and all application/native upgrade gates remain mandatory.

## Published evidence

- Published October 11, 2026, from `acc69da558433858add4f74c8d0ba3308ec1efdf`:
  https://github.com/smikees/armada/releases/tag/v0.99.106.
- Isolated local release gate: 3,632 passed, 5 skipped. Exact-source Windows CI passed
  both pinned Python 3.12 variants and the PHP relay check:
  https://github.com/smikees/armada/actions/runs/38142844535.
- Native launcher recovery passed all five interruption points; WebView2 passed 16
  multi-window session checks. Packaged upgrade from 0.99.105 passed all 69 real-page,
  restart and cleanup checks against the exact signed candidate.
- Fresh public downloads verified all four asset hashes, the Ed25519 manifest signature,
  the update archive hash, and byte-for-byte contents of all 358 committed app files.
- Installer SHA-256:
  `732f113a09e284879c82090d268344cc9ef04739dced5c40d5a1aa518ae24c7c`.
- https://armada.stamih.com/ updated with a backed-up, certificate-verified FTPS swap;
  public HTTPS page and installer download verified against local release files.
- The owner explicitly approved publishing this unsigned Windows beta installer and
  signed update. No owner app restart was required to publish.

The first full-suite run exposed a test assumption that all bundled fonts are selectable
body fonts. IBM Plex Mono is intentionally bundled only for data/code, and already had
its correct attribution and OFL notice. The test now resolves that family separately,
while continuing to require attribution and the original license for every bundled font.
