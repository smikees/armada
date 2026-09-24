"""Model catalog — the Claude models ARMADA offers in its dropdowns, synced from the live API list.

Design (see the model-picker discussion): API-driven, newest-first, no guidance text / no
primary-vs-more grouping. The list is fetched from Anthropic's /v1/models with the Claude Code OAuth
token (read-only — reuses usage_api's token reader, never refreshes/writes credentials) and cached
to <realm>/.armada/models.json so the dropdowns work offline and REMEMBER retired models. Retired
ids are kept in the cache (active:false, hidden from dropdowns) but run logs resolve model versions
independently (webui._pretty_model on the stored id), so a retired model still shows in usage.

Refresh happens lazily (a background pass when the cache is >~20h old and a valid token exists) and
on demand via `armada refresh-models`; either keeps the app in sync as Claude's lineup changes.
"""
from __future__ import annotations
import json
import math
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import usage_api
import logging
from .util import swallowed
log = logging.getLogger(__name__)

# --- token-consumption model (drives the model-icon colour gradient) --------------------------------
# Published API list prices, $ per million tokens (input, output). The /v1/models API does NOT expose
# pricing, so this is maintained by hand — update when Anthropic changes rates. Keyed by model family;
# an unknown family falls back to _PRICE_DEFAULT. (Sep 2026 rates.)
_PRICES = {"haiku": (1.0, 5.0), "sonnet": (3.0, 15.0), "opus": (5.0, 25.0), "fable": (10.0, 50.0)}
_PRICE_DEFAULT = (3.0, 15.0)                 # unknown model → treat as Sonnet-tier

# Effort → token-consumption multiplier. Effort scales ALL output (text, tool calls, thinking); per
# Anthropic's docs max effort can burn ~10× the tokens of low for the same prompt. Estimates, tunable.
_EFFORT_MULT = {"low": 1.0, "medium": 2.0, "high": 4.0, "xhigh": 7.0, "max": 10.0}
_EFFORT_DEFAULT = "high"


def model_family(model_id: str) -> str:
    d = (model_id or "").lower()
    return next((f for f in ("opus", "sonnet", "haiku", "fable") if f in d), "")


def prices_for(model_id: str) -> tuple[float, float]:
    """(input, output) $/Mtok for a model id or label; family lookup, default when unknown."""
    return _PRICES.get(model_family(model_id), _PRICE_DEFAULT)


def base_cost(model_id: str) -> float:
    """Output-weighted blended $/Mtok — the model's intrinsic consumption cost (output dominates)."""
    pin, pout = prices_for(model_id)
    return 0.25 * pin + 0.75 * pout


def effort_mult(effort: str) -> float:
    return _EFFORT_MULT.get((effort or _EFFORT_DEFAULT).lower(), _EFFORT_MULT[_EFFORT_DEFAULT])


# Verbosity moves the same dial as model and effort, but far less, and it is worth being clear why
# rather than pretending to a precision this does not have.
#
# Effort buys THINKING and verbosity buys WRITING, and the reply is the smaller half of an agent's
# output — reasoning tokens dominate at anything above low effort. So where effort spans 10x and the
# model families span roughly 60x, verbosity gets a 1.6x span: enough to move the marker visibly
# when you change it, not enough to outrank either of the other two.
#
# These four numbers are a judgement, not a measurement. ARMADA's run telemetry records tokens per
# run but not the verbosity that produced them, so there is nothing to fit a curve to yet. They are
# the right SHAPE — terse below standard, detailed above it — and the widget they feed is labelled
# "relative", which is the only claim being made.
_VERBOSITY_MULT = {"terse": 0.8, "brief": 0.9, "standard": 1.0, "full": 1.3}
_VERBOSITY_DEFAULT = "standard"


def verbosity_mult(level: str) -> float:
    return _VERBOSITY_MULT.get((level or _VERBOSITY_DEFAULT).lower(),
                               _VERBOSITY_MULT[_VERBOSITY_DEFAULT])


