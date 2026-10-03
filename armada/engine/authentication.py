"""Admission for background model work; cost alone never identifies a provider.

Probe only once there is work. A failed probe fails closed; being signed out is a
skip, not an execution failure. Never substitute a different connected provider.
"""
import logging

from .selection import engine_for

log = logging.getLogger(__name__)


def provider_access(provider: str) -> dict:
    if provider == "mock":
        return {"ok": True, "provider": provider}
    try:
        from ..providers import allowed
        if not allowed(provider):
            return {"ok": False, "provider": provider, "status": "skipped", "reason": "disconnected",
                    "detail": f"{provider.title()} is disconnected in Settings → App.", "skipped": True, "error": ""}
        if provider == "claude":
            from .. import auth
            state = auth.status()
        elif provider == "codex":
            from .codex import CodexEngine
            state = CodexEngine().auth_status()
        elif provider == "gemini":
            from .gemini import GeminiEngine
            state = GeminiEngine().auth_status()
        else:
            raise ValueError(f"Unknown provider: {provider}")
        if (not isinstance(state, dict) or state.get("ok") is not True
                or not isinstance(state.get("logged_in"), bool)):
            raise ValueError("Provider sign-in status is unavailable")
        if state.get("logged_in") is True:
            return {"ok": True, "provider": provider}
        status, reason = "skipped", "signed-out"
        detail = f"{provider.title()} is signed out. Sign in and retry."
    except Exception:
        # Probe exceptions can contain CLI output; expose a stable, credential-free reason.
        log.warning("Provider sign-in probe unavailable: %s", provider)
        status, reason = "error", "auth-unavailable"
        detail = f"Could not check {provider.title()} sign-in. Retry when the provider is available."
    return {"ok": False, "provider": provider, "status": status, "reason": reason,
            "detail": detail, "skipped": status == "skipped",
            "error": detail if status == "error" else ""}


def recipient_access(realm_root, agent, engine="auto") -> dict:
    if not isinstance(engine, (str, type(None))):
        return provider_access(engine.name)
    return provider_access(engine_for(realm_root, agent, override=engine))
