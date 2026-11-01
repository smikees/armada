# 0.99.119 — Keep desktop navigation in ARMADA

## Incident and evidence

On November 1, a normal click on Agents after restoring the long-running app
opened a loopback URL in Chrome and displayed the local-session refusal page.
The server log records HTTP 401 for that request, three seconds after a tray
restore. The same server had been running since October 30. There is no elapsed
time expiry in the local session implementation; the evidence does not support
an overnight session timeout or an application restart.

Chrome and WebView2 have separate cookie profiles. A raw app URL in Chrome cannot
authenticate, even while ARMADA is open. The shipped pywebview popup handler
delegates every new-window URL to the system browser, including local app URLs.
The old log did not record native popup events or the requesting browser. We can
reproduce that unsafe handoff with a new-window link, but cannot prove what made
the reported ordinary click request a new window. Do not describe this as a
confirmed modifier-key click or blame the user.

There was a second recovery gap: automatic reauthentication was limited to the
startup loader. Losing a WebView cookie later left the desktop on a refusal page.

## Changes

- A native navigation policy handles local popups in the existing authenticated
  WebView. It preserves the route, realm query and fragment. External links and
  provider sign-in keep the existing system-browser behavior.
- Both the top-level page and originating frame must belong to the exact app
  origin. Sandboxed content routes, other ports, lookalike hosts and unknown
  source frames cannot promote a popup into the privileged app. No token is
  handed to the system browser.
- A document-level 401 after startup can bootstrap the private session again and
  return to the requested route. A 30-second retry guard prevents loops. API
  requests and actions are not replayed. Cross-origin checks remain unchanged.
- The refusal screen tells users to switch to the ARMADA window. Its old
  “Return to ARMADA” link only retried the same unauthenticated browser session;
  that misleading button is removed for 401 responses.
- Diagnostics distinguish browser families and whether credentials were present,
  and record intercepted local popup paths and whether WebView reports a user
  gesture. Queries, fragments, cookie values and authorization headers are not
  logged.

The native policy uses the documented
[WebView2 new-window event and source-frame information](https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.core.corewebview2newwindowrequestedeventargs).
It is installed before window creation and applies to main and companion windows.

## Validation

Unit checks cover exact-origin matching, untrusted/unknown frame refusal, normal
external links, lost-cookie recovery, retry bounds, and exclusion of API actions.
Real HTTP checks verify recovery-page content and credential-free diagnostics.

The hidden native startup probe exercises ordinary navigation, an actual WebView2
new-window link, the external-browser handler, and deletion of the real HttpOnly
cookie after startup. It verifies that the destination and authentication recover
without restarting the server. Existing Settings-error, stale-realm, tray and
shutdown checks remain in the probe. Synthetic fixtures use isolated profiles and
never contact a provider or operate on the owner's jobs.

Publication evidence is recorded after the enforced release gates complete.

## Single-instance verification

The existing lifetime lock permits one desktop/server owner per Windows account,
independent of realm, port, working directory and configured data directory. Its
location is resolved from the Windows access token's profile rather than mutable
environment variables. The OS releases the lock on process exit or crash; a
second launch activates the existing owner instead of taking over its listener or
authentication. A headless owner can open its desktop in the same process.

Existing process tests exercise concurrent launches, mixed app/server requests,
crash recovery and concurrent activation. An additional process regression in this
release uses two working/data directories and two ports against one account lock,
then verifies the owner record stays unchanged and the duplicate requests
activation. The running installation was also checked: one desktop and its
scheduler child. Scheduler, WebView2 and agent CLI helper processes are not
additional app instances.
