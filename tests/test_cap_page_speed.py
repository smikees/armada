"""Opening Capabilities must not wait on the network.

Building the Catalogue's results queries the MCP registry. That call sat on the render path of the
whole page — so clicking Capabilities waited for it: about 700ms on a good day, and up to the
20-second timeout on a bad one, for a pane that starts hidden behind the User tab.
"""
import json
from pathlib import Path

import pytest

from armada import catalogue as C
from armada.webui import capabilities as CAP
from armada.webui import catalogue as WCAT   # the Catalogue tab's own rendering (Phase 2, 2.4)

_STATIC = Path(CAP.__file__).parent / "static" / "js"


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "_dir", lambda: tmp_path / "catalogue")
    monkeypatch.setattr(C, "_marketplaces_dir", lambda: tmp_path / "marketplaces")
    monkeypatch.setattr(C, "_skill_roots", lambda: [])
    monkeypatch.setattr(C, "_known_realms", lambda: [])
    C._reg_cache.clear()
    return tmp_path


@pytest.fixture
def realm(tmp_path):
    r = tmp_path / "realm"
    r.mkdir()
    (r / "realm.json").write_text(json.dumps({"name": "Test"}), encoding="utf-8")
    return r


def test_rendering_the_page_never_queries_the_registry(realm, monkeypatch):
    """The test that would have caught this: fail loudly if anything reaches the network while
    the page is being built."""
    from armada import reader

    def forbidden(url):
        pytest.fail(f"the page render fetched {url} — that is the lag")
    monkeypatch.setattr(C, "_get_json", forbidden)
    CAP._realm_skills(reader.read(str(realm)), realm)


def test_the_results_area_arrives_as_a_placeholder(realm, monkeypatch):
    from armada import reader
    monkeypatch.setattr(C, "_get_json", lambda url: pytest.fail("network on render"))
    pane = WCAT._catalogue_pane(reader.read(str(realm)), realm)
    assert 'id="cat-results" data-pending="1"' in pane
    assert "mc-cat-skel" in pane, "a spinner-less blank would let the filter bar jump"
    assert "Loading the catalogue" in pane


def test_everything_knowable_locally_is_still_rendered(realm, monkeypatch):
    """Only the results defer. The filter bar and the explainer come from the local index, and
    deferring those too would trade one blank moment for a bigger one."""
    from armada import reader
    monkeypatch.setattr(C, "_get_json", lambda url: pytest.fail("network on render"))
    pane = WCAT._catalogue_pane(reader.read(str(realm)), realm)
    assert 'id="cat-source"' in pane and 'id="cat-kind"' in pane
    assert "Capability types" in pane


def test_the_script_that_loads_them_is_defined_before_the_one_that_calls_it(realm):
    """It wasn't: tab_js restored the saved tab and called mcCatFilter, which _CAT_JS had not yet
    defined. The skeleton stayed up forever, and because the one-shot flag was cleared first there
    was nothing left to retry it. Now each lives in its own static module, loaded in page order —
    so the ordering that matters is which <script src> tag comes first."""
    from armada import reader
    html = CAP._realm_skills(reader.read(str(realm)), realm)
    assert html.index("/static/js/cat.js") < html.index("/static/js/captab.js")
    assert "function mcCatFilter" in (_STATIC / "cat.js").read_text(encoding="utf-8")
    assert "function mcCapTab" in (_STATIC / "captab.js").read_text(encoding="utf-8")


def test_the_one_shot_flag_survives_a_call_that_cannot_happen(realm):
    js = (_STATIC / "captab.js").read_text(encoding="utf-8")
    i = js.index('if(t==="catalogue"')
    seg = js[i:i + 260]
    assert 'typeof mcCatFilter==="function"' in seg
    assert seg.index("typeof mcCatFilter") < seg.index("delete box.dataset.pending")


# --- the explainer's chrome ----------------------------------------------------------------------

def test_the_explainer_is_headed_like_an_overview_widget(realm):
    from armada import reader
    pane = WCAT._catalogue_pane(reader.read(str(realm)), realm)
    assert 'summary class="mc-wid-h"' in pane, "same class, so the two can't drift apart"
    # .mc-wid-h carries only the background; a widget header's padding and rule are inline.
    seg = pane[pane.index('summary class="mc-wid-h"'):][:400]
    assert "padding:8px 12px" in seg
    assert "border-bottom:1px solid transparent" in seg


def test_the_explainer_is_not_narrower_than_the_filters(realm):
    """It shared a row with Refresh catalogue and so stopped 133px short of the filter bar below
    it — which reads as a box that didn't quite fit rather than one deliberately narrower."""
    from armada import reader
    pane = WCAT._catalogue_pane(reader.read(str(realm)), realm)
    assert "max-width:860px" not in pane
    # Nothing shares the explainer's row: it is the first thing in the pane.
    assert pane.index('class="mc-catinfo') < pane.index("Refresh catalogue")


def test_refresh_sits_at_the_right_end_of_the_filter_row(realm):
    """It had a line of its own above the explainer, for one button and a timestamp. The filter
    row had room, and these are controls for the same list."""
    from armada import reader
    pane = WCAT._catalogue_pane(reader.read(str(realm)), realm)
    bar = pane[pane.index('id="cat-q"'):pane.index('id="cat-results"')]
    assert "Refresh catalogue" in bar, "it is not inside the filter row"
    # Pushed right by auto margin rather than a spacer, so it wraps with the filters on a narrow
    # pane instead of holding the row open.
    assert "margin-left:auto" in bar[bar.index("cat-clear"):]
    assert bar.index("cat-clear") < bar.index("Refresh catalogue"), "after Clear, not before it"


# --- the Overview header -------------------------------------------------------------------------

def test_the_limits_block_starts_its_content_at_the_top():
    """Both a KPI cell and the limits block are 62px tall, but a KPI stacks caption-then-value from
    the top while this centred its whole block — putting "CLAUDE SUBSCRIPTION LIMITS" a few pixels
    below every other caption on the row. Measured in the browser: all six captions now sit at the
    same y."""
    from pathlib import Path
    src = Path(__file__).resolve().parents[1] / "armada" / "webui" / "pages.py"
    t = src.read_text(encoding="utf-8")
    i = t.index('id="mc-hdr-limits"')
    seg = t[i:i + 200]
    assert "justify-content:flex-start" in seg
    assert "justify-content:center" not in seg
