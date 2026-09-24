"""Markdown shown as prose, and one agent order across the whole app.

Two shapes of the same mistake. A document written in headings and lists was being displayed as
its source, on the pages where you read an agent's character; and every list of agents sorted
itself, so the Ministers grid, the Memory sidebar and the capability roster disagreed about the
order of one cabinet.
"""
import datetime
import inspect
import json
from pathlib import Path

import pytest

from armada import reader
from armada.webui import agentframe as AF
from armada.webui import memoryview as MV

_STATIC_JS = Path(AF.__file__).parent / "static" / "js"

COV = "# The Covenant\n\n## 1. Whose you are\n\n- Mihai is the **only** master you serve.\n"


@pytest.fixture
def realm(tmp_path):
    r = tmp_path / "Cabinet-realm"
    (r / "memory").mkdir(parents=True)
    (r / "realm.json").write_text(json.dumps({"name": "Cabinet", "owner": "M"}), encoding="utf-8")
    # deliberately out of order on disk, and the coordinator is not first alphabetically
    for aid, disp, coord in (("finance", "Warren", False), ("hand", "Marcus", True),
                             ("development", "Steve", False), ("education", "Aristotle", False),
                             ("travel", "Ibn Battuta", False)):
        d = r / "agents" / aid
        d.mkdir(parents=True)
        (d / "agent.json").write_text(json.dumps(
            {"id": aid, "display": disp, "coordinator": coord, "role": "R"}), encoding="utf-8")
    (r / "tenets.md").write_text(COV, encoding="utf-8")
    return r


# --------------------------------------------------------------------------- ordering

def test_coordinator_first_then_alphabetical(realm):
    m = reader.read(str(realm))
    assert [a.display for a in m.agents] == ["Marcus", "Aristotle", "Ibn Battuta", "Steve", "Warren"]


def test_members_inherit_the_same_order(realm):
    """members derives from agents, so one sort settles both."""
    m = reader.read(str(realm))
    assert [a.display for a in m.members] == ["Aristotle", "Ibn Battuta", "Steve", "Warren"]


def test_several_coordinators_are_alphabetical_among_themselves(realm):
    p = realm / "agents" / "finance" / "agent.json"
    p.write_text(json.dumps({"id": "finance", "display": "Warren", "coordinator": True}),
                 encoding="utf-8")
    m = reader.read(str(realm))
    assert [a.display for a in m.agents][:2] == ["Marcus", "Warren"]


def test_sorting_is_by_display_name_not_folder(realm):
    """'Ibn Battuta' sorts under I, not under 'travel'."""
    m = reader.read(str(realm))
    ids = [a.id for a in m.agents]
    assert ids.index("travel") < ids.index("development"), ids


def test_case_does_not_scatter_the_list(realm):
    (realm / "agents" / "estate").mkdir()
    (realm / "agents" / "estate" / "agent.json").write_text(
        json.dumps({"id": "estate", "display": "palladio"}), encoding="utf-8")
    m = reader.read(str(realm))
    names = [a.display for a in m.members]
    assert names == sorted(names, key=str.casefold)


def test_a_realm_with_no_coordinator_is_simply_alphabetical(realm):
    p = realm / "agents" / "hand" / "agent.json"
    p.write_text(json.dumps({"id": "hand", "display": "Marcus", "coordinator": False}),
                 encoding="utf-8")
    m = reader.read(str(realm))
    assert [a.display for a in m.agents] == ["Aristotle", "Ibn Battuta", "Marcus", "Steve", "Warren"]


def test_the_order_is_applied_at_the_single_entry_point():
    """Both realm formats go through read(); ordering per page is what let them drift."""
    src = inspect.getsource(reader.read)
    assert src.count("order_agents") == 2


# --------------------------------------------------------------------------- Covenant reading view

def test_the_covenant_reads_as_rendered_html(realm):
    """The rendered HTML is escaped inside a <template> for the JS to decode, so assert on the
    escaped form. _md maps '#' to h3 — headings are embedded in a page, not page titles."""
    modal = MV._covenant_modal(realm)
    assert "&lt;h3&gt;" in modal or "&lt;h4&gt;" in modal, "headings not rendered"
    assert "&lt;strong&gt;" in modal or "&lt;b&gt;" in modal, "emphasis not rendered"
    assert "&lt;ul&gt;" in modal or "&lt;li&gt;" in modal, "lists not rendered"
    assert "## 1. Whose" not in modal.split("mc-cov-raw")[0], "source leaked into the reading view"


