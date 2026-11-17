# `armada/webui/job_proposals.py`

Readable, escaped values and bounded inline comparisons for owner job review.

### class `_Document`

Keep safe rendered markup intact while comparing its visible text.

- `_Document.__init__(self, markup)` — —
- `_Document.handle_starttag(self, tag, attrs)` — —
- `_Document.handle_endtag(self, tag)` — —
- `_Document.handle_data(self, data)` — —
- `_Document.marked(self, spans, tag)` — —

### `_changed_spans(before, after)`

—

### `value_html(value, *, field='', absent=False)`

—

### `comparison(change)`

Two complete formatted values; only changed text receives diff marks.

### `review_html(review)`

—
