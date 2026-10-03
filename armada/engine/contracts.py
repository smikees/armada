"""Provider-independent requests, events and enforceable execution capabilities."""
from dataclasses import dataclass, asdict
import math
import re
from typing import Callable, Literal, Protocol, TypedDict


class RunEvent(TypedDict, total=False):
    kind: Literal["start", "text", "thinking", "tool", "tool_result", "error"]
    text: str
    name: str
    id: str
    input: dict
    error: str


class CancellationHandle(Protocol):
    @property
    def pid(self) -> int: ...
    def kill(self) -> None: ...
    def poll(self) -> int | None: ...


EventSink = Callable[[RunEvent], None]
ProcessSink = Callable[[CancellationHandle], None]


@dataclass(frozen=True)
class ProviderCapabilities:
    streaming: bool = False
    cancellation: bool = False
    budget: bool = False
    fallback: bool = False
    sealed_tools: bool = False
    tool_denials: bool = False


@dataclass(frozen=True)
class ExecutionPolicy:
    allowed_mcp_ids: frozenset[str] = frozenset()
    writable_roots: tuple[str, ...] = ()
    network_access: bool = False


@dataclass(frozen=True)
class RunRequest:
    system: str
    prompt: str
    model: str | None = None
    cwd: str | None = None
    allow_tools: bool = False
    timeout: int | float | None = 1200
    effort: str | None = None
    fallback_model: str | None = None
    max_budget_usd: float | None = None
    disallowed_tools: tuple[str, ...] = ()
    only_tools: tuple[str, ...] | None = None
    verbosity: str | None = None

    def kwargs(self):
        out = asdict(self)
        out["disallowed_tools"] = list(self.disallowed_tools)
        if self.verbosity is None:
            out.pop("verbosity")  # existing adapters need no new argument
        if self.only_tools is None:
            out.pop("only_tools")  # legacy streaming adapters predate sealed turns
        else:
            out["only_tools"] = list(self.only_tools)
        return out


def validate_request(provider: str, capabilities: ProviderCapabilities, request: RunRequest):
    """Reject requirements we cannot enforce, before context compaction or CLI launch."""
    from .selection import model_provider
    from ..providers import require_allowed
    require_allowed(provider)
    budget = request.max_budget_usd
    if budget is not None:
        if isinstance(budget, bool) or not isinstance(budget, (int, float)) or not math.isfinite(budget) or budget < 0:
            raise ValueError("The per-run dollar budget must be a finite nonnegative number.")
        if budget and not capabilities.budget:
            raise ValueError(f"{provider.title()} cannot enforce a dollar budget. Clear the per-run budget.")
    if request.fallback_model:
        if not capabilities.fallback:
            raise ValueError(f"{provider.title()} does not support automatic fallback models.")
        selected = model_provider(request.fallback_model)
        if selected and selected != provider and provider != "mock":
            raise ValueError("Cross-provider fallback is not supported. Choose a fallback from the same provider.")
    if request.only_tools is not None and not capabilities.sealed_tools:
        raise ValueError(f"{provider.title()} does not support a sealed tool allowlist.")
    if request.disallowed_tools and not capabilities.tool_denials:
        raise ValueError(f"{provider.title()} does not support tool denials.")
    if provider == "codex" and any(not re.fullmatch(r"mcp__[A-Za-z0-9_-]+(?:__\*)?", p)
                                   or "__" in p.removeprefix("mcp__").removesuffix("__*")
                                   for p in request.disallowed_tools):
        raise ValueError("Codex cannot enforce individual tool denials; only MCP server grants are supported.")


def execute_request(engine, request: RunRequest, *, on_event=None, on_proc=None):
    """Compatibility boundary for older injected adapters; production adapters use execute()."""
    from .base import EngineAdapter, RunResult, Usage
    from .process import safe_emit
    if isinstance(engine, EngineAdapter):
        return engine.execute(request, on_event=on_event, on_proc=on_proc)
    # Old local extensions may expose only run(), or the former streaming signature. Keep
    # discovery confined here, never in the coordinator. They must declare extra requirements.
    capabilities = getattr(engine, "capabilities", ProviderCapabilities())
    validate_request(getattr(engine, "name", "unknown"), capabilities, request)
    stream = getattr(engine, "run_stream", None)
    if stream:
        result = stream(**request.kwargs(), on_event=on_event, on_proc=on_proc)
    else:
        result = engine.run(**request.kwargs())
        if getattr(result, "output", ""):
            safe_emit(on_event, {"kind": "text", "text": result.output})
    if isinstance(result, RunResult):
        return result
    if not isinstance(getattr(result, "ok", None), bool):
        raise ValueError("Legacy engine returned no valid result.")
    usage = getattr(result, "usage", None)
    if not isinstance(usage, Usage):
        data = usage.as_dict() if usage is not None else {}
        usage = Usage(input=data.get("input"), output=data.get("output"),
                      cache_read=data.get("cache_read", 0), cache_write=data.get("cache_write", 0),
                      cost_usd=data.get("api_equiv_usd"))
    return RunResult(ok=result.ok, output=getattr(result, "output", ""), usage=usage,
                     error=getattr(result, "error", ""), model=getattr(result, "model", ""),
                     cancelled=getattr(result, "cancelled", False))
