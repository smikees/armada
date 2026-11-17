"""Stable destination frames for the two expensive, read-only inventory views."""
from ._base import _page_title
from ..assets import js

PAGES = {
    'artefacts': ('Artefacts', 'input & output files across the realm', '/api/artefacts-content'),
    'skills': ('Capabilities', 'who made it · what it can touch · your risk', '/api/capabilities-content'),
}


def frame(page, content, realm_root=None):
    title, subtitle, endpoint = PAGES[page]
    refresh = '<button type="button" class="btn btn-secondary btn-sm" onclick="location.reload()">Refresh</button>'
    actions = tabs = ''
    if page == 'skills':
        from .capabilities import page_controls
        actions, tabs = page_controls(realm_root)
    header = (f'<div class="mc-list-heading"><div>{_page_title(title, subtitle)}</div>'
              f'<div class="mc-list-actions">{actions}{refresh}</div></div>')
    pending = content is None
    if pending:
        # Controls retain their final geometry while their scripts are loading.
        header = header.replace('id="cap-actions"', 'id="cap-actions" data-page-controls inert')
        tabs = tabs.replace('data-page-controls', 'data-page-controls inert')
        content = (f'<div class="mc-list-loading" role="status"><span class="mc-loading-spinner" aria-hidden="true"></span>'
                   f' Loading {title.lower()}…</div>')
    return (f'<div class="mc-list-page">{header}{tabs}'
            f'<div id="mc-page-content" data-endpoint="{endpoint}" aria-busy="{str(pending).lower()}">{content}</div></div>'
            + (js('page_content') if pending else ''))


def document(realm, realm_root, page, dark=False, content=None):
    from .layout import _page_shell
    title = PAGES[page][0]
    return _page_shell(realm, title, title, frame(page, content, realm_root), dark)
