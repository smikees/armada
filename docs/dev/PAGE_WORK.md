# Page work and navigation contract

M10, 8 November 2026. Server-rendered pages remain the navigation boundary.

## Resources and state

- `assets` loads the small math controller; `math.js` loads the local KaTeX CSS
  and script once, only when a server-recognized formula appears. Rendering keeps
  the existing untrusted-TeX limits. Asset failure leaves readable source text.
- Closed avatar/changelog dialogs retain inert template content until opened.
  Select-backed menus retain their native value source and build rows on opening;
  provider refreshes invalidate those rows without changing the selected value.
- `page_state.js` keeps presentation state in session storage: at most 32 routes,
  keyed by realm, path and sorted query, with a two-hour restoration lifetime.
  Only job-filter text, known dropdown choices, scroll offsets and a focus ID are
  stored. Settings, credentials, grants and submit values are never captured.
  Explicit anchors and intervening user input take precedence. Hidden WebView2
  windows use a bounded timer fallback when animation frames are paused.
- Conversation drafts continue using the existing realm/thread draft store.
  Navigation restoration never sends a message or replays an operation.

## Snapshot ownership and limits

`routes.dashboard` renders/serves only the existing local copy. A missing copy has
an immediate placeholder. `snap.js` starts a background refresh and polls a ticket;
success reloads the content iframe only. Failure keeps the previous copy and shows
an error. A refresh request is not evidence of a completed write.

`section_snapshots` owns two workers, eight admitted refreshes and at most 64
retained states. Concurrent requests for the same realm/index/configuration share
one job. Tickets are checked against the current realm and configuration. Input
and final output are limited to 8 MiB. HTTP sources have a five-second socket
timeout and a twenty-second total budget checked between chunks (one in-progress
read may extend that budget). The UI stops polling after thirty seconds; a slow
local filesystem operation may still be running, and a later request can rejoin it.

Before committing, the worker locks `realm.json`, verifies the captured section
still occupies the same index, locks the destination, rechecks the shared Windows
path guard and atomically replaces the copy. Failed/oversized reads and edited or
deleted configurations cannot replace an existing copy. External editing that
ignores application locks is not a transactional configuration protocol.

Local source enumeration/read calls can block in the operating system, including
network drives. They are outside HTTP/render workers and bounded to two workers;
hard cancellation of blocked filesystem calls is not claimed. Owner-configured
sources may access the network; agent scope is unchanged. Content continues to
use the separate content origin or existing CSP fallback.

## Repeatable evidence

Run `tools/page_work_probe.py --output build/page-work.json` with the pinned
Windows runtime. It starts only a synthetic realm/server and an isolated WebView2
profile; providers are stubbed and its job is disabled. `--measure-only` records
resources without asserting the new behavior, for comparisons against older code.

The initial Settings measurement fell from 3,165 to about 1,053 DOM elements and
from 797,215 to about 502,760 transferred bytes. Formula-free pages make no KaTeX
requests (298,474 bytes avoided on a cold page). These are one-host resource
measurements, not latency percentiles. Native checks cover dialog hydration,
dynamic formulas, settings tab/focus/scroll, job filters and unsent drafts.

`tests/test_section_snapshots.py` checks blocked sources, coalescing, bounded
admission, obsolete configurations, size/deadline/disconnect failures and previous
copy preservation. `test_section_paths.py` covers path and content-origin guards.
