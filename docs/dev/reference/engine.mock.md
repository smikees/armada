# `armada/engine/mock.py`

Mock engine — lets the runner + telemetry be tested end-to-end offline, with no
Claude Code and no tokens spent. Same interface as the real adapter; swap with --engine.

### class `MockEngine`

—

- `MockEngine.doctor(self)` — —
- `MockEngine.run(self, system: str, prompt: str, model: Optional[str]=None, cwd: Optional[str]=None, allow_tools: bool=False, timeout: int=300, effort: Optional[str]=None, fallback_model: Optional[str]=None, max_budget_usd: Optional[float]=None, disallowed_tools: Optional[list]=None)` — —
