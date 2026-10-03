# `armada/request_context.py`

Immutable request/run destinations; the selected realm is only an admission-time default.

IDs identify canonical local folders, not permissions. Moving a folder changes its ID so stale
links fail closed. Explicit content destinations resolve only to known or registered realms.

### class `RealmMismatch`

A page/request no longer names the realm selected by the owner.


### class `RealmContext`

—

- `RealmContext.capture(cls, root)` — —
- `RealmContext.resolve(cls, identity, current)` — —

### class `RunContext`

—

- `RunContext.capture(cls, root, agent, thread='main', run_id=None)` — —
- `RunContext.key(self)` — —
- `RunContext.marker(self)` — —

### class `ActiveRun`

—


### `content_path(path)`

—

### `bound_url(url, context, *, content=False)`

Bind local URLs without double-binding or accepting an arbitrary file-system path.

### `navigation_url(url, root)`

Notification navigation selects its original realm before opening the destination.

### `bind_content_html(body, context)`

Bind real markup attributes without rewriting script text or untrusted documents.
