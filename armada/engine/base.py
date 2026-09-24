"""Engine adapter contract (SPEC §9). The provider seam: no engine-specific concept
leaks past this interface, so swapping Claude -> another engine is an adapter change,
not a realm change.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from typing import Optional


@dataclass
class Usage:
    input: int = 0
    output: int = 0
    cache_read: int = 0
    # Tokens written INTO the cache — the first time a context is seen it is cached rather than
    # read, so a fresh thread's whole prompt lands here and nowhere else. Omitting it made a real
    # 2,954-token turn report 6, because the only fields being counted were the handful of tokens
    # that were neither cached nor cache-read.
    cache_write: int = 0
    cost_usd: float = 0.0

    @property
    def total(self) -> int:
        return self.input + self.output + self.cache_read + self.cache_write

    def as_dict(self) -> dict:
        # NOTE: `api_equiv_usd` is what these tokens WOULD cost at API list prices. On a
        # subscription (OAuth) engine it is NOT billed — usage draws from the plan's quota.
        return {"input": self.input, "output": self.output, "cache_read": self.cache_read,
                "cache_write": self.cache_write,
                "total": self.total, "api_equiv_usd": round(self.cost_usd, 6)}


@dataclass
class RunResult:
    ok: bool
    output: str = ""
    usage: Usage = field(default_factory=Usage)
    model: str = ""
    error: str = ""
    raw: dict = field(default_factory=dict)


class EngineAdapter(ABC):
    name: str = "base"

    @abstractmethod
    def doctor(self) -> tuple[bool, str]:
        """Is the engine installed + authenticated? (ok, human-readable detail)."""

    @abstractmethod
    def run(self, system: str, prompt: str, model: Optional[str] = None,
            cwd: Optional[str] = None, allow_tools: bool = False, timeout: int = 300,
            effort: Optional[str] = None, fallback_model: Optional[str] = None,
            max_budget_usd: Optional[float] = None, disallowed_tools: Optional[list] = None,
            only_tools: Optional[list] = None) -> RunResult:
        """Run one turn. `system` = assembled context; `prompt` = the job ask.

        `fallback_model`: switch to this model if the primary is overloaded/unavailable.
        `max_budget_usd`: hard per-run spend ceiling (adapters that can't honour it ignore it).
        `only_tools`: a sealed turn — exactly these built-in tools, pre-approved, and nothing else:
        none of the owner's connectors, skills or plugins, no prompts that could approve more. For
        turns that read untrusted content (THREAT_MODEL T4); overrides `allow_tools`."""
