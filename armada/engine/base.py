"""Engine adapter contract (SPEC §9). The provider seam: no engine-specific concept
leaks past this interface, so swapping Claude -> another engine is an adapter change,
not a realm change.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import Optional
from .contracts import (ProviderCapabilities, ExecutionPolicy, RunRequest, RunEvent,
                        CancellationHandle, EventSink, ProcessSink, validate_request)


@dataclass
class Usage:
    input: int | None = None
    output: int | None = None
    cache_read: int = 0
    # Tokens written INTO the cache — the first time a context is seen it is cached rather than
    # read, so a fresh thread's whole prompt lands here and nowhere else. Omitting it made a real
    # 2,954-token turn report 6, because the only fields being counted were the handful of tokens
    # that were neither cached nor cache-read.
    cache_write: int = 0
    cost_usd: float | None = None

    @property
    def total(self) -> int | None:
        if self.input is None or self.output is None:
            return None
        return self.input + self.output + self.cache_read + self.cache_write

    def as_dict(self) -> dict:
        # NOTE: `api_equiv_usd` is what these tokens WOULD cost at API list prices. On a
        # subscription (OAuth) engine it is NOT billed — usage draws from the plan's quota.
        return {"input": self.input, "output": self.output, "cache_read": self.cache_read,
                "cache_write": self.cache_write,
                "total": self.total, "api_equiv_usd": round(self.cost_usd, 6) if self.cost_usd is not None else None}


@dataclass
class RunResult:
    ok: bool
    output: str = ""
    usage: Usage = field(default_factory=Usage)
    model: str = ""
    error: str = ""
    raw: dict = field(default_factory=dict)
    cancelled: bool = False
    timed_out: bool = False


class EngineAdapter(ABC):
    name: str = "base"
    capabilities = ProviderCapabilities()

    def configure(self, policy: ExecutionPolicy):
        """Bind an invocation-local policy; never mutate a shared adapter's grants."""
        import copy
        engine = copy.copy(self)
        engine.allowed_mcp_ids = policy.allowed_mcp_ids
        engine.writable_roots = policy.writable_roots
        engine.network_access = policy.network_access
        engine.allowed_app_ids = policy.allowed_app_ids
        return engine

    def execute(self, request: RunRequest, *, on_event: EventSink | None = None,
                on_proc: ProcessSink | None = None) -> RunResult:
        validate_request(self.name, self.capabilities, request)
        if self.capabilities.streaming:
            result = self.run_stream(**request.kwargs(), on_event=on_event, on_proc=on_proc)
        else:
            from .process import safe_emit
            result = self.run(**request.kwargs())
            if result.output:
                safe_emit(on_event, {"kind": "text", "text": result.output})
        if result.usage.cost_usd is None:
            from ..token_cost import estimate
            result.usage.cost_usd = estimate(result.model, result.usage.as_dict())
        return result

    def run_stream(self, *args, **kwargs) -> RunResult:
        raise NotImplementedError(f"{self.name} does not declare streaming support")

    @abstractmethod
    def doctor(self) -> tuple[bool, str]:
        """Is the engine installed + authenticated? (ok, human-readable detail)."""

    @abstractmethod
    def run(self, system: str, prompt: str, model: Optional[str] = None,
            cwd: Optional[str] = None, allow_tools: bool = False, timeout: int = 300,
            effort: Optional[str] = None, fallback_model: Optional[str] = None,
            max_budget_usd: Optional[float] = None, disallowed_tools: Optional[list] = None,
            only_tools: Optional[list] = None, verbosity: Optional[str] = None) -> RunResult:
        """Run one turn. `system` = assembled context; `prompt` = the job ask.

        `fallback_model`: switch to this model if the primary is overloaded/unavailable.
        `max_budget_usd`: hard per-run spend ceiling; unsupported requirements must be rejected.
        `only_tools`: a sealed turn — exactly these built-in tools, pre-approved, and nothing else:
        none of the owner's connectors, skills or plugins, no prompts that could approve more. For
        turns that read untrusted content (THREAT_MODEL T4); overrides `allow_tools`.
        `verbosity`: Armada's writing style; changes reply length, never the required work."""
