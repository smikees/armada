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

### `_mini_pill(text: str, variant: str='plain', title: str='')`

Little label reusing the model-pill look (grey fill, --r radius) so we keep one badge style.

### `_poss(name: str)`

Possessive form (raw — caller should E() it): 'Marcus' → "Marcus’", 'Warren' → "Warren’s".
