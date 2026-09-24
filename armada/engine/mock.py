"""Mock engine — lets the runner + telemetry be tested end-to-end offline, with no
Claude Code and no tokens spent. Same interface as the real adapter; swap with --engine.
"""
from __future__ import annotations
from typing import Optional
from .base import EngineAdapter, RunResult, Usage


class MockEngine(EngineAdapter):
    name = "mock"

    def doctor(self) -> tuple[bool, str]:
        return True, "Mock engine — always available (offline, no tokens spent)."

    def run(self, system: str, prompt: str, model: Optional[str] = None,
            cwd: Optional[str] = None, allow_tools: bool = False, timeout: int = 300,
            effort: Optional[str] = None, fallback_model: Optional[str] = None,
            max_budget_usd: Optional[float] = None, disallowed_tools: Optional[list] = None,
            only_tools: Optional[list] = None) -> RunResult:
        out = (f"[mock:{model or 'default'}] I received a system context of {len(system)} chars "
               f"and this ask: “{prompt.strip()[:160]}”. In a real run, {self.name} would do the work "
               f"and return the result here.")
        # plausible fake usage so telemetry/cost plumbing is exercised
        usage = Usage(input=max(1, len(system) // 4), output=max(1, len(out) // 4),
                      cache_read=0, cost_usd=0.0)
        return RunResult(ok=True, output=out, usage=usage, model=model or "mock-1",
                         raw={"mock": True})
