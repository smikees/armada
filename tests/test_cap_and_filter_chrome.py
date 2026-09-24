"""The status filter's swatches, and the capability card's chrome.

The filter dropdown carried its own table of flat colours. The legend it was supposed to match
gained tinted fills, a hollow border for Scheduled and a glyph for Missed — and the menu kept
offering the palette from two revisions earlier, so the same status looked like two different
things a centimetre apart. There is one definition now and the dropdown reads from it.
"""
import json
import re
from pathlib import Path

import pytest

from armada import reader
from armada.webui import agentbits as AB
from armada.webui import agentcommon as AC
from armada.webui import capabilities as CAP
from armada.webui import catalogue as WCAT   # the Catalogue tab's own rendering (Phase 2, 2.4)
from armada.webui import realmpages as R

STATIC = Path(R.__file__).parent / "static" / "js"


@pytest.fixture
def realm(tmp_path):
    root = tmp_path / "Cabinet-realm"
    ad = root / "agents" / "finance"
    (ad / "jobs").mkdir(parents=True)
    (root / "realm.json").write_text(json.dumps({"name": "Cabinet"}), encoding="utf-8")
    (ad / "agent.json").write_text(json.dumps({"id": "finance", "display": "Warren"}),
                                   encoding="utf-8")
    (ad / "jobs" / "alpha.json").write_text(json.dumps(
        {"id": "alpha", "name": "Alpha", "cron": "0 9 * * *", "prompt": "p"}), encoding="utf-8")
    return root


def _a(realm):
    return next(x for x in reader.read(str(realm)).agents if x.id == "finance")


# --------------------------------------------------------------------------- one swatch definition

def test_the_dropdown_and_the_legend_draw_the_same_swatch():
    """The actual bug: two renderers for one idea, and only one of them was kept up to date."""
    for bucket, label in AC._STATUS_FILTER_LABEL.items():
        want = AB._health_swatch(label, cls="mc-fdrop-dot")
        opts = [("", "All", ""), (bucket, label, label)]
        menu = AC._filter_dropdown("f", "All", opts)
        assert want in menu, f"{bucket} is not drawn with the legend's swatch"


def test_missed_is_the_glyph_in_the_menu_too():
    menu = AC._filter_dropdown("f", "All", [("none", "Missed", "Missed")])
    assert "M6 0C2.691" in menu, "the menu still draws a plain square for Missed"


def test_the_old_flat_colour_table_is_gone():
    """It listed a solid teal for Success the strip had not drawn since the tints landed."""
    assert AC._STATUS_FILTER_COLOR is AC._STATUS_FILTER_LABEL
    assert "var(--status-idle)" not in str(AC._STATUS_FILTER_LABEL)
    for v in AC._STATUS_FILTER_LABEL.values():
        assert v in AB._HEALTH_LEGEND_ORDER, f"{v} is not a status the legend knows"


def test_every_filter_bucket_has_a_swatch():
    from armada.webui.schedfmt import _STATUS_FILTERS
    for value, _label in _STATUS_FILTERS:
        assert value in AC._STATUS_FILTER_LABEL, f"{value} would render a blank swatch"


def test_the_swatch_travels_in_the_markup_not_as_a_colour():
    """A hollow border and an SVG do not survive being passed as a colour string."""
    js = (STATIC / "fdrop.js").read_text(encoding="utf-8")
    assert "function mcFDPick(el,fid,val,label,cb)" in js
    assert "outerHTML" in js
    menu = AC._filter_dropdown("f", "All", [("none", "Missed", "Missed")])
    assert "mcFDPick(this," in menu


def test_picking_an_option_still_clears_and_calls_back():
    js = (STATIC / "fdrop.js").read_text(encoding="utf-8")
    assert "mcFDClear" in js and "window[cb]()" in js


def test_a_dropdown_without_statuses_has_no_swatches():
    menu = AC._filter_dropdown("f", "All cadences", [("", "All cadences", ""), ("daily", "Daily", "")])
    assert "mc-fdrop-dot" not in menu


# --------------------------------------------------------------------------- the capability card

def _card(realm):
    return CAP._cap_card({"id": "x", "name": "windows-mcp", "status": "connected"},
                         kind="extensions", manage="realm")


def test_the_chevron_leads_the_row(realm):
    """It sat past the toggle and the bin, so the control that opens the row was the last one you
    reached — and the two lists opened from opposite ends."""
    c = _card(realm)
    summary = c[c.index("<summary"):c.index("</summary>")]
    assert summary.index("mc-cap-caret") < summary.index("mcCapToggle"), "chevron is still last"
    assert summary.index("mc-cap-caret") < summary.index("windows-mcp"), "chevron is not first"


def test_the_type_icon_sits_with_the_title(realm):
    c = _card(realm)
    head = c[c.index("mc-cap-caret"):c.index("windows-mcp")]
    assert "puzzle" in head or "<svg" in head, "the type icon is not next to the name"
    # …and no longer holds a column of its own
    assert "18px 300px" not in c


def test_the_row_still_has_its_columns(realm):
    c = _card(realm)
    assert re.search(r"grid-template-columns:14px 316px 88px 118px", c)


def test_the_actions_are_still_at_the_end(realm):
    c = _card(realm)
    summary = c[c.index("<summary"):c.index("</summary>")]
    assert "justify-self:end" in summary
    assert summary.index("mcCapToggle") < summary.index("mcCapDelete")


def test_opening_the_row_still_rotates_the_chevron():
    css = (Path(R.__file__).parent / "static" / "brand.css").read_text(encoding="utf-8")
    assert ".mc-cap[open] .mc-cap-caret" in css and "rotate(90deg)" in css


