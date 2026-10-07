# 2026-10-07: hidden server swallowed desktop launches

Status at incident closure: local installation recovered; preventive source changes were
prepared as v0.99.88. Subsequent publication is tracked in [release verification](RELEASE_0_99_88.md).
Private logs and original launcher files are preserved outside the repository.
Times below are Europe/Madrid. This report intentionally omits personal realm names and paths.

## What happened

The owner opened Settings while trying to obtain the new thread-window feature, saw a browser
error, rebooted, then could not open ARMADA. Launching showed an hourglass and no ARMADA process
remained visible in Task Manager.

The reboot/startup failure is confirmed. An old Windows Startup VBS invoked a custom PowerShell
script that started a development checkout's hidden `armada serve`, an independent scheduler,
and only then `armada app`. It also forced a historical realm instead of the last desktop realm.
That launcher predates the account-wide instance guard added in v0.99.79.

The hidden server acquired the shared account lock. Subsequent desktop launches wrote an
activation request and exited successfully, assuming the existing owner had a window.
Headless `serve` did not watch those requests and had no window to focus. Windows therefore
briefly showed launch activity and the desktop process disappeared. The remaining processes
were Python, not the branded ARMADA executable.

## Evidence and timeline

| Local time | Evidence | Meaning |
|---|---|---|
| 15:40:16 | Restart status acknowledged installed v0.99.87 desktop and scheduler | The earlier signed update completed successfully. |
| 17:59:35 | The old custom launcher ran while an installed desktop was already present | Mixed source/installed launch paths existed before reboot. This does not prove the Settings error's cause. |
| 18:01:05 | `PermissionError` reading the machine configuration | A real access failure occurred. The loader caught it and returned defaults; no matching Settings exception established causation. |
| 18:02:29 | Update state reported current/latest v0.99.87 | The two new features were unpublished source v0.99.88 and could not be obtained through the updater. |
| 18:10:24 | Login script began after reboot | Startup replayed the old launch sequence. |
| 18:10:28 | Script logged server ready, scheduler started, then "window launched" | That last message only meant process creation, not a ready window. |
| Investigation | Instance record had role `serve`, no desktop-ready acknowledgement; authenticated endpoint returned source v0.99.88 | A healthy hidden server owned the account, not a ready desktop. Settings itself returned HTTP 200 during investigation. |
| About 18:26 | Installed v0.99.87 desktop opened in the previous desktop realm; Settings returned 200; scheduler reported running with no recovery error | Local service was restored. |

The Taskbar pin also pointed at `pythonw.exe` instead of the packaged branded executable.
That was corrected, but it was not the lock collision's cause: both entry points hit the same guard.

## What remains unknown

The exact pre-reboot Settings error was not retained and could not be reproduced. Logs contained
browser disconnects and a configuration-access error, but no corresponding `/settings` exception.
Authentication and realm-mismatch refusals previously appeared as raw JSON and lacked navigation
diagnostic references. They remain possibilities, not established explanations. The startup
collision must not be presented as proof of what caused the earlier Settings page failure.

## Recovery performed

1. Backed up the old login script, Startup link, Taskbar pin, account instance/window state and logs.
2. Confirmed no active agent/job run markers before stopping the exact idle legacy server and scheduler.
3. Changed the custom login script to launch the installed `ARMADA.exe -m armada app` only,
   without forcing a realm. It now checks a living desktop-ready owner and shows an error on timeout.
4. Updated the Taskbar pin to the installed branded launcher.
5. Reopened the installed app in its previous desktop realm and verified authenticated Settings,
   desktop readiness and the supervised scheduler.

No realm or conversation data was edited as part of diagnosis. No update was published or
unpublished source copied over the installed package.

## Product changes

- Headless serving stays on a worker thread while the process's main thread can accept desktop
  activation. Promotion keeps the account lock, port, authentication and existing server.
  Runtime role, rather than original `serve` argv, determines restart mode after promotion.
- Duplicate headless launches do not open a window. Concurrent desktop requests converge on
  one owner. An older or unresponsive headless owner produces an actionable launch error.
- Failed native activation preserves the server and records the failure for subsequent launches.
  Early GUI entrypoint errors, including failures before realm resolution, are logged and shown.
- Document failures receive a self-contained recovery page and a reference logged with status,
  route and exception where applicable. Logs omit query strings and credentials. API refusal
  contracts remain unchanged. Recovery navigation drops a stale realm identity.
- Configuration reads retry brief access contention. Mutation uses strict reads and will not
  overwrite unreadable, malformed or non-object configuration with display defaults.
- The native end-to-end check exposed an additional close deadlock: the synchronous WinForms
  closing handler evaluated JavaScript on the same blocked UI thread. Closing now cancels once,
  saves state off-thread, then completes, waiting at most two seconds for state capture.
  This was reproduced in the probe; it is not asserted as the original Settings error.

## Why previous validation missed this

Account-lock tests covered duplicate apps and crash recovery, but not `serve` winning the lock
before `app`. A process launch was treated as success without verifying a window. Existing
browser/session probes created their own windows, so they did not cover the production main
window's close callback. The custom Startup task also lived outside installer-managed launchers.

## Verification and remaining release work

The focused tests exercise a real child server, account locking, concurrent activation, unchanged
authentication, old/unresponsive owners, preserved headless service after GUI failure, early
error reporting, real HTTP recovery responses, config preservation, and bounded close behavior.

`tools/startup_recovery_probe.py` passed all eight checks in actual hidden Windows WebView2:
headless readiness, production desktop bootstrap, preserved owner/port/authentication, Settings
500 recovery, authenticated Home navigation, stale-realm recovery, removal of stale realm context,
and native close with saved window state. It uses an isolated data directory, synthetic HTML,
and no providers, real schedulers, registry changes or personal realms.

Final validation on 2026-10-07: the pinned isolated Windows release gate passed with
**3,302 passed and 5 skipped** (511.02 seconds). The focused startup/recovery/authentication/
restart/logging checks passed **67 tests**. Both intentionally changed golden pages were reviewed:
only the troubleshooting search text and the three release-note entries changed during this fix.

At 18:54, rerunning the repaired Windows login script returned success and reused the same desktop
PID and instance identity. Authenticated Settings returned 200 and the scheduler remained running.
This verified the launch script without interrupting the recovered app.

The existing installed v0.99.87 was recovered by launcher repair. At incident closure, product hardening and both new
features awaited v0.99.88 release validation and publication. A full reboot is a
separate acceptance check; rerunning a login script against a live app is not equivalent to one.
