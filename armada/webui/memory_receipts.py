"""Saved memory provenance for one run, never inferred from today's files."""
from ._base import E


def render(receipt):
    if not isinstance(receipt, dict):
        return ''
    items = []
    labels = {'app': 'App', 'system': 'System', 'realm': 'Realm', 'agent': 'Private'}
    for item in receipt.get('items', []):
        stamp = item.get('refreshed') or item.get('updated')
        version = f' · {stamp}' if stamp else ''
        items.append(f'<li title="{E(item.get("sha256", ""))}"><b>{E(item.get("title", ""))}</b> '
                     f'· {E(labels.get(item.get("scope"), "Memory"))}{E(version)}'
                     f'<br><span style="overflow-wrap:anywhere">{E(item.get("path", ""))}</span></li>')
    return ('<details class="mc-memory-receipt" style="font-size:11px;color:var(--text-muted);margin:8px 0">'
            f'<summary>Memories received · {len(items)}</summary>'
            f'<p>Recorded for this run at {E(receipt.get("captured", ""))}.</p>'
            f'<ul>{"".join(items)}</ul></details>')
