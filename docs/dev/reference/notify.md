# `armada/notify.py`

Desktop notifications — native Windows toasts, best-effort.

ARMADA already knows when things happen (the runner writes run markers and reports; the approvals
inbox knows what's waiting). This module is only the delivery layer: turn an event into a toast.

Design rules, in order of importance:

1. **A notification must never affect a run.** Every entry point swallows its own errors and the
   send happens on a daemon thread, so a missing PowerShell, a locked desktop or a slow COM call
   can't delay or fail a job. Notifying is the least important thing ARMADA does.
2. **No new dependencies.** Toasts go through PowerShell's WinRT bridge, which is present on every
   Windows 10/11 box. ARMADA stays stdlib-only.
3. **Quiet by construction.** Identical events collapse inside a short window (see _DEDUPE_SEC) on
   every channel that interrupts you — desktop and Telegram — so a job retrying in a loop can't
   carpet either. The in-app feed is never collapsed: it is the record, not an interruption.

Attribution comes from the AppUserModelID that app.py already sets on the process, so toasts show
as "ARMADA" with its icon rather than as pythonw or PowerShell.

### `muted()`

Are off-machine channels muted for this process?

### `channel_enabled(channel: str)`

Is this delivery channel switched on for this machine?

### `channels_enabled()`

—

### `desktop_enabled()`

—

### `telegram_enabled()`

—

### `default_matrix()`

—

### `matrix(realm_root)`

The event × channel grid for this realm, defaults filled in.

### `cross_realm(realm_root)`

May this realm interrupt you while you are viewing a different one?

### `is_active_realm(realm_root)`

Is this the realm the app is currently in?

### `realm_label(realm_root)`

The realm's display name, for saying WHICH realm a notification came from.

### `_titled(realm_root, title: str)`

Prefix a notification with its realm.

### `wants(realm_root, event: str, channel: str)`

Should this event reach this channel? Every switch has to agree: the machine has to have the channel on, the realm has to want this kind there, and — for channels that reach you outside the realm — the realm has to be allowed to interrupt you while you're elsewhere.

### `enabled_events(realm_root)`

Back-compat view: is this event enabled on ANY channel?

### `_dedupe(key: str)`

True if this exact event fired very recently (so we should stay quiet).

### `_send(title: str, body: str)`

—

### `_feed_path(realm_root)`

—

### `_state_path(realm_root)`

—

### `_now()`

Timestamps carry microseconds on purpose. Read state is 'everything up to this instant', so at one-second resolution a notification arriving in the same second you hit Mark all read would be counted as already seen — and vanish from the unread badge without you ever seeing it.

### `_safe_href(href: str)`

Keep links pointing inside ARMADA.

### `record(realm_root, event: str, title: str, body: str='', href: str='')`

Append one entry to the in-app feed. Best-effort; returns the entry or None.

### `_trim(p: Path)`

Keep the file bounded. Cheap: only rewrites once it's meaningfully over the cap.

### `feed(realm_root, limit: int=50)`

Most recent entries first. Never raises — a missing or corrupt feed reads as empty.

### `prune(realm_root, days: int=RETAIN_DAYS)`

Drop entries older than `days`. Returns how many went. Age is the right axis for history — a count cap silently loses today's notifications on a busy realm.

### `_dt_now()`

—

### `_dt_timedelta(**kw)`

—

### `last_read(realm_root)`

—

### `mark_read(realm_root)`

Mark everything currently in the feed as seen.

### `unread_count(realm_root, items=None)`

—

### `emit(realm_root, event: str, title: str, body: str='', href: str='')`

The one way ARMADA announces something: archive it in the app, and — for the event kinds that warrant interrupting — also raise a desktop notification.

### `_send_telegram(realm_root, event: str, title: str, body: str, href: str)`

Push a notification to the linked Telegram chat.

### `toast(title: str, body: str='', *, realm_root=None, event: str='')`

Show a desktop notification. Returns True if it was dispatched (not that it was displayed).
