"""Values interpolated into JavaScript inside HTML event attributes (found writing 5.8).

`onclick="f('{E(x)}')"` looks escaped and isn't: the HTML parser decodes `&#x27;` back into `'`
before the JavaScript parser runs, so a value with a quote closes the string and the rest runs as
code — with the app's full API one `fetch` away. Capability names come from third-party
marketplaces and thread titles from model output, so "the values are ours" doesn't hold.
`_base._J` JSON-encodes, then HTML-escapes; call sites use it without surrounding quotes.
"""
import html
import json
import re
from pathlib import Path

import pytest

from armada.webui._base import _J

WEBUI = Path(__file__).resolve().parents[1] / "armada" / "webui"


def test_no_html_escaped_value_is_quoted_into_an_event_attribute():
    bad = []
    for f in sorted(WEBUI.glob("*.py")):
        for i, ln in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r'\bon[a-z]+=\\?"', ln) and re.search(r"\\'\{E\(", ln):
                bad.append(f"{f.name}:{i}")
    assert not bad, "use {_J(x)} (no quotes) for values inside on*= attributes:\n  " + "\n  ".join(bad)


@pytest.mark.parametrize("value", [
    "plain", "O'Brien", 'say "hi"', "x');fetch('/api/restart',{method:'POST'});//",
    "back\\slash", "line\nbreak", "</script><script>alert(1)</script>", "ünïcødé ✓", "", None, 42,
])
def test_J_round_trips_through_an_attribute_and_a_js_parser(value):
    attr = _J(value)
    assert "'" not in attr and '"' not in attr and "<" not in attr   # can't close the attribute or a tag
    decoded = html.unescape(attr)              # what the JS engine sees after the HTML parser
    assert json.loads(decoded) == ("" if value is None else str(value))
