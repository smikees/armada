# `armada/thread_windows.py`

Realm-bound destinations and shared state for independent thread views.

### `target(root, agent, thread)`

Validate an existing thread without silently falling back to main.

### `state(root, agent, thread, revision='')`

Canonical conversation snapshot, shared by the cockpit, widget and companion.
