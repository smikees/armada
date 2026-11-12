# `armada/execution_admission.py`

Account-wide bounded execution, with kernel-owned tickets and fair realm turns.

Tickets are scheduling metadata, never permission grants or replay instructions. A dead
owner frees capacity; the caller's durable attempt record retains any uncertain outcome.

### class `QueueFull`

—


### class `Cancelled`

—


### `_directory()`

—

### `_state_path()`

—

### `_slot_path(slot)`

—

### `_read()`

—

### `_read_snapshot(*, timeout=5.0)`

—

### `_prune(state)`

—

### `_blocking_reason(row, active, pending, rows)`

—

### `_promote(state)`

—

### `_transaction()`

—

### class `Ticket`

—

- `Ticket.__init__(self, context, provider, *, realm_required=True, background=False)` — —
- `Ticket._publish(self, context, provider, realm_required)` — —
- `Ticket._row(self, state)` — —
- `Ticket.ready(self)` — —
- `Ticket.wait(self, cancelled=lambda: False, on_wait=None, on_queue=None)` — —
- `Ticket._watch(self)` — —
- `Ticket.activate(self, on_cancel=None)` — —
- `Ticket.close(self)` — —

### `scope(context, provider, *, cancelled=lambda: False, on_cancel=None, on_wait=None, on_queue=None, realm_required=True, background=False)`

—

### `cancel(realm_id, *, agent=None, thread=None, run_id=None)`

—

### `snapshot()`

—

### `cancelled()`

—

### `defer_current(until)`

Release capacity while a logical invocation waits for its subscription reset.

### `view(root, agent=None, thread=None)`

Read-only presentation hint. Kernel ownership, never this hint, admits execution.

### `provider_call(provider, cwd=None, on_proc=None, on_wait=None, on_queue=None)`

Include auxiliary model calls (titles/search/reviews/compaction) in the same budget.
