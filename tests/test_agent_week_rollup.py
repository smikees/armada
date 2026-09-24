"""One agent, one row of seven squares — the worst thing each day.

The agent cards and the Register widget each drew their own week from run-reports alone. That week
knew nothing about schedules, so it could not tell "nothing was due" from "everything was missed",
and it disagreed with the Jobs page about the same agent. Both now roll up the Jobs page's own
per-job week across every job the agent owns, worst status wins.
"""
import datetime
import json
import re

import pytest

from armada import reader
from armada.webui import agentbits as AB
from armada.webui import realmpages as R
from armada.webui import widgets as W


@pytest.fixture
def realm(tmp_path):
    root = tmp_path / "Cabinet-realm"
    (root / "agents" / "finance" / "jobs").mkdir(parents=True)
    (root / "realm.json").write_text(json.dumps({"name": "Cabinet"}), encoding="utf-8")
    (root / "agents" / "finance" / "agent.json").write_text(
        json.dumps({"id": "finance", "display": "Warren"}), encoding="utf-8")
    return root


def _job(realm, jid, cron="0 9 * * *", enabled=True, created="2020-01-01T00:00:00+00:00"):
    """`created` defaults to long ago: a job written today cannot have missed yesterday, which is
    correct but makes it useless for testing the rollup."""
    (realm / "agents" / "finance" / "jobs" / f"{jid}.json").write_text(json.dumps(
        {"id": jid, "name": jid.title(), "cron": cron, "prompt": "p", "enabled": enabled,
         "created": created}), encoding="utf-8")


def _agent(realm):
    return next(a for a in reader.read(str(realm)).agents if a.id == "finance")


def _week(realm, now=None):
    now = now or datetime.datetime.now().astimezone()
    return [lbl for _d, _dt, lbl, _w in AB._agent_health7(realm, _agent(realm), now)]


# --------------------------------------------------------------------------- the precedence

def test_the_order_is_the_one_that_was_asked_for():
    assert AB._HEALTH_WORST[:4] == ["Missed", "Failed", "Warning", "Running"]
    assert AB._HEALTH_WORST[-2:] == ["Scheduled", "Not scheduled"]


def test_success_outranks_scheduled_but_loses_to_everything_worse():
    """A day that already produced a good run says more than one merely pencilled in; a day with a
    problem says more than either."""
    r = AB._HEALTH_RANK
    assert r["Running"] < r["Success"] < r["Scheduled"] < r["Not scheduled"]
    for bad in ("Missed", "Failed", "Warning"):
        assert r[bad] < r["Success"]


@pytest.mark.parametrize("labels,winner", [
    (["Missed", "Failed"], "Missed"),
    (["Failed", "Warning"], "Failed"),
    (["Warning", "Running"], "Warning"),
    (["Running", "Success"], "Running"),
    (["Success", "Scheduled"], "Success"),
    (["Scheduled", "Not scheduled"], "Scheduled"),
])
def test_the_worse_of_a_pair_wins(labels, winner):
    assert min(labels, key=lambda x: AB._HEALTH_RANK[x]) == winner


# --------------------------------------------------------------------------- the rollup

def test_one_missed_job_colours_the_whole_day(realm):
    """The card answers "is anything wrong over there", which is the worst case, not the average."""
    _job(realm, "good", cron="0 9 * * *")
    _job(realm, "bad", cron="0 9 * * *")
    now = datetime.datetime.now().astimezone().replace(hour=23, minute=0)
    ymd = (now - datetime.timedelta(days=1)).date().isoformat()
    runs = realm / "agents" / "finance" / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    (runs / "finance.jsonl").write_text(
        json.dumps({"ts": ymd + "T09:00:00+02:00", "task": "good", "status": "ok"}) + "\n",
        encoding="utf-8")
    assert _week(realm, now)[2] == "Missed", "the job that did run hid the one that didn't"


def test_an_agent_with_no_jobs_is_not_scheduled_all_week(realm):
    assert set(_week(realm)) == {"Not scheduled"}


def test_a_job_that_is_off_cannot_be_missed(realm):
    """It is not due, so there is nothing for it to have missed."""
    _job(realm, "paused", cron="0 9 * * *", enabled=False)
    assert "Missed" not in _week(realm)


def test_the_week_is_the_seven_days_up_to_today(realm):
    """On a card and in the Register this is a log: every square has already happened."""
    _job(realm, "alpha")
    wk = AB._agent_health7(realm, _agent(realm), datetime.datetime.now().astimezone())
    assert len(wk) == 7
    assert wk[-1][0] == datetime.date.today().strftime("%A"), "today is not the last square"
    first = datetime.date.today() - datetime.timedelta(days=6)
    assert wk[0][0] == first.strftime("%A")


def test_no_square_on_a_card_is_in_the_future(realm):
    """The centred week belongs to the Jobs list, where a strip is one job whose next run you can
    act on. Here it would be a forecast in a column headed "status"."""
    _job(realm, "alpha", cron="0 9 * * *")
    wk = AB._agent_health7(realm, _agent(realm),
                           datetime.datetime.now().astimezone().replace(hour=23))
    assert "Scheduled" not in [l for _d, _dt, l, _w in wk[:-1]], (
        "a past day was labelled with a future status")