# --------------------------------------------------------------------------- the agent's legend

def test_the_agent_page_carries_the_legend(realm):
    html = CAP._tab_skills(reader.read(str(realm)), realm, _a(realm))
    for token in ("Trusted", "Review", "Caution", "Reads only", "Files"):
        assert token in html, f"legend missing {token}"


def test_it_is_the_same_legend_as_the_realm_page(realm):
    """Learning the colours on one page to use them on another is the thing this fixes."""
    html = CAP._tab_skills(reader.read(str(realm)), realm, _a(realm))
    assert CAP._cap_legend() in html


def test_the_legend_sits_in_a_rail_beside_the_cards(realm):
    html = CAP._tab_skills(reader.read(str(realm)), realm, _a(realm))
    assert "position:sticky" in html and "width:390px" in html


# --------------------------------------------------------------------------- the button

def test_the_update_button_says_what_it_checks(realm):
    html = CAP._tab_skills(reader.read(str(realm)), realm, _a(realm))  # not here…
    assert "Check for version updates" not in html
    from armada.webui import _core
    page = _core._realm_skills(reader.read(str(realm)), realm)          # …but on the realm page
    assert "Check for version updates" in page
    assert ">Check for updates<" not in page


# ------------------------------------------------------------- the Catalogue filters are the Jobs filters

def _cat_bar(realm):
    from armada import reader
    return WCAT._catalogue_pane(reader.read(str(realm)), str(realm))


def test_the_catalogue_uses_the_apps_filter_dropdown(realm):
    """It had plain <select>s. Two controls doing the same job, side by side in the same app,
    looking different — the filter bar is one thing, not one per page."""
    bar = _cat_bar(realm)
    for fid in ("cat-source", "cat-kind", "cat-author", "cat-category"):
        if f'id="{fid}"' in bar:
            assert f'<details class="mc-fdrop" id="{fid}"' in bar, f"{fid} is not the app's dropdown"
    assert "<select id=\"cat-" not in bar


def test_the_catalogue_search_box_matches_the_jobs_one(realm):
    bar = _cat_bar(realm)
    from armada.webui import _base
    assert f'style="{_base._FIELD};padding-left:30px;padding-right:26px"' in bar


def test_the_type_filter_carries_no_counts(realm):
    """Connectors and Extensions can only be counted by asking the registry, which is searched and
    never mirrored — so a count here would be the mirrored half of the answer wearing the whole
    answer's clothes."""
    bar = _cat_bar(realm)
    menu = bar[bar.index('id="cat-kind"'):]
    menu = menu[:menu.index("</details>")]
    for label in ("Connectors", "Extensions", "Skills", "Plugins"):
        assert f">{label}<" in menu, f"{label} is missing from the type filter"
    assert not re.search(r">(Connectors|Extensions|Skills|Plugins) \(\d", menu), \
        "the type filter is still showing counts"


def test_the_filters_are_read_from_data_val_not_value(realm):
    """The app's dropdown is a <details> carrying its value in data-val; only an <input> has
    .value. Reading .value would have made every filter silently do nothing."""
    js = (STATIC / "cat.js").read_text(encoding="utf-8")
    assert "e.dataset.val!==undefined" in js
    assert 'mcFDClear(MC_CAT_F,"mcCatFilter")' in js


def test_the_skill_file_icons_are_not_oversized(realm):
    it = {"id": "house-style", "name": "House style", "source": "custom"}
    html = CAP._cap_prov(it, "skills")
    sizes = [int(m) for m in re.findall(r'width="(\d+)" height="\d+"', html)]
    assert sizes and max(sizes) <= 16, f"an icon in the Contents row is still {max(sizes)}px"


def test_the_capabilities_page_loads_the_script_its_dropdowns_need(realm):
    """The regression: the page rendered the app's filter dropdown and never loaded fdrop.js, so
    clicking an option called an undefined function and the Catalogue's filters did nothing."""
    from armada import reader
    page = CAP._realm_skills(reader.read(str(realm)), str(realm))
    assert 'class="mc-fdrop"' in page, "the page uses the dropdown"
    # The SCRIPT TAG, not the onclick text — every menu row names mcFDPick whether or not the
    # function exists, which is exactly how this shipped broken.
    assert "/static/js/fdrop.js" in page, "…and must load the script that defines mcFDPick"


def test_the_user_filters_are_the_same_control_as_everywhere_else(realm):
    from armada import reader
    page = CAP._realm_skills(reader.read(str(realm)), str(realm))
    # cap-f-source, not cap-f-made: it filters where a capability came from now, which is what
    # its own "All sources" label always said it did.
    for fid in ("cap-f-type", "cap-f-avail", "cap-f-source", "cap-f-tier"):
        assert f'<details class="mc-fdrop" id="{fid}"' in page, f"{fid} is not the app's dropdown"
    assert '<select id="cap-f-' not in page
    from armada.webui import _base
    assert f'style="{_base._FIELD};padding-left:30px;padding-right:26px"' in page


def test_the_user_filters_read_data_val(realm):
    """Same trap as the Catalogue's: a <details> has no .value."""
    from armada import reader
    page = CAP._realm_skills(reader.read(str(realm)), str(realm))
    assert "/static/js/capfilter.js" in page, "…and must load the script that defines mcCapVal"
    js = (STATIC / "capfilter.js").read_text(encoding="utf-8")
    assert "mcCapVal" in js
    assert '.value' not in js.split("function mcCapFilter(){")[1].split("document.querySelectorAll")[0] \
        .replace('s.value', '').replace('(s&&s.value)', ''), "a filter is still being read with .value"
