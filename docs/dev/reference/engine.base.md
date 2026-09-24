# `armada/engine/base.py`

Engine adapter contract (SPEC §9). The provider seam: no engine-specific concept
leaks past this interface, so swapping Claude -> another engine is an adapter change,
not a realm change.

### class `Usage`

—

- `Usage.total(self)` — —
- `Usage.as_dict(self)` — —

### class `RunResult`

—


### class `EngineAdapter`

—

- `EngineAdapter.doctor(self)` — Is the engine installed + authenticated? (ok, human-readable detail).
- `EngineAdapter.run(self, system: str, prompt: str, model: Optional[str]=None, cwd: Optional[str]=None, allow_tools: bool=False, timeout: int=300, effort: Optional[str]=None, fallback_model: Optional[str]=None, max_budget_usd: Optional[float]=None, disallowed_tools: Optional[list]=None, only_tools: Optional[list]=None)` — Run one turn. `system` = assembled context; `prompt` = the job ask.
