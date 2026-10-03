"""Transparent shell for Alexander's independent desktop companion."""
from __future__ import annotations

from ..assets import CSS_LINKS, ALEXANDER_JS
from .layout import _theme_style, _MODEBOOT_JS, dark_default
from .threadsview import _user_avatar
from .agentbits import _bust, _model_chip
from ._base import E
from .. import providers
from ..alexander import config


def render(realm_root=None) -> str:
    avatar = (_user_avatar(realm_root, 26) if realm_root is not None else "") or _bust(26, False)
    cfg = config.load()
    # Page rendering uses recorded connections; it must not launch provider CLI probes.
    connected = set(providers.connected())
    states = {p: {"connected": p in connected} for p in providers.NAMES}
    hint = ""
    try:
        provider, model, effort = config.resolve(realm_root, states=states)
        usage = f"Uses your {providers.NAMES[provider]} plan · counted as System"
    except ValueError as exc:
        model = cfg["model"] if cfg["model"] != "auto" else "Automatic"
        effort = cfg["effort"] if cfg["effort"] != "auto" else "Automatic"
        hint = str(exc)
        usage = "Counted as System usage"
    chip = _model_chip(model, effort, verbosity=cfg["verbosity"])
    if hint:
        chip = '<span title="' + E(hint) + '">' + chip + '</span>'
    root_class = 'mc-ax-window-root' + (' armada-dark' if dark_default() else '')
    return ('<!doctype html><html lang="en" class="' + root_class + '"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Alexander — ARMADA</title>' + CSS_LINKS + _theme_style() + _MODEBOOT_JS +
            '</head><body class="mc-ax-window-page"><template id="mc-ax-owner-avatar">' + avatar +
            '</template><template id="mc-ax-model-chip">' + chip +
            '</template><template id="mc-ax-usage">' + E(usage) +
            '</template>' + ALEXANDER_JS + '</body></html>')
