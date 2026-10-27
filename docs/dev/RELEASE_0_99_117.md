# 0.99.117 — Close-to-tray lifecycle hardening

## Investigation and limits

The owner reported a white main window that could not be moved or closed after
closing to the tray. The installed 0.99.116 log showed successful startup and no
corresponding application crash. During initial inspection the actual main HWND
was hidden and answered a bounded Windows message probe immediately. Ordinary
close/restore cycles on the previous implementation also passed. The exact visible
white-window freeze has **not** been reproduced, and this release does not claim
a proven cause for every white-window failure.

Code inspection found independently scheduled save/hide operations with no ordering
against restore. Tray actions synchronously called another STA's window methods;
delayed minimize notifications could also override a restore. These are concrete
lifecycle hazards, addressed and tested below. Previously the native startup probe
disabled the tray entirely, leaving this behavior outside the release gate.

## Changes

- `DesktopVisibility` posts native operations with `BeginInvoke`, allowing the
  synchronous FormClosing callback to finish cancellation first. Generation checks
  discard superseded work; main-window activation and companion navigation share it.
- State capture runs away from both UI loops, waits at most 400 ms before hiding,
  and permits only one outstanding snapshot. A stalled renderer cannot hold up a
  tray hide. Normal saves retain the route, draft and geometry; the existing bounded
  full-quit save remains in place.
- Minimize notifications recheck native window state on the UI thread. Restore
  shows the hidden form before normalizing a minimized state, preserving maximized
  windows. Quit invalidates pending visibility work.
- Tray callbacks dispatch away from the notification icon's STA. Tray shutdown is
  posted to its own native dispatcher, which is disposed with the icon.
- Diagnostic logs identify requested/applied transitions, delays and failed saves
  without including draft content or credentials.
- Installer staging now requires a native tray lifecycle check using its packaged
  runtime. It exercises actual Open/Quit menu handlers, repeated WM_CLOSE/restore,
  minimize, a stalled snapshot, busy WebView2, draft preservation and native teardown.

## Validation

- Nine focused concurrency regression tests pass. The related desktop, startup and
  detached-window tests passed before the final minimize guard; the full release
  gate covers the final source.
- The native source probe checks startup/authentication recovery as well as the
  tray lifecycle. Its watchdog now covers teardown, not only the test controller.
- Provider metadata confirms current preferred Claude/Codex models and Gemini
  3.8 Flash. The older absent Gemini fallback remains filtered; no defaults changed.
- Release gates and public publication evidence will be recorded after they complete.

Publication does not restart the owner's running application. The authorized beta
installer remains unsigned; compatible update manifests are Ed25519-signed.
