# `armada/routes/__init__.py`

Handler mixins for `armada serve` (Phase 2, 2.3), grouped by area.

`serve.py`'s `Handler` class stays the single HTTP request handler and keeps its route tables
(`_GET_EXACT`, `_GET_PREFIX`, `_POST_JSON`) and core dispatch (`do_GET`/`do_POST`/`_route_get`/
`_route_post`, plus `_send`/`_json`/`_query`/`_body`/`_same_origin`) — only the handler METHOD
bodies moved here, grouped by area and mixed back into `Handler` via multiple inheritance. A pure
move: no behaviour change, and no module here is meant to be used on its own.
