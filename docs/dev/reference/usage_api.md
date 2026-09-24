# `armada/usage_api.py`

Read the real Claude subscription usage (session + weekly) that powers the Claude app's Usage view.

ARMADA runs agents through Claude Code on the owner's Max/Pro subscription, so the OAuth token Claude
Code stores locally is enough to query Anthropic's (undocumented) usage endpoint — the same one the
`/usage` view uses. We show the current 5-hour session and 7-day weekly utilisation as % of limit,
with reset times. Anthropic publishes no token-denominated limits, so these percentages ARE the limit
comparison; the widget's per-agent/per-model token tally (from local run telemetry) is separate.

Deliberately READ-ONLY and best-effort: we read the credentials file but never write it, never refresh
the token, and never raise. Undocumented endpoint; may change without notice.

**Why we never refresh the token ourselves.** The credentials file holds a refresh token, so minting
a fresh access token would be easy — and is a trap. If Anthropic rotates refresh tokens on use (the
usual practice), consuming one without writing the replacement back would invalidate Claude Code's
stored credential and break the owner's sign-in; writing it back means this app mutating another
application's credential store. Instead the `usage-keepalive` system job makes a trivial Claude Code
call every few hours, and Claude Code refreshes its own token as a side effect. Measured: one 5-second
call extended expiry by ~18 hours.

**Why the last reading is kept on disk.** An access token lives ~12-18 hours. Before, an expired one
meant the bars vanished entirely — not stale, *gone* — which is a worse answer than a slightly old
number, because a blank header tells the owner nothing at all. We now persist each successful reading
and serve it with its age when the live call fails, so the figures are always on screen. `age_sec`
and `stale` are on every served payload; the UI decides how loudly to caveat.

### `_read_token()`

(access_token, expires_at_ms) from Claude Code's credentials, or None if unreadable.

### `_countdown(resets_at: str)`

'2h 10m' / '3d 4h' until an ISO reset time (best-effort; '' if unparseable).

### `_window(d: dict)`

—

### `_fetch_live()`

—

### `message_for(reason: str)`

The owner-facing line for an unavailable reason. Never empty, even for a reason we've not seen before — silence is the one outcome that leaves someone staring at a blank header.

### `_normalise(d: dict)`

Guarantee the contract the UI relies on: unavailable results always carry a `message`.

### `_disk_path(realm_root)`

—

### `_remember(realm_root, data: dict)`

Persist a good reading so an expired token doesn't blank the header.

### `_recall(realm_root)`

(data, age_seconds) from the last good reading, or None if absent/stale/unreadable.

### `_as_of(data: dict, age: float, reason: str)`

A remembered reading, labelled honestly. The percentages are real but old, and the reset countdowns are NOT recomputed — a countdown from a stale reading would be actively wrong.

### `_AGE_NOTE(age: float)`

—

### `fetch(realm_root=None)`

Cached (60s) real usage: {available, session:{pct,...}, weekly:{...}, age_sec, stale} or {available:False, reason, message}.
