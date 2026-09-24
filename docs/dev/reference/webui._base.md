# `armada/webui/_base.py`

Base layer — shared low-level UI primitives (carved from _core.py in Phase 3).

The foundation every renderer builds on: HTML escaping, form-field style constants, the safe
Markdown renderer, and small label formatters. Depends ONLY on stdlib, so any module (including
future component modules) can import from here without touching _core — this is what lets the
mid-DAG renderers be carved out later without import cycles.

### `_J(value)`

A value as a JavaScript string literal, safe inside an HTML event attribute (onclick="…").

### `_md_inline(s: str)`

Inline Markdown on already-HTML-escaped text: code, bold, italic, links.

### `_list_items(lines: list[str], i: int, n: int, pat: str)`

Collect one list's items, folding hard-wrapped continuation lines back into their item.

### `_md(text: str)`

Render a safe subset of Markdown to HTML. The input is untrusted, so it is HTML-escaped first — only the whitelisted tags emitted below can appear. Supports headings, bullet/number lists, tables, code fences, inline code/bold/italic/links, and paragraphs.

### `_page_title(t: str, sub: str='', right: str='', right_html: str='')`

`right` is muted text set alongside the heading; `right_html` is markup (a button, say) and is NOT escaped — pass only markup this code built, never anything user-supplied.

### `_chip(text: str, variant: str='plain', title: str='')`

A chip (DESIGN_SYSTEM §7): the model-pill look — grey fill, --r radius — for a label that names something (a model, a kind), where a pill states a status. `.mc-chip`, UI audit P3.

### `_tone(col: str)`

The pill tone for a status colour: 'var(--status-ok)' or '--status-ok' → 'ok'. Anything else (idle, muted) is 'neutral'.

### `_pill(inner: str, tone: str='neutral', title: str='', style: str='')`

A status pill. `inner` is HTML (escape text before passing it).

### `_poss(name: str)`

Possessive form (raw — caller should E() it): 'Marcus' → "Marcus’", 'Warren' → "Warren’s".
