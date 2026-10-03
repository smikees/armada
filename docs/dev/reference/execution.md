# `armada/execution.py`

Own agent turns across HTTP, plain chat, jobs, inbox and Telegram.

Runner functions remain compatibility entry points and context-building helpers. This module
owns admission, activity, progress, terminal history, accounting and cleanup. Transports only
observe events; a disconnected observer cannot abandon the conversation.

### class `_LiveTextRenderer`

Throttle Markdown rendering without leaving the last delta waiting for another event.

- `_LiveTextRenderer.__init__(self, sink, interval=0.1, checkpoint=None)` — —
- `_LiveTextRenderer._paint(self)` — —
- `_LiveTextRenderer.update(self, text)` — —
- `_LiveTextRenderer._tick(self)` — —
- `_LiveTextRenderer.flush(self)` — —
- `_LiveTextRenderer.close(self)` — —

### `_report_summary(output: str)`

Keep the deliverable in run history without showing its machine status marker.

### class `RunSession`

Exclusive in-process admission and owned activity marker, including early cancellation.

- `RunSession.__init__(self, context, registry=None, lock=None)` — —
- `RunSession.__enter__(self)` — —
- `RunSession.bind(self, process)` — —
- `RunSession.cancel(key, registry=None, lock=None)` — —
- `RunSession.close(self)` — —
- `RunSession.__exit__(self, *args)` — —

### class `TurnRequest`

—


### class `TurnCoordinator`

—

- `TurnCoordinator.__init__(self, request: TurnRequest, *, on_event=None, on_proc=None, session=None)` — —
- `TurnCoordinator.run(self)` — —
