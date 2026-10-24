# `armada/webui/_math.py`

Protect explicit TeX spans before the shared safe Markdown parser touches them.

### `protect(text)`

Return Markdown plus a restoration function; source HTML remains escaped later.