def _log_norm(value: float, lo: float, hi: float) -> int:
    """Map value∈[lo,hi] to 0..99 on a log scale (costs span ~100×, so log reads evenly)."""
    if value <= lo or hi <= lo:
        return 0
    if value >= hi:
        return 99
    return int(round(99 * (math.log(value) - math.log(lo)) / (math.log(hi) - math.log(lo))))


def _model_costs() -> list[float]:
    return [0.25 * pi + 0.75 * po for pi, po in _PRICES.values()]


def _combo_costs() -> list[float]:
    """Every model × effort × verbosity. The scale has to span what is actually reachable, or the
    marker can never touch either end."""
    return [(0.25 * pi + 0.75 * po) * m * v
            for pi, po in _PRICES.values()
            for m in _EFFORT_MULT.values()
            for v in _VERBOSITY_MULT.values()]


def model_index(model_id: str) -> int:
    """0..99 consumption index for a model on its own (relative to the cheapest/priciest model)."""
    costs = _model_costs()
    return _log_norm(base_cost(model_id), min(costs), max(costs))


def combo_index(model_id: str, effort: str, verbosity: str = "") -> int:
    """0..99 consumption index for a model + effort + verbosity combo, relative to the cheapest and
    priciest combination reachable. This is what the agent icon + config marker use.

    `verbosity` is optional and blank means the default, so a caller that only knows the model and
    the effort — the Usage breakdown, a model chip — still gets a sensible answer."""
    combos = _combo_costs()
    v = base_cost(model_id) * effort_mult(effort) * verbosity_mult(verbosity)
    return _log_norm(v, min(combos), max(combos))


def js_tables() -> dict:
    """The price/effort/verbosity tables + combo range, for the config page to compute the marker
    live in JS. The browser has to arrive at the same number this module would."""
    combos = _combo_costs()
    return {"prices": _PRICES, "priceDefault": list(_PRICE_DEFAULT),
            "effort": _EFFORT_MULT, "effortDefault": _EFFORT_DEFAULT,
            "verbosity": _VERBOSITY_MULT, "verbosityDefault": _VERBOSITY_DEFAULT,
            "comboMin": min(combos), "comboMax": max(combos)}

_ENDPOINT = "https://api.anthropic.com/v1/models?limit=100"
_UA = "claude-code/2.0.32 (ARMADA)"

# Fallback lineup so dropdowns are never empty before the first successful sync (best-effort ids;
# a live sync overwrites labels/order with the real display names + created dates). Newest first.
_SEED = [
    {"id": "claude-fable-5-1", "label": "Claude Fable 5.1"},
    {"id": "claude-opus-5", "label": "Claude Opus 5"},
    {"id": "claude-sonnet-5", "label": "Claude Sonnet 5"},
    {"id": "claude-haiku-4-5", "label": "Claude Haiku 4.5"},
    {"id": "claude-fable-5", "label": "Claude Fable 5"},
    {"id": "claude-opus-4-8", "label": "Claude Opus 4.8"},
    {"id": "claude-opus-4-7", "label": "Claude Opus 4.7"},
    {"id": "claude-opus-4-6", "label": "Claude Opus 4.6"},
    {"id": "claude-sonnet-4-6", "label": "Claude Sonnet 4.6"},
]
_TTL = 20 * 3600.0            # refresh at most ~daily
_lock = threading.Lock()
_last_try = 0.0


def _path(realm_root) -> Path:
    return Path(realm_root) / ".armada" / "models.json"


def _ordered(models_list: list[dict]) -> list[dict]:
    # newest first: dated entries by created_at descending (ISO sorts lexically), undated last
    dated = sorted((m for m in models_list if m.get("created_at")),
                   key=lambda m: m["created_at"], reverse=True)
    undated = [m for m in models_list if not m.get("created_at")]
    return dated + undated


