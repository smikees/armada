# `armada/webui/consumption.py`

Token-consumption gradient + model-colour mapping (carved from _core.py in Phase 3).

A pure lower layer: depends only on the models catalogue and stdlib, never on _core helpers,
so _core (and pages) import these names back without any import cycle.

### `_model_color(label: str, i: int=0)`

—

### `_grad_rgb(t: float)`

—

### `_consumption_color(index: int)`

—

### `_consumption_gradient_css()`

—

### `_consumption_js(realm, model_id: str='c-model', effort_id: str='c-effort', marker_id: str='c-consmarker', mark_scope: str='', verbosity_id: str='')`

Client mirror of models.combo_index + the gradient sampler, so a model/effort/verbosity picker moves its marker and recolours its model icon live (no server round-trip). `mark_scope` limits which .mc-modelmark icons get recoloured (a CSS-selector prefix) so two pickers on one page don't clash. `verbosity_id` is optional: a form without a verbosity field falls back to the realm's own default, which is what such an agent would actually inherit.

### `_model_is_claude(label: str)`

True for a real Claude model label (not Mock/Unknown/empty) — gates the Claude icon.
