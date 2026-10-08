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

Generated probe reports, screenshots and packaged assets remain under ignored build/dist paths.

## Publication

[Release v0.99.92](https://github.com/smikees/armada/releases/tag/v0.99.92) was published
on 2026-10-08T14:43:15Z from commit
`bd719ef6e5385528db40d2ceaa23d1b098ab071f`.

- The enforced publisher passed **3,343 isolated tests with 5 skips** and successful
  Windows CI for this exact commit on pinned Python 3.12.10 and current Python 3.12:
  [CI run 37793094365](https://github.com/smikees/armada/actions/runs/37793094365).
- The compiled launcher passed all **5 interruption recovery checks**, and the branded
  packaged runtime passed all **16 native WebView2 multi-window session checks**.
- The exact signed package passed **63 native upgrade checks** from 0.99.91 to 0.99.92,
  including authenticated real-page navigation, scheduler/restart recovery and cleanup.
- The detached-conversation native regression passed **76 checks**. The released production
  code is identical to the final native-tested code; the last source commit replaces only
  the obsolete portrait test and records that correction.
- Fresh public downloads verified the manifest's Ed25519 signature, all four GitHub asset
  digests/sizes, the local installer digest and all **325 packaged source files** byte for byte.
- The authenticated live update check staged 0.99.92. The existing **0.99.91** process and
  instance nonce were preserved; applying the update awaits the owner's normal restart.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| armada-0.99.92.zip | 5,482,633 | `73e5647be16a71e54f02a3441782bfd8107ab1a6c360858b35741bbd9dba28c9` |
| ARMADA-Setup-0.99.92.exe | 20,431,801 | `cd2975dd6fe55c809890c225975239c6e3983b5f931c15ec5855e2363ecea3c0` |
| armada-update.json | 347 | `6dde156fe0c644b79516d2efd4c1b8e5b6d51fbbed0baa873bb8f36813db9202` |
| armada-update.json.sig | 89 | `bb958a2fe4dcd459857c8ea5e0c351c50e8777c3c9f907d07bc3f9e668d9e4be` |

Generated evidence remains under ignored build paths:
`publish-0.99.92-published.log`, `release-evidence-0.99.92.json`,
`thread-sync-0.99.92-final.json`, `upgrade-0.99.92.json`,
`verification-0.99.92/result.json` and `staging-0.99.92-live.json`.
No user realm or provider turn is used as a release fixture.
