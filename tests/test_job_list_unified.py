"""One job list, two pages.

The realm Jobs page was a sortable table with a Created column, a last-run dot and a click that
threw you onto the agent's page. An agent's Jobs tab was expandable rows with cost, next run, a
week strip and an on/off switch. Same jobs, two readings, and only one of them let you do anything.
They are now the same renderer; the realm page adds Kind and Owner, which are the two facts an
agent's own page answers by being that agent's page.
"""
import datetime
import json
import re
from pathlib import Path

import pytest

from armada import reader
from armada.webui import agentframe as AF
from armada.webui import realmpages as R
from armada.webui import pages as P

STATIC = Path(R.__file__).parent / "static" / "js"


@pytest.fixture
def realm(tmp_path):
    root = tmp_path / "Cabinet-realm"
    (root / "realm.json").parent.mkdir(parents=True, exist_ok=True)
    (root / "realm.json").write_text(json.dumps({"name": "Cabinet"}), encoding="utf-8")
    for aid, disp, jobs in (("finance", "Warren", ("alpha", "beta")), ("estate", "Palladio", ("gamma",))):
        ad = root / "agents" / aid
        (ad / "jobs").mkdir(parents=True)
        (ad / "agent.json").write_text(json.dumps({"id": aid, "display": disp}), encoding="utf-8")
        for jid in jobs:
            (ad / "jobs" / f"{jid}.json").write_text(json.dumps({
                "id": jid, "name": jid.title(), "cron": "0 9 * * *", "prompt": "do the thing",
                "summary": f"{jid} summary"}), encoding="utf-8")
    return root


def _realm_page(realm):
    return R._realm_jobs(reader.read(str(realm)), realm, datetime.date.today())


def _agent_page(realm):
    m = reader.read(str(realm))
    a = next(x for x in m.agents if x.id == "finance")
    return AF._tab_jobs(m, realm, a, datetime.date.today())


def _row(html, jid):
    i = html.index(f'data-jid="{jid}"')
    return html[i:].split("</details>", 1)[0]


# --------------------------------------------------------------------------- same renderer

def test_the_agent_tab_and_the_realm_page_share_one_renderer():
    assert AF._job_list is R._job_list
    assert AF._job_cost_pill is R._job_cost_pill
    assert AF._job_token_estimate is R._job_token_estimate


def test_the_realm_page_is_no_longer_a_table_of_jobs(realm):
    html = _realm_page(realm)
    assert 'id="mc-jobstable" class="mc-joblist' in html
    assert "mc-sortable" not in html.split("mc-jobs-cal")[0], "the user pane is still a sorted table"
    assert html.count('<details class="mc-job') == 3, "not one expandable row per job"


def test_every_job_in_the_realm_is_listed(realm):
    html = _realm_page(realm)
    for jid in ("alpha", "beta", "gamma"):
        assert f'data-jid="{jid}"' in html


# --------------------------------------------------------------------------- the two extra columns

def test_kind_and_owner_show_only_on_the_realm_page(realm):
    rp, ap = _realm_page(realm), _agent_page(realm)
    assert "mcSortJobs(this,'kind','mc-jobstable')" in rp
    assert "mcSortJobs(this,'owner','mc-jobstable')" in rp
    assert "'kind'" not in ap and "'owner'" not in ap, "the agent page repeats what it already says"


def test_they_sit_between_the_name_and_the_cadence(realm):
    order = re.findall(r">(Job|Kind|Owner|Cadence|Cost|Next run) ", _realm_page(realm))
    assert order[:5] == ["Job", "Kind", "Owner", "Cadence", "Cost"], order


def test_the_owner_name_is_in_the_row(realm):
    assert ">Warren<" in _row(_realm_page(realm), "alpha")
    assert ">Palladio<" in _row(_realm_page(realm), "gamma")


def test_the_two_grids_differ_only_by_those_columns():
    assert R._JOB_GRID == f"grid-template-columns:1fr {R._JOB_TAIL}"
    assert R._JOB_GRID_OWNED.endswith(R._JOB_TAIL)
    assert R._JOB_GRID_OWNED.count("px") == R._JOB_GRID.count("px") + 2


# --------------------------------------------------------------------------- behaviour

def test_expanding_stays_on_the_page(realm):
    """It used to be a whole-row link that threw you onto the agent."""
    html = _realm_page(realm)
    assert "location.href='/agent/" not in html, "rows still navigate away instead of expanding"
    assert "<summary" in _row(html, "alpha")


def test_edit_goes_to_the_jobs_own_page_from_both(realm):
    for html in (_realm_page(realm), _agent_page(realm)):
        assert 'href="/job/finance/alpha"' in html


def test_the_expanded_row_carries_the_same_three_actions(realm):
    for html in (_realm_page(realm), _agent_page(realm)):
        row = _row(html, "alpha")
        for token in ("mcRun(", "Edit job", "mcDeleteJob("):
            assert token in row, token
        assert "Run history" in row or "<th>When</th>" in row


def test_a_job_can_be_switched_off_from_the_realm_page(realm):
    assert "mcJobEnable(this,&quot;finance&quot;,&quot;alpha&quot;)" in _realm_page(realm)


# --------------------------------------------------------------------------- what the columns sort on

def test_cost_and_next_run_sort_as_numbers_not_as_labels(realm):
    """"≈14k / run" and "Mon 9/21, 20:00" do not sort as themselves."""
    row = _row(_realm_page(realm), "alpha")
    assert re.search(r'data-cost="\d{12}"', row), "cost has no sortable key"
    assert re.search(r'data-next="[\dTz:+-]+"', row), "next run has no sortable key"


def test_the_next_run_column_no_longer_sorts_by_last_status(realm):
    assert "mcSortJobs(this,'status'" not in _realm_page(realm)
    assert "mcSortJobs(this,'next'" in _realm_page(realm)


def test_rows_carry_both_sort_keys_and_filter_buckets(realm):
    row = _row(_realm_page(realm), "alpha")
    for attr in ("data-name", "data-cadence", "data-status",          # sort
                 "data-jstatus", "data-jcad", "data-owner"):          # filter
        assert attr in row, attr


def test_sorting_is_scoped_to_one_list():
    """Both lists exist in the same app; a sort on one must not reorder the other."""
    js = (STATIC / "jobs_sort.js").read_text(encoding="utf-8")
    assert "function mcSortJobs(el,key,boxId)" in js
    assert "boxId||'mc-joblist'" in js


def test_the_filter_bar_can_read_details_rows():
    js = (STATIC / "jobs_filter.js").read_text(encoding="utf-8")
    assert "details.mc-job" in js, "the shared filter still only knows about table rows"
    assert "tbody tr" in js, "system jobs are still a table and must keep working"
    assert "r.dataset.jstatus||r.dataset.status" in js


# --------------------------------------------------------------------------- the Created column

def test_created_is_gone_from_the_list(realm):
    assert ">Created " not in _realm_page(realm)


def test_created_moved_into_the_job_page_header(realm):
    html = P.render_job(reader.read(str(realm)), realm, "finance", "alpha")
    head = html.split("mc-appscroll", 1)[0]
    assert "created " in head, "the date has nowhere left to live"
    assert re.search(r"created \d{4}-\d{2}-\d{2}", head)