def fetch_live_result() -> tuple:
    """(models, reason). `models` is None when nothing could be fetched, and `reason` says why.

    There are six distinct ways this can come back empty and they want different responses from
    the owner — a signed-out session is fixed by signing in, a switched-off sync isn't a problem at
    all, and only one of them is actually "Anthropic wasn't reachable". Collapsing them all into
    None meant the notification asserted a network fault whatever had happened, including when
    ARMADA had simply declined to ask."""
    if os.environ.get("ARMADA_NO_MODEL_SYNC"):
        return None, "off"                  # kill-switch: offline/deterministic (tests, air-gapped)
    tok = usage_api._read_token()
    if not tok:
        return None, "signed-out"
    access, exp_ms = tok
    if exp_ms and exp_ms <= int(time.time() * 1000) + 30_000:
        # Expired — the next agent run refreshes it. Nothing is wrong; we just can't ask right now.
        return None, "token-expired"
    req = urllib.request.Request(_ENDPOINT, headers={
        "Authorization": f"Bearer {access}", "anthropic-version": "2023-06-01",
        "anthropic-beta": usage_api._BETA, "User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=6.0) as r:
            body = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:   # noqa — caller keeps the cached catalog either way
        return None, f"http-{e.code}"
    except Exception as e:  # noqa
        log.debug('fetch_live_result: failed; error returned to the caller', exc_info=True)
        return None, f"unreachable ({type(e).__name__})"
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, list):
        return None, "unexpected-response"
    out = []
    for m in data:
        mid = m.get("id")
        if mid:
            out.append({"id": mid, "label": m.get("display_name") or mid,
                        "created_at": m.get("created_at") or ""})
    return (out, "") if out else (None, "empty-response")


def fetch_live() -> list[dict] | None:
    """Live /v1/models via the read-only OAuth token → [{id,label,created_at}] or None."""
    return fetch_live_result()[0]


def load(realm_root) -> dict:
    """Cached catalog {updated_at, models:[{id,label,created_at,active}]}; seeded if absent."""
    try:
        return json.loads(_path(realm_root).read_text("utf-8"))
    except Exception:  # noqa — missing/malformed → seed
        swallowed(log, 'load: failed; returning a fallback')
        return {"updated_at": "", "models": [{**m, "created_at": "", "active": True} for m in _SEED]}


def refresh(realm_root) -> dict:
    """Sync the cache from the live list: new ids added (active), missing ones marked retired
    (active:false, kept for history). No-op if the live list can't be fetched. Returns a summary."""
    live, why = fetch_live_result()
    if live is None:
        return {"ok": False, "reason": why or "unavailable"}
    cur = {m["id"]: m for m in load(realm_root).get("models", [])}
    live_ids = {m["id"] for m in live}
    merged = {}
    for m in live:
        pin, pout = prices_for(m["id"])               # store consumption prices alongside each model
        merged[m["id"]] = {**m, "active": True, "in": pin, "out": pout}
    for mid, m in cur.items():                        # keep previously-known ids as retired
        if mid not in live_ids:
            merged[mid] = {**m, "active": False}
    models = _ordered(list(merged.values()))
    added = sorted(live_ids - set(cur))
    retired = sorted(set(cur) - live_ids)
    data = {"updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "models": models}
    p = _path(realm_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    tmp.replace(p)                                    # atomic
    return {"ok": True, "count": len(models), "active": len(live_ids),
            "added": added, "retired": retired}


def _maybe_refresh_async(realm_root) -> None:
    """Kick a background refresh if the cache is stale and we haven't just tried (best-effort)."""
    global _last_try
    now = time.time()
    if now - _last_try < 3600:                        # don't retry more than hourly
        return
    cat = load(realm_root)
    fresh = False
    try:
        if cat.get("updated_at"):
            age = now - time.mktime(time.strptime(cat["updated_at"], "%Y-%m-%dT%H:%M:%S"))
            fresh = age < _TTL
    except Exception:  # noqa
        swallowed(log, '_maybe_refresh_async: failed; using a default')
        fresh = False
    if fresh:
        return
    _last_try = now
    threading.Thread(target=lambda: refresh(realm_root), daemon=True).start()


def options(realm_root) -> list[tuple[str, str]]:
    """(id, label) for active models, newest-first — for the config dropdowns. Triggers a lazy
    background refresh when the cache is stale; returns the current cache immediately (non-blocking)."""
    _maybe_refresh_async(realm_root)
    models = _ordered([m for m in load(realm_root).get("models", []) if m.get("active", True)])
    return [(m["id"], m.get("label") or m["id"]) for m in models]
