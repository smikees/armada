# 0.99.92 verification

Maintenance release for detached thread divergence and broken Stop. Runtime compatibility is
unchanged. Update manifests remain Ed25519-signed; the installer continues the owner-authorized
unsigned Windows beta distribution. Clean-Sandbox GUI and trusted publisher-signing acceptance
remain outstanding.

## Cause and behavior

The sending page maintained its own optimistic/SSE transcript while other views polled the
persisted render. Polling skipped the sending view and hidden documents, so Markdown, tool
activity, final errors and intermediate progress could disagree or stay stale. Stop used a
cached run ID, ignored failed cancellation responses and disconnected the observing transport
even when the backend continued.

The cockpit, widget and companion now use one canonical conversation observer for live and
terminal content. SSE invalidates that snapshot; it does not create a second transcript.
Realm/thread-scoped BroadcastChannel invalidations accelerate sibling updates, with bounded
polling as the fallback, including occluded documents. Unsaved edits and selected passages
are preserved until they are released. Local drafts and expanded tool details remain local UI
state. Snapshot metrics are shared too.

Stop resolves the conversation by immutable realm, agent and thread at the server. It cancels
only matching owned active turns, supports the legacy run-ID route, retains transport during
cancellation, retries when a local Stop beats admission, and displays failed cancellation for
retry. Once the stream headers confirm server admission, only the snapshot decides busy/idle.
A disconnected transport cannot declare the engine idle, and a stalled transport cannot
keep a completed engine busy. Terminal SSE events release the keep-alive reader. The
observer reconciles durable progress and completion.

## Validation

- The isolated thread-window, chat persistence, execution-contract and HTML snapshot selection
  passed **132 tests**. JavaScript harnesses exercise both production sender and observer together:
  divergent SSE HTML is ignored, hidden views refresh, stale run IDs are tolerated,
  Stop errors are retryable, early Stop survives admission, disconnect preserves busy state,
  stalled transport cannot hold completion busy and terminal errors release their stream.
- The hidden native WebView2 probe passed **76 checks** using a deterministic EngineAdapter through the production
  coordinator, persistence and cancellation paths. No model provider or user realm is used.
  It compares exact live and terminal transcript HTML; cancels from the observing detached,
  sending detached and observing cockpit views; retains realm binding; and exercises
  interrupted transport and close/reopen during a running conversation.
- Release-owned provider preferences were reviewed against the same-day 0.99.91 provider
  verification. They are unchanged; unavailable catalogue picks retain the CLI-default fallback.
- The portrait regression now checks actual admitted-live and completed HTML, preserving
  the complete avatar and color crescent. The old source-text assertion required the removed
  client-side cloning renderer; the full gate correctly withheld that candidate.
- The enforced maintenance publisher must pass the full pinned isolated suite, successful
  Windows CI for the exact source, branded WebView2 session and compiled-launcher recovery
  checks, followed by the exact-package native upgrade gate before publishing.

Publication evidence and final gate counts are recorded after successful publication.
Generated probe reports, screenshots and packaged assets remain under ignored build/dist paths.
