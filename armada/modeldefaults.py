"""Apply a confirmed realm model combination to the current team."""
from contextlib import ExitStack
from pathlib import Path
from uuid import uuid4

from . import models, util, verbosity
from .engine.selection import model_provider


def apply_to_agents(root, model, effort, level):
    root = Path(root).resolve()
    if not isinstance(model, str) or model not in dict(models.options(root)):
        raise ValueError("Choose a model from the connected providers.")
    if not isinstance(effort, str) or effort not in ("auto", "low", "medium", "high", "xhigh", "max"):
        raise ValueError("Choose a valid thinking level.")
    if not isinstance(level, str) or level not in verbosity.LEVELS:
        raise ValueError("Choose a valid verbosity level.")
    if model_provider(model) == "codex":
        from .engine.codex import cached_models, model_id
        item = next((m for m in cached_models() if m["slug"] == model_id(model)), {})
        supported = [v.get("effort") if isinstance(v, dict) else v
                     for v in item.get("supported_reasoning_levels", [])]
        if supported and effort != "auto" and effort not in supported:
            raise ValueError("That thinking level is not supported by the selected model.")
    if model_provider(model) == 'gemini':
        from .alexander.config import efforts
        if effort not in efforts(model):
            raise ValueError('That thinking level is not supported by the selected model.')

    # Lock the same files as individual settings/grant edits. Read the entire batch before
    # writing so a corrupt agent cannot leave half the team changed. Jobs retain their overrides.
    realm_path = root / "realm.json"
    with ExitStack() as locks:
        locks.enter_context(util.file_lock(realm_path))
        agents = sorted((root / "agents").glob("*/agent.json"))
        for path in agents:
            if path.resolve().parent.parent != (root / "agents").resolve():
                raise ValueError("An agent folder points outside this realm.")
            locks.enter_context(util.file_lock(path))
        paths = agents + [realm_path]
        configs = {p: util.read_json_state(p) for p in paths}
        originals = {p: p.read_bytes().decode("utf-8") for p in paths}
        backup = root / ".armada" / "backups" / ("model-defaults-" + uuid4().hex + ".json")
        util.write_json_atomic(backup, {"files": {str(p.relative_to(root)): text
                                               for p, text in originals.items()}})
        for path in agents:
            configs[path].update(model=model, effort=effort, verbosity=level)
        configs[realm_path].update(default_model=model, default_effort=effort,
                                  default_verbosity=level)
        written = []
        try:
            for path in paths:
                util.write_json_atomic(path, configs[path])
                written.append(path)
        except OSError as exc:
            failed = []
            for path in reversed(written):
                try:
                    util.write_text_atomic(path, originals[path], newline="")
                except OSError:
                    failed.append(str(path.relative_to(root)))
            if failed:
                raise util.StateError(f"Could not restore {', '.join(failed)}. Original settings are in {backup}.") from exc
            raise util.StateError("Could not save the settings. All changes were restored.") from exc
    return {"ok": True, "agents": len(agents)}
