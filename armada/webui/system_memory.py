"""Shared read-only reader for app-wide instructions in Settings and Memory."""
from html import escape as E
from .. import system_memory
from ..assets import js
from ..icons import _icon


def reader():
    try:
        entry = system_memory.load()
    except (OSError, ValueError) as exc:
        return '<p role="alert">ARMADA system memories could not be loaded: ' + E(str(exc)) + '</p>'
    return (
        '<p class="mc-hint">Read-only instructions shared by all agents in every realm, including Alexander.</p>'
        '<div class="mc-system-memory-row">'
        f'<button type="button" id="mc-system-memory-open" class="btn-link" aria-haspopup="dialog">{E(entry.title)}</button>'
        f'<button type="button" id="mc-system-memory-file" class="mc-cap-ico" title="Go to file" '
        f'aria-label="Go to file for {E(entry.title)}">{_icon("go-to-file", 16)}</button></div>'
        '<div id="mc-system-memory-status" class="mc-hint" role="status"></div>'
        '<dialog id="mc-system-memory-dialog" class="mc-modal-box mc-system-memory-dialog" '
        'aria-labelledby="mc-system-memory-title">'
        '<div class="mc-system-memory-header">'
        f'<h2 id="mc-system-memory-title">{E(entry.title)}</h2>'
        '<form method="dialog"><button class="btn btn-secondary" autofocus>Close</button></form></div>'
        f'<div class="mc-system-memory-text" role="region" aria-label="Memory content" tabindex="0">'
        f'{E(entry.text if entry.text.strip() else "No instructions are configured.")}</div></dialog>'
        + js('system_memory'))
