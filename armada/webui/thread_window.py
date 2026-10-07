"""The ordinary conversation pane in Alexander's independent window frame."""
from pathlib import Path

import json
from .. import reader, appconfig
from ..assets import CSS_LINKS, CHAT_JS, CONFIRM_JS, THREADLIST_JS, MODEBOOT_JS, js
from ..icons import _ICONS_JS, _icon
from ..thread_windows import target
from ._base import E
from .agentbits import _portrait
from .layout import _theme_style, dark_default
from .threadsview import _chat_center, _clear_thread_unread


def render(root, agent, thread):
    context, a, title, _ = target(root, agent, thread)
    _clear_thread_unread(Path(context.root) / "agents" / a.id, thread)
    classes = "mc-ax-window-root" + (" armada-dark" if dark_default() else "")
    owner = str((appconfig.load().get("user") or {}).get("name") or "You")
    heading = (
        f'<div class="mc-ax-portrait">{_portrait(root, a, 88, dot=True)}</div>'
        f'<div class="mc-thread-identity"><span class="mc-ax-name">{E(a.display)}</span>'
        f'<span class="mc-ax-subtitle" title="{E(reader.read(context.root).name)}">{E(reader.read(context.root).name)}</span></div>'
        f'<button type="button" class="mc-iconbtn" title="Close window" aria-label="Close window" data-thread-close>{_icon("x",16)}</button>'
    )
    return (
        f'<!doctype html><html lang="en" class="{classes}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="armada-companion" content="thread">'
        f'<title>{E(a.display)} · {E(title)} — ARMADA</title>'
        f'{CSS_LINKS}{_theme_style()}{MODEBOOT_JS}</head><body class="mc-ax-window-page">'
        '<div class="mc-ax is-window mc-thread-window"><section class="mc-ax-panel" aria-label="Thread">'
        f'<main class="mc-thread-window-content" style="--thread-owner:{E(json.dumps(owner, ensure_ascii=False))}">'
        f'{_chat_center(root, a, thread, lead=heading, detached=True)}</main>'
        '<button type="button" class="mc-thread-resize" aria-label="Resize window" '
        'title="Drag to resize; use arrow keys for smaller changes" data-thread-resize hidden>'
        '<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">'
        '<path d="M5 13L13 5M9 13L13 9" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>'
        '</button></section></div>'
        f'{_ICONS_JS}{CONFIRM_JS}{THREADLIST_JS}{CHAT_JS}{js("thread_window")}</body></html>'
    )


def unavailable(message):
    """Keep a stale companion closable without opening a different thread."""
    return (
        '<!doctype html><html class="mc-ax-window-root"><head><meta charset="utf-8">'
        f'{CSS_LINKS}{_theme_style()}{MODEBOOT_JS}</head><body class="mc-ax-window-page">'
        '<div class="mc-ax is-window mc-thread-window"><section class="mc-ax-panel">'
        '<header class="mc-ax-head pywebview-drag-region"><div class="mc-ax-who">Thread unavailable</div>'
        f'<button class="mc-iconbtn" aria-label="Close window" data-thread-close>{_icon("x",16)}</button></header>'
        f'<p style="padding:20px">{E(message)}</p></section></div>{js("thread_window")}</body></html>'
    )
