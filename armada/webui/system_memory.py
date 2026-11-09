"""The app-wide owner instruction editor, separate from generated realm memories."""
from html import escape as E
from .. import system_memory


def editor():
    try:
        saved = system_memory.load()
    except (OSError, ValueError) as exc:
        return '<p role="alert">System memory cannot be loaded: ' + E(str(exc)) + '</p>'
    return (
        '<p class="mc-muted">Owner instructions shared by all agents in every realm, including Alexander. '
        'Changes apply to their next turn. This is separate from each realm’s generated memory.</p>'
        '<label for="st-system-memory">ARMADA system memory</label>'
        f'<textarea id="st-system-memory" rows="14" maxlength="{system_memory.MAX_LENGTH}" '
        f'data-revision="{E(saved["revision"])}" data-default="{E(system_memory.DEFAULT)}" '
        'style="display:block;width:100%;box-sizing:border-box;resize:vertical;margin:8px 0;'
        'font:inherit;line-height:1.5">' + E(saved['text']) + '</textarea>'
        '<p class="mc-muted">Includes instructions for timed inbox tasks. Code enforces their windows '
        'even if this text is changed. A confirmed owner Process now action can override a valid window.</p>'
        '<button type="button" class="btn btn-secondary" onclick="mcRestoreSystemMemory()">Restore default text</button>'
        '<span id="st-system-memory-hint" role="status" style="margin-left:10px"></span>')
