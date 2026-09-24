"""Token-consumption gradient + model-colour mapping (carved from _core.py in Phase 3).

A pure lower layer: depends only on the models catalogue and stdlib, never on _core helpers,
so _core (and pages) import these names back without any import cycle.
"""
from __future__ import annotations
import json
from .. import models
from ..assets import CONSUMPTION_JS as _CONSUMPTION_JS_ASSET
import logging
from ..util import swallowed
log = logging.getLogger(__name__)


_MODEL_CLR = {"Opus": "#8b5cf6", "Sonnet": "#2563eb", "Haiku": "#0ea5a4", "Fable": "#e0761b",
              "Mock (offline)": "var(--color-neutral-300)", "Unknown": "var(--color-neutral-400)"}
_MODEL_FALLBACK = ["#db2777", "#65a30d", "#0891b2", "#ca8a04", "#7c3aed"]


def _model_color(label: str, i: int = 0) -> str:
    # colour a model by its token-consumption index on the shared gradient (light = low, dark = high);
    # non-Claude labels (Mock/Unknown/other) fall back to the neutral palette.
    if _model_is_claude(label):
        return _consumption_color(models.model_index(label))
    return _MODEL_CLR.get(label) or _MODEL_CLR.get(label.split()[0] if label else "") \
        or _MODEL_FALLBACK[i % len(_MODEL_FALLBACK)]


_MODEL_FAMILY_BASE = {"Opus": "#7c3aed", "Sonnet": "#2563eb", "Haiku": "#0ea5a4", "Fable": "#e0761b"}

_CONSUMPTION_STOPS = [(0.0, (0x46, 0x9B, 0x52)), (0.28, (0x93, 0xBF, 0x4E)), (0.52, (0xF1, 0xCB, 0x3F)),
                      (0.76, (0xE2, 0x7D, 0x2F)), (1.0, (0xC4, 0x3A, 0x2E))]


def _grad_rgb(t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    for i in range(1, len(_CONSUMPTION_STOPS)):
        p0, c0 = _CONSUMPTION_STOPS[i - 1]
        p1, c1 = _CONSUMPTION_STOPS[i]
        if t <= p1:
            f = 0.0 if p1 == p0 else (t - p0) / (p1 - p0)
            return tuple(round(c0[k] + (c1[k] - c0[k]) * f) for k in range(3))
    return _CONSUMPTION_STOPS[-1][1]


def _consumption_color(index: int) -> str:
    r, g, b = _grad_rgb(max(0, min(99, int(index))) / 99.0)
    return f"#{r:02x}{g:02x}{b:02x}"


def _consumption_gradient_css() -> str:
    return "linear-gradient(90deg," + ",".join(
        f"#{c[0]:02x}{c[1]:02x}{c[2]:02x} {round(p * 100)}%" for p, c in _CONSUMPTION_STOPS) + ")"


def _consumption_js(realm, model_id: str = "c-model", effort_id: str = "c-effort",
                    marker_id: str = "c-consmarker", mark_scope: str = "",
                    verbosity_id: str = "") -> str:
    """Client mirror of models.combo_index + the gradient sampler, so a model/effort/verbosity picker
    moves its marker and recolours its model icon live (no server round-trip). `mark_scope` limits
    which .mc-modelmark icons get recoloured (a CSS-selector prefix) so two pickers on one page don't
    clash. `verbosity_id` is optional: a form without a verbosity field falls back to the realm's own
    default, which is what such an agent would actually inherit."""
    from .. import verbosity as _verbosity
    C = models.js_tables()
    C["stops"] = [[p, list(c)] for p, c in _CONSUMPTION_STOPS]
    C["defaultModel"] = getattr(realm, "default_model", "") or "Claude Opus 4.8"
    C["defaultEffort"] = getattr(realm, "default_effort", "") or "high"
    try:
        C["defaultVerbosity"] = _verbosity.realm_level(realm.root)
    except Exception:  # noqa — no realm root to read is not a reason to break the widget
        swallowed(log, '_consumption_js: failed; using a default')
        C["defaultVerbosity"] = _verbosity.DEFAULT
    sel = json.dumps((mark_scope + " " if mark_scope else "") + ".mc-modelmark")
    # Static logic (fam/price/idx/grad/the picker wiring) lives in webui/static/js/consumption.js
    # as mcConsumptionInit(C,MID,EID,KID,VID,SEL) (Phase 2, 2.1); only this call's own data and
    # element ids are inline.
    call = ("mcConsumptionInit(" + json.dumps(C) + "," + json.dumps(model_id) + ","
            + json.dumps(effort_id) + "," + json.dumps(marker_id) + "," + json.dumps(verbosity_id)
            + "," + sel + ");")
    return _CONSUMPTION_JS_ASSET + "<script>" + call + "</script>"


def _model_is_claude(label: str) -> bool:
    """True for a real Claude model label (not Mock/Unknown/empty) — gates the Claude icon."""
    low = (label or "").lower()
    if not low or low.startswith("mock") or low == "unknown":
        return False
    return "claude" in low or any(f in low for f in ("opus", "sonnet", "haiku", "fable"))
