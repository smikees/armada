# ARMADA 0.99.81 verification

## Desktop session regression

pywebview starts in private mode by default. Its WebView2 adapter deletes all cookies in the
shared profile whenever a window initializes. Opening Alexander therefore removed the main
cockpit's local-session cookie too. Alexander opened a protected URL without re-authentication,
and subsequent Usage refreshes also returned HTTP 401. The message did not describe a closed
app or an engine sign-in failure.

The desktop now explicitly shares a persistent, owner-only profile beneath the protected local
authentication directory, with private mode disabled. Every native companion enters through the
private fragment bootstrap. Server credentials still rotate on launch; public pages do not
disclose them, and origin checks, HttpOnly cookies and workspace authorization remain enforced.
Support payloads wait through the authentication redirect until the companion's receiver exists,
then deliver once. Browser preferences can persist across desktop restarts in this profile.

## Verification

The old behavior was reproduced with the actual branded embedded runtime and Windows WebView2:
the main Usage request initially returned 200, then both companion and main returned 401 after
companion initialization. The corrected production opener passed 14 hidden browser checks,
including two companion open/close cycles, Usage in both windows, payload delivery exactly once,
main navigation, fragment removal and rejection of credential-free authentication requests.

Installer staging now requires this real-browser gate, using its own staged runtime and synthetic
HTTP fixtures in an isolated data directory. It makes no model calls or changes to live realms.
Focused HTTP/lifecycle tests additionally cover authentication redirects, protected profile
placement, link rejection, cookie validation and origin restrictions. Full-suite and release
verification results are recorded below.

The final isolated suite passed: **3,111 passed, five skipped**. A final focused pass of
51 HTTP, lifecycle, startup and logging checks also passed, including assertions that the
production main-window startup forwards the protected profile configuration. The packaged
installer passed all 14 native WebView2 checks and all five interrupted-update recovery probes.
The only page snapshot change was the new changelog entry; generated references are current.

## Distribution boundaries

The stable bootstrap and runtime are unchanged, preserving compatible package updates.
This is an owner-authorized unsigned maintenance beta. Authenticode and clean-Sandbox GUI
acceptance remain unverified; Windows Application Control error 4551 is not resolved. The native
browser gate covers session behavior, not a complete clean-machine installer/user-flow acceptance.
No live job, realm or running desktop was modified to publish this release.

## Published metadata

[Exact-source Windows/PHP CI](https://github.com/smikees/armada/actions/runs/37305110091)
passed on Python 3.12.10 and current 3.12, plus the PHP report relay. Documentation/reference
checks passed (123 tests). The public latest-release manifest signature, source commit, runtime,
ZIP size/hash and installer hash were verified after publication.

Release: [v0.99.81](https://github.com/smikees/armada/releases/tag/v0.99.81).
Installer and update source: `d9580128177690ff9f20d2e886e751efeb7de7a5`.
Runtime: `py3.12-abe4061a3fa70426`.
Installer SHA-256: `48d49b0bb5cf6cc8483dde287b1c5a5a36e21428c501c1ab68d20c293f508303`.
Update ZIP SHA-256: `ad74430021ec5fc93e752c7a15246ed0efc0f7d7691b5d386f996986e131fdd5`.

The website index was published through certificate-validated FTPS, backing up its previous
copy. Its live HTTPS version and installer link were verified; the report relay and other files
were unchanged. GitHub About metadata continues to present all three providers equally.
Subsequent repository edits record verification and strengthen the startup configuration guard;
the packaged app code remains the exact validated source above.
