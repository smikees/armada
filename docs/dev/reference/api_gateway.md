# `armada/api_gateway.py`

Invocation-local Anthropic gateway: real keys stay in the host.

Only Messages and free token counting are exposed. A numeric ceiling keeps the legacy
conservative per-request budget. Explicit None delegates spending enforcement to the
provider, as selected in the owner API fallback setup.

### class `Budget`

—

- `Budget.__init__(self, ceiling)` — —
- `Budget.authorise(self, body, input_tokens)` — —
- `Budget.finish(self, model, reservation, usage)` — Release unused request capacity only after terminal usage is complete.
- `Budget.cost(self)` — Independent provider usage prevents a worker from understating CLI totals.

### `metered_cost(model, usage)`

Verified first-party standard rates, applied to the provider's actual counters.

### class `_Usage`

Read usage counters without persisting provider text or tool arguments.

- `_Usage.__init__(self, streaming)` — —
- `_Usage.add(self, chunk)` — —
- `_Usage.event(self, value)` — —
- `_Usage.finish(self)` — —

### class `Gateway`

—

- `Gateway.__init__(self, key, ceiling)` — —
- `Gateway._open(self, path, body, headers)` — —
- `Gateway.count(self, body, headers)` — —
- `Gateway.__enter__(self)` — —
- `Gateway.env(self)` — —
- `Gateway.__exit__(self, *args)` — —
