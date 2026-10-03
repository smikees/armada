# `armada/engine/codex.py`

Codex CLI turns, using the owner's login and Armada's existing context and history.

One fresh exec per turn avoids keeping a second, divergent conversation in Codex. JSONL events
are translated to Armada's existing stream contract. No credential file is read or copied.

### `_feature_args()`

—

### `codex_home()`

—

### `cached_models()`

Read only the CLI's public model metadata; never fetch during a page render.

### `model_id(value: str)`

—

### `_verbosity_args(model: str, level: str | None)`

Map Armada's four writing styles to Codex's three native verbosity levels.

### class `CodexEngine`

—

- `CodexEngine.__init__(self, binary='codex')` — —
- `CodexEngine._launcher(self)` — —
- `CodexEngine._probe(self, args, cwd=None)` — —
- `CodexEngine.auth_status(self)` — —
- `CodexEngine.doctor(self)` — —
- `CodexEngine.start_login(self)` — —
- `CodexEngine._mcp_args(self, allow_tools, denied, cwd=None)` — —
- `CodexEngine._args(self, model, allow_tools, effort, denied, cwd=None, verbosity=None)` — —
- `CodexEngine.run(self, system, prompt, model=None, cwd=None, allow_tools=False, timeout=300, effort=None, fallback_model=None, max_budget_usd=None, disallowed_tools=None, only_tools=None, verbosity=None)` — —
- `CodexEngine.run_stream(self, system, prompt, model=None, cwd=None, allow_tools=False, timeout=300, on_event=None, on_proc=None, effort=None, fallback_model=None, max_budget_usd=None, disallowed_tools=None, only_tools=None, verbosity=None)` — —
- `CodexEngine._run_app_stream(self, launcher, system, prompt, model, cwd, allow_tools, timeout, on_event, on_proc, effort, disallowed_tools, verbosity=None)` — Stream actual Codex text deltas while keeping each Armada turn isolated and ephemeral.

### class `_Stream`

Normalize completed items once; a started/updated item is never an extra reply.

- `_Stream.__init__(self, emit, model='', cwd=None)` — —
- `_Stream.accept(self, event)` — —

### class `_AppStream`

Translate Codex app-server notifications into Armada's durable turn events.

- `_AppStream.__init__(self, emit, model='', cwd=None)` — —
- `_AppStream.output(self)` — —
- `_AppStream.accept(self, message)` — —