def test_raw_markdown_is_kept_for_the_editor_only(realm):
    modal = MV._covenant_modal(realm)
    assert 'id="mc-cov-rendered"' in modal
    assert "/static/js/covenant.js" in modal
    assert "mcCovDecode(\"mc-cov-raw\")" in (_STATIC_JS / "covenant.js").read_text(encoding="utf-8")


def test_nothing_is_parsed_in_the_browser(realm):
    """Two markdown renderers is how a preview starts disagreeing with the page."""
    modal = MV._covenant_modal(realm)
    assert "window.mcMd" not in modal
    assert "<pre" not in modal, "the fallback that displayed hashes and hyphens"


def test_an_empty_covenant_reads_as_a_prompt_not_a_blank(tmp_path):
    r = tmp_path / "r"
    r.mkdir()
    assert "Nothing written yet" in MV._covenant_modal(r)


# --------------------------------------------------------------------------- Configure fields

def test_configure_fields_render_by_default(realm):
    m = reader.read(str(realm))
    a = next(x for x in m.agents if x.id == "hand")
    (realm / "agents" / "hand" / "soul.md").write_text("# Marcus\n\nAfter **Agrippa**.\n",
                                                       encoding="utf-8")
    html = AF._tab_configure(m, realm, a)
    assert 'id="c-soul-view"' in html
    assert "<strong>Agrippa</strong>" in html or "<b>Agrippa</b>" in html


def test_the_textarea_survives_for_saving(realm):
    """mcSaveAgent reads these ids; hiding the field must not remove it."""
    m = reader.read(str(realm))
    a = next(x for x in m.agents if x.id == "hand")
    html = AF._tab_configure(m, realm, a)
    for fid in ("c-soul", "c-mandate", "c-tenets"):
        assert f'<textarea id="{fid}"' in html
        assert f'id="{fid}-view"' in html


def test_the_editor_starts_hidden(realm):
    m = reader.read(str(realm))
    a = next(x for x in m.agents if x.id == "hand")
    html = AF._tab_configure(m, realm, a)
    block = html.split('<textarea id="c-soul"')[1].split("</textarea>")[0]
    assert "display:none" in block


def test_an_empty_field_says_so(realm):
    m = reader.read(str(realm))
    a = next(x for x in m.agents if x.id == "education")
    assert "Nothing yet." in AF._tab_configure(m, realm, a)


def test_there_is_still_only_the_servers_markdown_renderer(realm):
    """Clicking away previews unsaved text — by asking the server to render it, not by parsing
    markdown in the browser. Two renderers is how a preview starts disagreeing with the page."""
    js = (_STATIC_JS / "mdfield.js").read_text(encoding="utf-8")
    assert "/api/render-md" in js
    assert "mcMd(" not in js and "marked" not in js


def test_clicking_away_leaves_edit_mode(realm):
    """So you can check your formatting without committing it."""
    m = reader.read(str(realm))
    a = next(x for x in m.agents if x.id == "hand")
    html = AF._tab_configure(m, realm, a)
    assert 'onblur="mcMdBlur(&#x27;c-soul&#x27;)"' in html or 'onblur="mcMdBlur(\'c-soul\')"' in html
    js = (_STATIC_JS / "mdfield.js").read_text(encoding="utf-8")
    assert "mcMdEdit(id,false);}" in js.split("mcMdBlur")[1]


def test_a_preview_is_marked_unsaved(realm):
    """The rendered view after a blur shows text that is not on disk; saying so is the difference
    between a preview and a lie."""
    m = reader.read(str(realm))
    a = next(x for x in m.agents if x.id == "hand")
    html = AF._tab_configure(m, realm, a)
    for fid in ("c-soul", "c-mandate", "c-tenets"):
        assert f'id="{fid}-dirty"' in html
    mdfield_js = (_STATIC_JS / "mdfield.js").read_text(encoding="utf-8")
    blur = mdfield_js.split("mcMdBlur")[1]
    assert "data-orig" in blur, "no baseline to compare against"
    assert 'd.style.display=dirty?"":"none"' in blur
    # and saving clears it — the text on screen is the text on disk again
    js = (Path(__file__).resolve().parents[1] / "armada" / "webui" / "static" / "js" / "agent.js"
          ).read_text(encoding="utf-8")
    tick = js.split("function mcSavedTick")[1].split("\nasync function")[0]
    assert "setAttribute('data-orig',t.value)" in tick and "d.style.display='none'" in tick


