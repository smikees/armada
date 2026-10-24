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
- Final full suite, exact-source CI, native recovery/session/upgrade and public asset/website
  verification must pass before publication completes. Runtime compatibility is unchanged.

Voice remains experimental. Measuring signal at the app output does not prove the user's chosen
Windows output device is audible or unmuted. The approved maintenance installer is unsigned;
the compatible update remains Ed25519-signed. Publishing does not restart the owner's app.
