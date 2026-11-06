# `armada/desktop_operations.py`

Bounded asynchronous native script calls; no worker thread per browser call.

### class `_Call`

—


### class `ScriptCalls`

Native UI timer polls at most four tasks; timeouts retain their capacity.

- `ScriptCalls.__init__(self, post, start, *, capacity=4)` — —
- `ScriptCalls.evaluate(self, script, timeout=10)` — —
- `ScriptCalls._finish(self, call, *, value=None, error='')` — —
- `ScriptCalls.poll(self)` — —
- `ScriptCalls.reset(self, *, close=False)` — —
