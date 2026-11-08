# Immediate page-navigation feedback

8 November 2026, 0.99.135. A menu click must acknowledge the destination before
server rendering finishes. Artefacts made the gap obvious: `_gather_artifacts`
reads thread messages and checks referenced files before the full page is returned.
Until now the outgoing page and selected tab remained unchanged throughout that wait.

## Research and choice

The relevant latency is click-to-visible-feedback, separately from content-ready
time. [Chrome's INP guidance](https://web.dev/articles/inp) recommends prompt visual
feedback for interactions. A native document-navigation observer fits ARMADA's
server-rendered architecture: the [Navigation API](https://developer.mozilla.org/en-US/docs/Web/API/Navigation/navigate_event)
reports navigation starting without requiring interception. Browser history can
restore the outgoing document, so cleanup also handles
[pageshow](https://developer.mozilla.org/en-US/docs/Web/API/Window/pageshow_event).

The chosen solution paints the selected destination and a loading view immediately,
then lets the browser complete its normal navigation. It needs no SPA router,
HTML reinjection, speculative file/history scans, or new authorization cache.
Those larger changes would add lifecycle and state risks without being necessary
to acknowledge this click. This does not claim that large Artefacts lists now
finish gathering instantly.

## Behavior and boundaries

- The shared navigation controller runs on existing first-party pages. It observes
  same-origin application page navigations, including primary menus, agent tabs
  and custom sections. The Navigation API also covers supported programmatic and
  back/forward navigation. Older browsers get ordinary-link and custom-section
  feedback as a fallback.
- The destination tab becomes selected and the content area shows its title and
  “Loading page…”. Other menu items remain available. A later selection supersedes
  the earlier navigation using the browser's normal cancellation behavior.
- The old content remains in the DOM, hidden/inert and held at its existing size;
  its scroll geometry, fields, filters and drafts remain available to existing
  pagehide persistence. A sibling loading view uses normal flex layout, so it
  stays below a menu that wraps onto two rows. Cancelling restores the original
  styles, accessibility state and selected tab.
- After eight seconds, “Stay on this page” stops the pending browser navigation
  and restores the outgoing page. Aborted navigation and pagehide/pageshow also
  clean up the loading state. This cannot cancel work already executing on the
  server; the operation being observed is a page read, not an action replay.
- Downloads, external destinations, mutation/action endpoints, same-document
  changes and native form submissions are excluded. The older-browser click
  fallback also excludes modified clicks, new-window targets and prevented events.
  Existing realm binding, authentication, redirects and browser history are unchanged.
- The loading label is a live status, the old content is marked busy/inert, and
  the spinner respects reduced-motion preferences. No fake percentage is shown.
  The renderer must be responsive to paint feedback; this does not repair a hung
  browser process or remove server/file I/O limits.

## Verification

`python tools/navigation_probe.py --output build/navigation.json` starts only an
isolated synthetic realm and WebView2 profile. It holds the Artefacts response,
checks loading feedback before releasing it, and exercises slow-load cancellation,
retained fields/scroll, rapid menu changes, completed navigation and Back.
`--baseline` disables only the new controller to compare the prior behavior.

The probe uses an authenticated loopback test bridge driven by the outgoing page.
This is deliberate: WebView2's [ExecuteScriptAsync contract](https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.core.corewebview2.executescriptasync)
targets the destination document once navigation starts, so using it to inspect
the outgoing document would accidentally wait until the delay had ended. Test
bridge endpoints exist only in the probe subclass, never in the application.

Reported timing is click-to-visible DOM state measured within the native browser,
not physical monitor latency or a whole-session INP score. The acceptance ceiling
is 100ms with the response still held. Light/wide and dark/1024px captures render
the native DOM in headless Chromium. JavaScript behavior tests cover excluded
navigations and the older-browser fallback. Native page-work and shared-window
checks cover presentation-state and conversation regressions.
