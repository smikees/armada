"""The thread rail's artifact headings link through to the full list, already filtered.

Clicking "Input artifacts" in a thread should land on the Artefacts page showing that agent's
inputs — not everything, and not with the filters left for the reader to reapply by hand.
"""
import re
from pathlib import Path

import pytest

from armada.webui.threadsview import _thread_arts_rail

_INPUTS = [{"name": "brief.png", "url": "/x"}]
_OUTPUTS = [{"name": "report.md", "path": "D:/report.md", "exists": True}]


def _links(html):
    return re.findall(r'href="([^"]+)"', html)


def test_headings_link_to_the_filtered_list():
    links = _links(_thread_arts_rail(_INPUTS, _OUTPUTS, "finance"))
    assert "/artefacts?owner=finance&type=input" in links
    assert "/artefacts?owner=finance&type=output" in links


def test_each_heading_carries_its_own_type():
    html = _thread_arts_rail(_INPUTS, _OUTPUTS, "finance")
    inp = html.index("Input artifacts")
    out = html.index("Output artifacts")
    assert "type=input" in html[:inp] or "type=input" in html[inp - 400:inp]
    assert "type=output" in html[out - 400:out]


def test_an_agent_id_needing_escaping_stays_in_the_path():
    links = _links(_thread_arts_rail(_INPUTS, [], "odd/name here"))
    assert "/artefacts?owner=odd%2Fname%20here&type=input" in links


def test_a_section_with_nothing_in_it_is_not_rendered():
    html = _thread_arts_rail([], _OUTPUTS, "finance")
    assert "Input artifacts" not in html
    assert "Output artifacts" in html


def test_no_link_without_an_agent():
    """Rendered outside an agent context there's nothing to filter by, so the heading stays text."""
    assert _links(_thread_arts_rail(_INPUTS, _OUTPUTS, "")) == []


def test_the_empty_rail_still_explains_itself():
    html = _thread_arts_rail([], [], "finance")
    assert "will appear here" in html


def test_the_artefacts_page_applies_url_filters():
    js = (Path(__file__).resolve().parents[1] / "armada" / "webui" / "static" / "js"
          / "artefacts.js").read_text(encoding="utf-8")
    assert "URLSearchParams" in js
    assert "['owner','art-owner']" in js and "['type','art-type']" in js
    assert "dd.dataset.val=val" in js, "the custom dropdown reads its value from data-val"
    assert "mc-fdrop-lbl" in js, "the pill must show the label, not stay on its placeholder"
