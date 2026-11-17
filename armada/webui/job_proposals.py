"""Readable, escaped values and bounded inline comparisons for owner job review."""
from difflib import SequenceMatcher
from html.parser import HTMLParser
import json
import re

from ._base import E, _md


class _Document(HTMLParser):
    """Keep safe rendered markup intact while comparing its visible text."""
    def __init__(self, markup):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.text = ''
        self.links = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        self.parts.append((self.get_starttag_text(), None, None))
        if tag == 'a':
            self.links.append([(key, value) for key, value in attrs if key in ('href', 'data-local-file')])
        if tag in ('br', 'p', 'li', 'tr', 'td', 'th', 'pre', 'h3', 'h4', 'h5', 'h6'):
            self.text += '\n'

    def handle_endtag(self, tag):
        self.parts.append((f'</{tag}>', None, None))
        if tag in ('p', 'li', 'tr', 'td', 'th', 'pre', 'h3', 'h4', 'h5', 'h6'):
            self.text += '\n'

    def handle_data(self, data):
        start = len(self.text)
        self.text += data
        self.parts.append((data, start, len(self.text)))

    def marked(self, spans, tag):
        out = []
        cursor = 0
        for text, start, end in self.parts:
            if start is None:
                out.append(text)
                continue
            while cursor < len(spans) and spans[cursor][1] <= start:
                cursor += 1
            position = start
            for lo, hi in spans[cursor:]:
                if lo >= end:
                    break
                lo, hi = max(start, lo), min(end, hi)
                out.append(E(text[position-start:lo-start]))
                out.append(f'<{tag}>' + E(text[lo-start:hi-start]) + f'</{tag}>')
                position = hi
            out.append(E(text[position-start:]))
        return ''.join(out)


def _changed_spans(before, after):
    tokens = [list(re.finditer(r'\s+|\w+|[^\w\s]', text)) for text in (before, after)]
    values = [[m.group() for m in matches] for matches in tokens]
    a, b = values
    prefix = 0
    while prefix < min(len(a), len(b)) and a[prefix] == b[prefix]:
        prefix += 1
    ae, be = len(a), len(b)
    while ae > prefix and be > prefix and a[ae-1] == b[be-1]:
        ae -= 1
        be -= 1
    # Large, repetitive prompts must not turn a local page render into quadratic work.
    if (ae-prefix) * (be-prefix) > 1_000_000:
        edits = [('replace', prefix, ae, prefix, be)]
    else:
        edits = [(kind, i+prefix, j+prefix, k+prefix, l+prefix)
                 for kind, i, j, k, l in SequenceMatcher(None, a[prefix:ae], b[prefix:be], autojunk=False).get_opcodes()]
    result = [[], []]
    for kind, i, j, k, l in edits:
        if kind != 'equal':
            for side, lo, hi in ((0, i, j), (1, k, l)):
                if lo < hi:
                    result[side].append((tokens[side][lo].start(), tokens[side][hi-1].end()))
    return result


def value_html(value, *, field='', absent=False):
    if absent:
        return '<p class="mc-prop-empty">Not set</p>'
    if isinstance(value, str):
        if not value:
            return '<p class="mc-prop-empty">Empty</p>'
        if field == 'prompt':
            return _md(value, preserve_breaks=True)
        return '<pre class="mc-prop-plain">' + E(value) + '</pre>'
    if value is None or isinstance(value, (bool, int, float)):
        return '<p>' + E('None' if value is None else 'Yes' if value is True else 'No' if value is False else str(value)) + '</p>'
    return '<pre class="mc-prop-code">' + E(json.dumps(value, ensure_ascii=False, indent=2)) + '</pre>'


def comparison(change):
    """Two complete formatted values; only changed text receives diff marks."""
    old = _Document(value_html(change['before'], field=change['field'], absent=change['added']))
    new = _Document(value_html(change['after'], field=change['field'], absent=change['removed']))
    note = ''
    if not change['added'] and not change['removed'] and (old.links != new.links or (
            old.text == new.text and (type(change['before']) is not type(change['after']) or change['before'] != change['after']))):
        # Do not conceal Markdown-only edits or a different link destination behind equal labels.
        old = _Document(value_html(change['before']))
        new = _Document(value_html(change['after']))
        note = '<p class="mc-prop-note">Formatting or link target changed; source shown for comparison.</p>'
        if old.text == new.text:
            old = _Document(value_html(json.dumps(change['before'], ensure_ascii=False)))
            new = _Document(value_html(json.dumps(change['after'], ensure_ascii=False)))
            note = '<p class="mc-prop-note">Value type changed; exact values shown for comparison.</p>'
    removed, added = ([(0, len(old.text))], [(0, len(new.text))]) if change['added'] or change['removed'] else _changed_spans(old.text, new.text)
    return old.marked(removed, 'del'), new.marked(added, 'ins'), note


def review_html(review):
    baseline = 'Approved value' if review['approved'] is not None else 'Saved value'
    rows = []
    for change in review['changes']:
        before, after, note = comparison(change)
        label = {'timeout': 'Time limit (seconds)', 'allow_tools': 'Tools allowed',
                 'run': 'Command', 'cron': 'Schedule', 'api_run_ceiling_usd': 'API ceiling (USD)'}.get(
                     change['field'], change['field'].replace('_', ' ').capitalize())
        rows.append(f'<section class="mc-prop-field" aria-label="{E(label)}">'
                    f'<h4>{E(label)}</h4>{note}<div class="mc-prop-values" tabindex="0" role="region" aria-label="{E(label)} comparison">'
                    f'<div class="mc-prop-value"><h5>{baseline}</h5><div class="mc-md">{before}</div></div>'
                    f'<div class="mc-prop-value"><h5>Proposed value</h5><div class="mc-md">{after}</div></div>'
                    '</div></section>')
    notice = '<p class="mc-prop-note">Approve replaces the saved job; Reject discards only this proposal.</p>'
    if review['approved'] is None:
        notice += '<p class="mc-prop-note">An older approval snapshot is unavailable; comparing with the saved job.</p>'
    elif review['approved'] != review['before']:
        notice += '<p class="mc-prop-warning">The saved file also differs from its last approved version. Review before approving.</p>'
    legend = '<div class="mc-prop-legend"><span><del>Removed</del> from approved / saved</span><span><ins>Added</ins> in proposed</span></div>'
    return notice + '<div class="mc-propdiff">' + (legend + ''.join(rows) if rows else '<p>No changed values.</p>') + '</div>'