def test_the_rendered_view_is_itself_the_edit_affordance(realm):
    """Clicking the text starts editing — anything that looks like a document should."""
    m = reader.read(str(realm))
    a = next(x for x in m.agents if x.id == "hand")
    html = AF._tab_configure(m, realm, a)
    view = html.split('id="c-soul-view"')[1].split(">")[0]
    assert "mcMdEdit(&#x27;c-soul&#x27;,true)" in view or "mcMdEdit('c-soul',true)" in view
    assert "cursor:text" in view


def test_text_is_escaped_once_per_destination_not_twice(realm):
    """The field was escaped before _md_field, which escapes again for each destination. So the
    reader saw "doesn&amp;#x27;t" and — worse — the textarea decoded one level, meaning the next
    Save wrote "doesn&#x27;t" into mandate.md. Three files on disk had to be repaired."""
    (realm / "agents" / "hand" / "mandate.md").write_text(
        "Hold the picture, so Mihai doesn't have to. A & B <tag>\n", encoding="utf-8")
    m = reader.read(str(realm))
    a = next(x for x in m.agents if x.id == "hand")
    html = AF._tab_configure(m, realm, a)
    assert "&amp;#x27;" not in html, "apostrophe escaped twice"
    assert "&amp;amp;" not in html, "ampersand escaped twice"
    view = html.split('id="c-mandate-view"')[1].split('<textarea')[0]
    assert "doesn&#x27;t" in view and "A &amp; B" in view and "&lt;tag&gt;" in view


def test_the_textarea_round_trips_the_file_byte_for_byte(realm):
    """What you'd send back to /api/save-agent has to be what was read, or saving corrupts it."""
    import html as _h
    raw = "It's a \"quote\" & an <angle>\n"
    (realm / "agents" / "hand" / "soul.md").write_text(raw, encoding="utf-8")
    m = reader.read(str(realm))
    a = next(x for x in m.agents if x.id == "hand")
    page = AF._tab_configure(m, realm, a)
    in_ta = page.split('<textarea id="c-soul"')[1].split(">", 1)[1].split("</textarea>")[0]
    assert _h.unescape(in_ta) == raw.strip()


def test_the_field_keeps_its_height_when_it_turns_into_an_editor(realm):
    """It used to snap back to min-height on click, so a long Soul became an 80px box and the page
    jumped under the cursor. Both boxes are border-box, so offsetHeight transfers directly."""
    js = (_STATIC_JS / "mdfield.js").read_text(encoding="utf-8")
    assert "v.offsetHeight" in js
    assert 't.style.height=h+"px"' in js
    # measured before the view is hidden — a display:none element has no offsetHeight
    assert js.index("v.offsetHeight") < js.index('v.style.display=on?"none"')


# --------------------------------------------------------------------------- sticky Save / Cancel

def test_save_and_cancel_share_a_row(realm):
    m = reader.read(str(realm))
    a = next(x for x in m.agents if x.id == "hand")
    rail = AF._configure_actions(a)
    row = rail.split('<div style="display:flex;gap:8px">')[1].split("</div>")[0]
    assert "Save" in row and "Cancel" in row
    assert row.count("flex:1") == 2, "they should split the width evenly"


def test_opening_advanced_brings_it_into_view(realm):
    """It is the last thing on the page, so opening it otherwise reveals content below the fold."""
    m = reader.read(str(realm))
    a = next(x for x in m.agents if x.id == "hand")
    html = AF._tab_configure(m, realm, a)
    assert "ontoggle=" in html and "mcRevealSection" in html
    assert "/static/js/reveal.js" in AF._REVEAL_JS
    js = (_STATIC_JS / "reveal.js").read_text(encoding="utf-8")
    assert ".mc-appscroll" in js, "the window doesn't scroll; that element does"
    # whole section if it fits, otherwise its heading at the top
    assert "h+pad*2<=vh" in js and "top-pad" in js


def test_save_and_cancel_are_pinned_beside_the_form(realm):
    """The page is long enough that Save at the bottom meant scrolling past everything you hadn't
    touched to commit a one-word change."""
    m = reader.read(str(realm))
    a = next(x for x in m.agents if x.id == "hand")
    rail = AF._configure_actions(a)
    assert "position:sticky" in rail
    assert 'id="c-save"' in rail and "mcSaveAgent(&quot;hand&quot;)" in rail
    assert "/agent/hand" in rail  # Cancel
    assert AF._configure_actions(a) in AF._tab_configure(m, realm, a)


