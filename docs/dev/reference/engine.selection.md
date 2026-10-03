# `armada/engine/selection.py`

Resolve the provider from the chosen model, keeping old Claude realms readable.

### `read_config(path)`

—

### `model_provider(model: str)`

—

### `enabled_providers(realm_root)`

—

### `engine_for(realm_root, agent=None, job=None, override=None)`

Explicit CLI override → job model → agent model → realm model → legacy engine.
