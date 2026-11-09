# `armada/engine/codex_steering.py`

Bounded mid-turn input for Codex app-server; the RPC owner alone writes stdin.

### class `SteeringControl`

—

- `SteeringControl.__init__(self)` — —
- `SteeringControl.ready(self)` — —
- `SteeringControl.activate(self, thread_id, turn_id)` — —
- `SteeringControl.submit(self, identity, text, callback)` — —
- `SteeringControl._finish(self, row, status, error='')` — —
- `SteeringControl.drain(self, send)` — —
- `SteeringControl.accept(self, message)` — —
- `SteeringControl.close(self)` — —

### class `SteeringProcess`

Expose steering only for this particular app-server process and active turn.

- `SteeringProcess.__init__(self, process, control)` — —
- `SteeringProcess.pid(self)` — —
- `SteeringProcess.can_steer(self)` — —
- `SteeringProcess.poll(self)` — —
- `SteeringProcess.kill(self)` — —
- `SteeringProcess.steer(self, identity, text, callback)` — —
