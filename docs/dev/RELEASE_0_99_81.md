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
verification results are recorded below after completion.

## Distribution boundaries

The stable bootstrap and runtime are unchanged, preserving compatible package updates.
This is an owner-authorized unsigned maintenance beta. Authenticode and clean-Sandbox GUI
acceptance remain unverified; Windows Application Control error 4551 is not resolved. The native
browser gate covers session behavior, not a complete clean-machine installer/user-flow acceptance.
No live job, realm or running desktop was modified to publish this release.