def test_the_dates_and_the_labels_line_up(realm):
    """The rollup zips per-job weeks onto its own list of days. Ask the jobs for a centred week and
    paste it onto a trailing one and last Wednesday wears next Wednesday's status."""
    _job(realm, "alpha", cron="0 9 * * *")
    now = datetime.datetime.now().astimezone()
    rolled = AB._agent_health7(realm, _agent(realm), now)
    direct = AB._job_health7([], "0 9 * * *", now, since="2020-01-01T00:00:00+00:00",
                             back=6, fwd=0)
    assert [d[:2] for d in rolled] == [d[:2] for d in direct], "day labels drifted"
    assert [d[2] for d in rolled] == [d[2] for d in direct], "statuses drifted"


def test_the_rollup_uses_the_jobs_pages_own_week(realm):
    """Two implementations is how a card and the Jobs page come to disagree about one agent."""
    import inspect
    assert "_job_health7" in inspect.getsource(AB._agent_health7)
    assert AB._job_health7 is R._job_health7


# --------------------------------------------------------------------------- the two renderers

def test_the_card_draws_the_shared_squares(realm):
    _job(realm, "alpha")
    html = R._realm_ministers(reader.read(str(realm)), realm, datetime.date.today())
    assert html.count("width:11px;height:11px") == 7, "not seven shared squares"
    assert "width:6px;height:12px" not in html, "the card still draws its own bars"


def test_the_card_has_no_day_initials(realm):
    """Every square is a day that has already happened, so the initials only repeated the tooltip
    — and on a 330px card they cost a line the profile wanted."""
    _job(realm, "alpha")
    html = R._realm_ministers(reader.read(str(realm)), realm, datetime.date.today())
    assert "border-bottom:1.5px solid var(--color-accent-2)" not in html, "today is still marked"
    assert 'title="Job outcomes, last 7 days"' in html, "the strip is unlabelled"


def test_the_register_draws_the_same_squares(realm):
    _job(realm, "alpha")
    html = W._register(reader.read(str(realm)), realm, datetime.date.today())
    row = html.split("<tbody>")[1].split("</tr>")[0]
    assert row.count("width:11px;height:11px") == 7
    assert "width:7px;height:14px" not in html, "the register still draws its own bars"


def test_all_three_views_agree_for_one_agent(realm):
    _job(realm, "alpha")
    m = reader.read(str(realm))
    card = R._realm_ministers(m, realm, datetime.date.today())
    reg = W._register(m, realm, datetime.date.today())
    pat = re.compile(r'<i title="([^"]*[Jj]ob [a-z]+[^"]*)"')
    assert pat.findall(card) and pat.findall(card) == pat.findall(reg), (
        "the card and the register disagree")


# --------------------------------------------------------------------------- the tooltips

def test_a_square_says_what_happened_to_a_job(realm):
    """"Scheduled" beside a date read as a property of the date."""
    _job(realm, "alpha")
    html = R._realm_ministers(reader.read(str(realm)), realm, datetime.date.today())
    tips = re.findall(r'<i title="([^"]+)"', html)
    assert tips, "no tooltips"
    for t in tips:
        assert re.search(r"· (Job (succeeded|running|scheduled|warning|failed|missed)"
                         r"|No job scheduled)", t), t


def test_every_status_has_a_phrase():
    assert set(AB._HEALTH_PHRASE) == set(AB._HEALTH_WORST), "a status has no sentence form"


def test_the_jobs_list_tooltips_use_the_same_phrases(realm):
    """One wording, or the same square means two things on two pages."""
    _job(realm, "alpha")
    html = R._realm_jobs(reader.read(str(realm)), realm, datetime.date.today())
    assert re.search(r'<i title="[^"]*· Job ', html)


# --------------------------------------------------------------------------- the register columns

def _autonomy_title():
    from armada.webui.agentbits import _AUTONOMY_META
    return _AUTONOMY_META["manual"][3]


def test_autonomy_left_its_column_for_the_name(realm):
    html = W._register(reader.read(str(realm)), realm, datetime.date.today())
    assert ">Autonomy</th>" not in html, "the column is still there"
    row = html.split("<tbody>")[1].split("</tr>")[0]
    name_cell = row.split("</td>")[0]
    assert _autonomy_title()[:24] in name_cell, "the badge is not in the name cell"


def test_the_autonomy_icon_is_still_shown_exactly_once(realm):
    html = W._register(reader.read(str(realm)), realm, datetime.date.today())
    row = html.split("<tbody>")[1].split("</tr>")[0]
    assert row.count(_autonomy_title()[:24]) == 1, "the badge is duplicated or gone"


def test_the_row_lost_a_cell(realm):
    """Removing a column means removing its <td> too, or every row after it shifts left."""
    html = W._register(reader.read(str(realm)), realm, datetime.date.today())
    head = html.split("<tbody>")[0]
    row = html.split("<tbody>")[1].split("</tr>")[0]
    ncols = len(re.findall(r"<th[ >]", head))     # not "<th", which also matches <thead>
    assert ncols == row.count("<td"), f"header has {ncols} columns, the row has {row.count('<td')}"


def test_the_seven_day_column_says_what_it_is(realm):
    """Day initials would name the weekday of each cell; the column needs to say what the cells
    are. They are all past days, so there is no split to mark."""
    html = W._register(reader.read(str(realm)), realm, datetime.date.today())
    head = html.split("<tbody>")[0]
    assert ">7D job status<" in head
    assert ">7d<" not in head, "the bare 7d label is still there"
    assert "border-bottom:1.5px solid var(--color-accent-2)" not in head, "today is still marked"