def test_the_page_says_saved_rather_than_navigating_away(realm):
    """Editing happens in passes; leaving the page after each one loses your place."""
    m = reader.read(str(realm))
    a = next(x for x in m.agents if x.id == "hand")
    assert 'id="c-saved"' in AF._tab_configure(m, realm, a)
    js = (Path(__file__).resolve().parents[1] / "armada" / "webui" / "static" / "js" / "agent.js"
          ).read_text(encoding="utf-8")
    body = js.split("async function mcSaveAgent")[1].split("function mcSavedTick")[0]
    assert "location.href" not in body, "still navigates away on save"
    assert "mcSavedTick(r)" in body


def test_the_save_response_carries_the_rendered_documents(realm):
    from armada import serve

    class _H(serve.Handler):
        def __init__(self, r):
            self.realm = str(r)

    res = _H(realm)._save_agent({"agent": "hand", "display": "Marcus",
                                 "mandate": "# Mission\n\nHold it, so Mihai doesn't have to.\n"})
    assert res["ok"] and res["display"] == "Marcus"
    html = res["rendered"]["c-mandate"]
    assert "<h3>Mission</h3>" in html
    assert "doesn&#x27;t" in html and "&amp;#x27;" not in html
    # and what was written is the text, not the entities
    assert "doesn't" in (realm / "agents" / "hand" / "mandate.md").read_text(encoding="utf-8")


def test_the_documents_return_to_reading_mode_from_server_html(realm):
    """Still one markdown renderer: the save response carries HTML from the same _md()."""
    js = (Path(__file__).resolve().parents[1] / "armada" / "webui" / "static" / "js" / "agent.js"
          ).read_text(encoding="utf-8")
    tick = js.split("function mcSavedTick")[1].split("\nasync function")[0]
    assert "r.rendered" in tick
    assert "mcMdEdit(id,false)" in tick
    assert "location.reload" not in tick, "a reload is the thing staying on the page avoids"


# --------------------------------------------------------------------------- Overview is gone

def test_an_unknown_subtab_lands_on_threads_not_on_a_digest(realm):
    """Overview was a read-only summary of Mandate, Soul, Jobs, Memory and Skills; each of those
    now has its own tab that shows more and lets you edit it."""
    assert not hasattr(AF, "_tab_overview")
    src = inspect.getsource(AF._agent_body)
    assert "_tab_overview" not in src
    assert "_tab_threads" in src.rsplit("return", 1)[-1] or "_tab_threads" in src


def test_the_sub_tab_strip_no_longer_offers_it(realm):
    from armada.webui import threadsview as TV
    strip = TV._sub("Threads", "hand", {})
    assert "Overview" not in strip
    assert "/agent/hand/threads" in strip


def test_an_old_overview_link_still_opens_the_agent(realm):
    """Bookmarks shouldn't land on a page whose crumb names a section that isn't there."""
    from armada.webui import pages as P
    m = reader.read(str(realm))
    html = P.render_agent(m, realm, "hand", subtab="overview")
    assert "› <b>Threads</b>" in html


# --------------------------------------------------------------------------- Covenant stamp

def test_the_covenant_says_when_it_was_last_changed(realm):
    """Governance you can edit needs a date, or you cannot tell a considered text from a stale one."""
    stamp = MV._covenant_updated(realm)
    from armada import datefmt
    assert stamp == datefmt.day(datetime.date.today())            # `24 Sep` (DESIGN_SYSTEM §9a)
    assert f"updated {stamp}" in MV._covenant_block(reader.read(str(realm)), realm)


def test_the_stamp_also_rides_along_in_the_reader(realm):
    stamp = MV._covenant_updated(realm)
    modal = MV._covenant_modal(realm)
    assert f"updated {stamp}" in modal
    # and survives the close-and-reopen path: covenant.js snapshots mc-cov-sub's own
    # server-rendered text on load and restores it on close, rather than baking in a second copy.
    assert modal.count(f"updated {stamp}") == 1
    js = (_STATIC_JS / "covenant.js").read_text(encoding="utf-8")
    assert "MC_COV_SUB" in js and 'getElementById("mc-cov-sub")' in js


def test_a_covenant_that_was_never_written_has_no_date(tmp_path):
    r = tmp_path / "r"
    r.mkdir()
    assert MV._covenant_updated(r) == ""
    assert "updated " not in MV._covenant_modal(r)
