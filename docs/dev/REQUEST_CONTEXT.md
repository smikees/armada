# Request and run identity

The selected realm is a default for new requests, not a destination that running work looks up
again. `request_context.RealmContext` is frozen and contains a canonical root and a stable ID
(the first 32 hexadecimal characters of SHA-256 over the resolved, OS-normalized folder path).
Moving a realm changes its ID. These IDs prevent accidental retargeting; they are not credentials
or an authorization boundary against code running as the owner.

## HTTP admission

`Handler._bind_request` captures selection under `SELECTION_LOCK` on every request, including
reused connections. The handler's instance `realm` shadows the mutable class default. Request
body reads happen before taking the selection lock. A later `/switch` cannot change the root
used by an admitted handler or its response rendering.

Trusted pages contain an `armada-realm` meta tag and load `realm-context.js` before other scripts.
The script captures that value once, adds `X-Armada-Realm` to same-origin app fetches, and binds
forms and navigation links. Explicit `/switch` links remain selection actions. Realm-scoped
POSTs require an identity; clients may also supply `_realm` in the query or JSON body. Conflicting
identities, missing mutation identities, and identities different from the current selection
return HTTP 409 with `code: realm_mismatch`. The browser surfaces the message and rejects the
fetch, so chained operations do not continue after a stale save. Polling from stale pages is
also rejected. Reload the page before editing the newly selected realm.

Welcome/create-realm, CLI sign-in/install, and restart/update endpoints may omit identity because
they do not operate on an existing realm. A supplied mismatching identity is still rejected.
Host, Origin, Fetch Metadata, schema-version and path-confinement checks remain in force.

## Content and notifications

Read-only content can explicitly name a previously selected realm. Resolution accepts only known
or registered realm roots; the client cannot submit a filesystem path as an identity. Uploaded
images, thread attachments and embeds carry `_realm`; mini-sites use
`/r/<realm-id>/section-raw/<index>` and `/r/<realm-id>/section-asset/<index>/...`. Their injected
`base` URL keeps relative scripts, styles and data in the same realm across selection changes.
Unbound content requests fail closed. The content server still has no mutation APIs, and app-origin
fallback content retains its sandbox policy.

Trusted markup attributes are bound during response rendering, without modifying script text or
untrusted documents. Portraits embedded in script data carry identity at their renderer; dynamic
dashboard embeds use `mcRealmUrl`. New dynamic content URLs must do the same. Notification feed
links explicitly select their source realm, then open an identity-bound destination. Stored
notification records keep their existing format.

## Runs and cancellation

`RunContext` adds agent, thread and run ID to the frozen realm context. Chat streaming checks this
context against its arguments before invoking an engine. Completion, title generation, unread
updates, artifact capture and normal run telemetry use the captured destination. Non-streaming
chat and agent jobs also capture context for their execution and telemetry.

The active chat registry is locked and keyed by `(realm_id, run_id)`. Duplicate active IDs in one
realm are refused; identical IDs in different realms are independent. Each run owns an activity
marker at `agents/<agent>/runs/.running/_chat-<run_id>.json`; completion removes only its entry
and marker. The UI also reads legacy `_chat.json` markers during transition.

`GET /api/chat-stop?tid=<run-id>` requires explicit realm identity and may target a known realm
that is no longer selected. Cancellation before the process callback is remembered and applied
when the process arrives. Process-tree cleanup, adapter deadlines and terminal-event guarantees
are provided by the shared [CLI turn lifecycle](PROCESS_LIFECYCLE.md) (ticket **2.18**).

Verification lives in `tests/test_realm_context.py` and `tests/realm_context_harness.js`: real HTTP
A-to-B switches with overlapping identical agent/thread/run IDs, transcript/report/artifact/title
and unread destinations, cancellation, duplicate admission, stale saves/polls, bound mini-site
assets, handler reuse, early cancellation and the browser request contract. Existing origin,
SVG-isolation and first-run tests exercise identity-aware requests too.

## Upgrade

There is no realm-format migration. Restart the app server and reload existing pages to obtain
identity-bearing requests and content URLs. Older automation clients that POST to realm-scoped
routes must send the page's realm identity. Path IDs change on folder moves, so old links then
need to be recreated. This change has been verified in source; it does not itself restart the
owner's running app or scheduler.
