# 0.99.117 — Close-to-tray lifecycle hardening

## Investigation and limits

The owner reported a white main window that could not be moved or closed after
closing to the tray. The installed 0.99.116 log showed successful startup and no
corresponding application crash. During initial inspection the actual main HWND
was hidden and answered a bounded Windows message probe immediately. Ordinary
close/restore cycles on the previous implementation also passed. The exact visible
white-window freeze has **not** been reproduced, and this release does not claim
a proven cause for every white-window failure. The owner subsequently confirmed that
the blank view was still visible. A later process and desktop inventory found no
running installed ARMADA instance, with an intervening startup recorded in its log;
no frozen-window dump was available to establish the original blocking call.

Code inspection found independently scheduled save/hide operations with no ordering
against restore. Tray actions synchronously called another STA's window methods;
delayed minimize notifications could also override a restore. These are concrete
lifecycle hazards, addressed and tested below. Previously the native startup probe
disabled the tray entirely, leaving this behavior outside the release gate.

## Follow-up: persistent surface after the app exited

The owner confirmed the rectangle persisted. A direct pointer hit test, repeated
with physical/DPI-aware coordinates, identified Task Manager underneath the blank
area. A fresh window capture showed the white rounded rectangle drawn over it.
The installed ARMADA process was absent. A wider scan of 446 native windows,
including desktop child windows, found no ARMADA or Ghost HWND covering that area.
No matching ARMADA, WebView2 or compositor crash was found in the recent event log.

This makes a stale desktop composition surface the leading explanation for the
persistent rectangle, rather than an extant ARMADA window awaiting a close event.
It does not establish whether ARMADA originally triggered it, nor prove a driver
fault. An automated Windows graphics-refresh shortcut did not visibly clear the
surface in subsequent captures; owner confirmation of a manual refresh is pending.
The visible incident therefore remains unresolved despite the verified tray fixes.

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
- Final release gates and public download verification passed, as recorded below.

Publication does not restart the owner's running application. The authorized beta
installer remains unsigned; compatible update manifests are Ed25519-signed.

## Publication evidence

Published 2026-10-27 as normal/latest
[v0.99.117](https://github.com/smikees/armada/releases/tag/v0.99.117) from source `d90ac80fdf0da40a437f53a71467cd46da7f5d9b` through
`tools/publish_release.py --maintenance-unsigned`.

- Pinned isolated full release gate: **3767 passed, 5 skipped**.
- [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/40565856088) passed before artifact staging.
- Mandatory staged native launcher recovery and WebView2 multi-window session checks passed.
- The new packaged tray lifecycle/startup gate passed all 60 checks, including
  Open/Quit on the actual tray STA, delayed saves, busy WebView2, saved drafts and shutdown.
- Signed compatible upgrade from 0.99.116 passed all 69 native checks.
- All four public downloads match their local sizes and SHA-256 values. The update signature
  verifies, and its package contains exactly 435 tracked application
  files, byte for byte. It is the latest normal GitHub release.
- [armada.stamih.com](https://armada.stamih.com/) deployed with certificate-verified FTPS,
  backup, verified temporary upload and rename. Public HTTPS content and installer download
  match the release. Website SHA-256: `dd73a73623246a3f1fc37c378649b41ee66b11be96ae3d55f178f8c82ace702d`.
- The release process did not restart the owner's application. The maintenance installer remains unsigned;
  the compatible update manifest is Ed25519-signed.

| Public artifact | SHA-256 |
| --- | --- |
| `armada-0.99.117.zip` | `6498b2b5e94cf4b99e0a2066caa88fcb6f770fe849992a6295ee56b7a4dcefae` |
| `ARMADA-Setup-0.99.117.exe` | `81ec9dc11a638b377e92a453b6aab62e7988349035f52d1b26de5f00105b3393` |
| `armada-update.json` | `e0448228aaa5d77e5461ed697c36f1c8edb02dbe746632e0a38033001f8e899d` |
| `armada-update.json.sig` | `a828aab59cc81c7c09f3bbd29e3fbd5a4eb3e8fbaccc4c57567b65acec08a104` |
