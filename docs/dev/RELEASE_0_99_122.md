# 0.99.122 — Close the desktop before update handover

On November 4, 2026, the owner reported an immovable, always-on-top white ARMADA
rectangle after updating to 0.99.121. The update monitor had verified the successor
desktop and scheduler. Native inspection found one responsive but hidden main form;
a scan of 310 top-level and child windows found no visible ARMADA or Ghost window
corresponding to the rectangle. The owner confirmed it remained on screen.

The Windows graphics-refresh shortcut did not remove it. With the owner's explicit
approval after saving work, restarting only the current session's Desktop Window
Manager cleared the surface. Windows created a replacement compositor, and the
owner confirmed the rectangle disappeared without rebooting. ARMADA was not restarted
for this recovery. This confirms compositor recovery works for this occurrence; it
does not prove the original compositor failure or a particular driver defect.

## Repair

The installed update path called `os._exit()` from the HTTP restart thread while
WinForms and WebView2 were still alive. Unmonitored desktop restarts similarly
replaced the process before native teardown. This is a concrete lifecycle defect,
even though the persistent compositor artifact has not been reproduced synthetically.

Both desktop paths now close companion windows and the main form normally, bypass
close-to-tray cancellation, and hide the main surface before its final close. The
restart continuation runs on the main thread after the GUI loop and tray stop;
only then are listeners released. Monitored updates return normally through CLI
and installation-lease cleanup. Their supervisor still waits for process exit and
verifies successor version, desktop and scheduler. There is no forced-exit fallback
for a hung desktop. Its existing monitor timeout remains available for diagnosis.

Update preparation uses the same bounded state snapshot as full Quit. A stalled
renderer cannot hold this step forever, and restart does not request a second
JavaScript snapshot while native controls are closing. A timed-out snapshot may
retain previously saved state; the diagnostic log records that limitation.

## Validation and scope

Focused tests cover deferred listener release/replacement, normal monitored exit,
continuation ordering, bounded state capture and the existing restart/tray contracts.
Native source checks passed visible, hidden-to-tray and infinite-JavaScript-renderer
restart cases. Each checks disposed native form and browser control, vanished HWND,
stopped tray, browser process exit and main-thread continuation. These cases are now
mandatory installer staging gates. The signed previous-release upgrade probe now
uses the normal `keep_in_tray=True` setting.

All tests use synthetic profiles and realms. No owner app restart or live realm
mutation is used for validation. The earlier 0.99.117 incident remains historical;
this occurrence has an owner-confirmed recovery, while prevention is tested at the
native lifecycle boundary rather than claimed as a reproduction of the DWM fault.
Provider defaults retain the November 4 metadata review from 0.99.121. The bundled
Python security review and maintenance beta signing boundaries also remain unchanged.
Update assets are signed; Windows publisher signing remains the documented limitation.

## Publication evidence — November 4, 2026

Published [v0.99.122](https://github.com/smikees/armada/releases/tag/v0.99.122)
from `397e4403ec2ac1e054f779bbba8ae15baeffc49e` using the unified maintenance
publisher. Both local full-suite runs passed **3,915 tests with 5 skipped**, including
the publisher's exact-commit run. [Windows CI](https://github.com/smikees/armada/actions/runs/41881039626)
passed both Python versions and the relay job.

The packaged gates passed all five launcher recovery interruption points, 16
WebView2 session checks, 68 tray checks, and 69 checks in each of the visible, tray
and busy-renderer restart cases. The signed upgrade rehearsal passed 72 checks,
including the candidate's actual HTTP restart through native disposal to an
intercepted process-replacement boundary. Native probes require browser process
exit within five seconds of control teardown. The production process is never
forcibly killed to satisfy that check.

All four public assets were downloaded and matched to the tested build. The update
signature, manifest commit and all 446 packaged source files were verified. Installer
SHA-256: `a9172a8e0640cf422fbbff67d286ae6cd563ebf4acf0195f1c3c1ae8a54f8c75`.
Evidence remains outside source control in `build/release-evidence-0.99.122.json`,
`build/upgrade-0.99.122.json` and the staged native restart reports.

The website's final HTML upload initially timed out during verification. An index-only
retry through the same certificate-validated FTPS deployer preserved backups and
verified the temporary file before renaming it. Public HTTPS then matched the source
apart from the known hosting script, and its installer link returned the exact tested
bytes. Both GitHub and armada.stamih.com now publish 0.99.122.

The owner's desktop and scheduler remained healthy on 0.99.121 after compositor
recovery; no owner app restart was performed for testing or publication. For the
first installation of this fix, Quit from the tray before running the 0.99.122
installer, avoiding the old version's abrupt update shutdown path.
