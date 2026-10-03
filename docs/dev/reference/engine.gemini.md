# `armada/engine/gemini.py`

Google Gemini through the supported Antigravity CLI; cached login, fresh scoped turns.

### `invalidate_auth()`

—

### `cached_models()`

—

### `model_options()`

—

### `model_id(value)`

—

### `scoped_project(roots, servers, network)`

A fresh project owns each run's grants; never edit the user's global policy.

### `parse_models(text)`

—

### class `GeminiEngine`

—

- `GeminiEngine.__init__(self, binary='agy')` — —
- `GeminiEngine._launcher(self)` — —
- `GeminiEngine._probe(self, args)` — —
- `GeminiEngine.auth_status(self, force=False)` — —
- `GeminiEngine.doctor(self)` — —
- `GeminiEngine.usage_limits(self)` — —
- `GeminiEngine._connectors(self, denied)` — —
- `GeminiEngine._agent(self, system, allow_tools, denied)` — —
- `GeminiEngine.run(self, system, prompt, **kwargs)` — —
- `GeminiEngine.run_stream(self, system, prompt, model=None, cwd=None, allow_tools=False, timeout=300, effort=None, fallback_model=None, max_budget_usd=None, disallowed_tools=None, only_tools=None, verbosity=None, on_event=None, on_proc=None)` — —
