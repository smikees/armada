# `armada/models.py`

Model catalog — the Claude models ARMADA offers in its dropdowns, synced from the live API list.

Design (see the model-picker discussion): API-driven, newest-first, no guidance text / no
primary-vs-more grouping. The list is fetched from Anthropic's /v1/models with the Claude Code OAuth
token (read-only — reuses usage_api's token reader, never refreshes/writes credentials) and cached
to <realm>/.armada/models.json so the dropdowns work offline and REMEMBER retired models. Retired
ids are kept in the cache (active:false, hidden from dropdowns) but run logs resolve model versions
independently (webui._pretty_model on the stored id), so a retired model still shows in usage.

Refresh happens lazily (a background pass when the cache is >~20h old and a valid token exists) and
on demand via `armada refresh-models`; either keeps the app in sync as Claude's lineup changes.

### `model_family(model_id: str)`

—

### `prices_for(model_id: str)`

(input, output) $/Mtok for a model id or label; family lookup, default when unknown.

### `base_cost(model_id: str)`

Output-weighted blended $/Mtok — the model's intrinsic consumption cost (output dominates).

### `effort_mult(effort: str)`

—

### `verbosity_mult(level: str)`

—

### `_log_norm(value: float, lo: float, hi: float)`

Map value∈[lo,hi] to 0..99 on a log scale (costs span ~100×, so log reads evenly).

### `_model_costs()`

—

### `_combo_costs()`

Every model × effort × verbosity. The scale has to span what is actually reachable, or the marker can never touch either end.

### `model_index(model_id: str)`

0..99 consumption index for a model on its own (relative to the cheapest/priciest model).

### `combo_index(model_id: str, effort: str, verbosity: str='')`

0..99 consumption index for a model + effort + verbosity combo, relative to the cheapest and priciest combination reachable. This is what the agent icon + config marker use.

### `js_tables()`

The price/effort/verbosity tables + combo range, for the config page to compute the marker live in JS. The browser has to arrive at the same number this module would.

### `_path(realm_root)`

—

### `_ordered(models_list: list[dict])`

—

### `fetch_live_result()`

(models, reason). `models` is None when nothing could be fetched, and `reason` says why.

### `fetch_live()`

Live /v1/models via the read-only OAuth token → [{id,label,created_at}] or None.

### `load(realm_root)`

Cached catalog {updated_at, models:[{id,label,created_at,active}]}; seeded if absent.

### `refresh(realm_root)`

Sync the cache from the live list: new ids added (active), missing ones marked retired (active:false, kept for history). No-op if the live list can't be fetched. Returns a summary.

### `_maybe_refresh_async(realm_root)`

Kick a background refresh if the cache is stale and we haven't just tried (best-effort).

### `options(realm_root)`

(id, label) for active models, newest-first — for the config dropdowns. Triggers a lazy background refresh when the cache is stale; returns the current cache immediately (non-blocking).
