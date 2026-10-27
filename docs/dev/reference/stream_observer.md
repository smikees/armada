# `armada/stream_observer.py`

A slow UI observer cannot hold the engine's event/cancellation loop.

### class `StreamObserver`

—

- `StreamObserver.__init__(self, handler)` — —
- `StreamObserver.disconnect(self)` — —
- `StreamObserver.__call__(self, event)` — —
- `StreamObserver._deliver(self)` — —
- `StreamObserver.close(self)` — —
