# `armada/dispatch.py`

A bounded scheduler queue. Only admitted work receives a worker thread.

The daemon owns discovery and pumping; workers own execution and terminal evidence.
No executor's hidden/unbounded queue, and no worker is occupied waiting for a slot.

### class `Dispatcher`

—

- `Dispatcher.__init__(self)` — —
- `Dispatcher.contains(self, key)` — —
- `Dispatcher.submit(self, context, provider, prepare)` — Reserve bounded queue space before durable claiming. prepare returns work/cancel.
- `Dispatcher.pump(self)` — —
- `Dispatcher._run(self, key, ticket, work)` — —
- `Dispatcher.cancel_pending(self, root, reason='The scheduler stopped before this job began.')` — —
- `Dispatcher.defer_prerequisites(self, key, reason)` — Release a queued job's capacity while its durable prerequisite wait continues.
- `Dispatcher.busy(self, root)` — —
- `Dispatcher.close(self)` — —
