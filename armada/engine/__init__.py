"""Engine adapters — the provider seam. `get_engine(name)` is the only factory."""
from __future__ import annotations
from .base import EngineAdapter, RunResult, Usage
from .mock import MockEngine
from .claude import ClaudeEngine
from .codex import CodexEngine
from .gemini import GeminiEngine
from .selection import engine_for, enabled_providers, model_provider

_REGISTRY = {"mock": MockEngine, "claude": ClaudeEngine, "codex": CodexEngine, "gemini": GeminiEngine}


def get_engine(name: str = "mock") -> EngineAdapter:
    name = (name or "mock").lower()
    if name not in _REGISTRY:
        raise SystemExit(f"ARMADA: unknown engine '{name}' (have: {', '.join(_REGISTRY)})")
    return _REGISTRY[name]()


def engines() -> list[str]:
    return list(_REGISTRY)
