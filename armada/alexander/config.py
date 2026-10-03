"""Alexander's app-wide model preference, independent of realm defaults."""
from .. import appconfig, providers, models, verbosity
from ..engine.selection import model_provider
from . import MODEL, EFFORT

CODEX_MODEL = "gpt-6-sol"
CODEX_EFFORT = "medium"


def load():
    return {"model": "auto", "effort": "auto", "verbosity": verbosity.DEFAULT, **appconfig.get("alexander", {})}


def efforts(model):
    if model == "auto":
        return ["auto", "low", "medium", "high"]
    if model_provider(model) == "gemini":
        from ..engine.gemini import cached_models, model_id
        item = next((m for m in cached_models() if m["id"] == model_id(model)), {})
        return ["auto"] + [e for e in ("low", "medium", "high") if e in item.get("efforts", ("low", "medium", "high"))]
    if model_provider(model) == "codex":
        from ..engine.codex import cached_models
        item = next((m for m in cached_models() if m["slug"] == model), {})
        values = [v.get("effort") if isinstance(v, dict) else v
                  for v in item.get("supported_reasoning_levels", [])]
        return ["auto"] + [v for v in (values or ["low", "medium", "high", "xhigh"])
                           if v in ("low", "medium", "high", "xhigh", "max")]
    return ["auto", "low", "medium", "high", "max"]


def save(root, model, effort, verbosity_level=None):
    if model != "auto" and model not in dict(models.options(root)):
        raise ValueError("Choose a model from a connected provider.")
    if effort not in efforts(model):
        raise ValueError("That effort is not supported by the selected model.")
    level = load()["verbosity"] if verbosity_level is None else verbosity_level
    if level not in verbosity.LEVELS:
        raise ValueError("Choose a supported verbosity level.")
    appconfig.save({"alexander": {"model": model, "effort": effort, "verbosity": level}})
    return {"ok": True}


def resolve(root, states=None):
    states = providers.statuses() if states is None else states
    cfg = load()
    model = cfg["model"]
    if model == "auto":
        if states["claude"]["connected"]:
            model = MODEL
        elif states["codex"]["connected"]:
            model = CODEX_MODEL
        elif states.get("gemini", {}).get("connected"):
            model = "gemini:auto"
        else:
            raise ValueError("Connect Claude, Codex or Gemini in Settings → App to talk to Alexander.")
    provider = model_provider(model)
    if provider not in states or not states[provider]["connected"]:
        raise ValueError("Alexander's selected provider is disconnected. Reconnect it or choose Automatic in App → Advanced.")
    if provider == "codex":
        from ..engine.codex import cached_models
        available = cached_models()
        if available and model not in {m["slug"] for m in available} and model != "codex:default":
            raise ValueError("Alexander's model is unavailable for this account. Choose an available model in App → Advanced.")
    effort = cfg["effort"]
    if effort == "auto":
        effort = EFFORT if provider == "claude" else CODEX_EFFORT
        if provider == 'gemini' and effort not in efforts(model):
            effort = 'high'
    if effort not in efforts(model):
        raise ValueError("Alexander's effort is unavailable for this model. Update it in App → Advanced.")
    return provider, model, effort
