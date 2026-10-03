# `armada/engine/contracts.py`

Provider-independent requests, events and enforceable execution capabilities.

### class `RunEvent`

—


### class `CancellationHandle`

—

- `CancellationHandle.pid(self)` — —
- `CancellationHandle.kill(self)` — —
- `CancellationHandle.poll(self)` — —

### class `ProviderCapabilities`

—


### class `ExecutionPolicy`

—


### class `RunRequest`

—

- `RunRequest.kwargs(self)` — —

### `validate_request(provider: str, capabilities: ProviderCapabilities, request: RunRequest)`

Reject requirements we cannot enforce, before context compaction or CLI launch.

### `execute_request(engine, request: RunRequest, *, on_event=None, on_proc=None)`

Compatibility boundary for older injected adapters; production adapters use execute().
