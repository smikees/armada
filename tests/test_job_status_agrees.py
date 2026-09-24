"""One definition of a job's status, across the row, the filter, the expanded view and the calendar.

Four jobs, none of which had ever run, all showed "no last status" and all matched the Missed
filter — while the strip beside them marked two as missed and two as never due. Expanding a job
marked missed showed "no runs yet" and nothing else. And the calendar, which had never learned
about a job's creation date, counted fire times from before the job was written as misses: the
same job read "missed four times" on the calendar and "missed once" on the list.
"""
import datetime
import json
import re

import pytest

from armada import reader
from armada.webui import realmpages as R, agentbits as AB, agentcommon as AC
from armada import webui


@pytest.fixture
def realm(tmp_path):
    """One agent, two jobs, written 'yesterday': one due since and missed, one never due."""
    root = tmp_path / "realm"
    ad = root / "agents" / "warren"
    (ad / "jobs").mkdir(parents=True)
    (root / "realm.json").write_text(json.dumps({"name": "Cabinet"}), encoding="utf-8")
    (ad / "agent.json").write_text(json.dumps({"id": "warren", "display": "Warren"}),
                                   encoding="utf-8")
    born = (datetime.datetime.now().astimezone() - datetime.timedelta(days=1)).replace(hour=0, minute=1)
    for jid, cron in (("due", "0 1 * * *"), ("later", "0 1 1 1 *")):
        (ad / "jobs" / f"{jid}.json").write_text(json.dumps(
            {"id": jid, "name": jid.title(), "cron": cron, "prompt": "p",
             "created": born.isoformat()}), encoding="utf-8")
    return root


def _rows(realm):
    now = datetime.datetime.now().astimezone()
    r = reader.read(str(realm))
    a = next(x for x in r.agents if x.id == "warren")
    runs_all, running = AB._runs(realm, a.id), AC._running_jobs(realm, a.id)
    return {j.id: R._job_row(realm, a, j, now, runs_all, running, True) for j in a.jobs}


def _attr(html, name):
    m = re.search(rf'{name}="([^"]*)"', html)
    return m.group(1) if m else None


def test_a_job_that_was_never_due_does_not_match_missed(realm):
    """The bug in one line: 'no runs' and 'missed' are not the same fact."""
    rows = _rows(realm)
    assert _attr(rows["due"], "data-jstatus") == "none"
    assert _attr(rows["later"], "data-jstatus") == "", \
        "a job that has never been due must not match the Missed filter"


def test_the_expanded_view_is_a_run_log_not_the_strip_again(realm):
    """The strip in the collapsed row already says how the schedule has been going. The expanded
    view answers a different question — what happened on the runs themselves — so it is a plain
    log of the last few, and says plainly when there haven't been any."""
    row = _rows(realm)["due"]
    assert "Last 7 runs" in row
    assert "no runs yet" in row
    body = row[row.index("Last 7 runs"):]
    assert "Missed" not in body, "the expanded log should not repeat the week strip"


def test_the_calendar_and_the_strip_agree_on_missed(realm):
    """The calendar had no notion of when a job was written, so it counted fire times from before
    the job existed. Same job, same window, same answer."""
    r = reader.read(str(realm))
    today = datetime.date.today()
    evs = webui._jobcal_events(r, str(realm), today - datetime.timedelta(days=3), today)
    cal_missed = {e["ts"][:10] for e in evs if e["status"] == "missed" and e["job"] == "due"}

    now = datetime.datetime.now().astimezone()
    a = next(x for x in r.agents if x.id == "warren")
    j = next(x for x in a.jobs if x.id == "due")
    jc = AC._job_prompt(realm, a.id, j.id)
    wk = AB._job_health7([], j.cadence, now, False,
                         since=AB._job_created_ts(realm, a.id, j.id, jc))
    today_i = AB._WEEK_BACK
    strip_missed = set()
    for i, (_d, _dt, label, _w) in enumerate(wk):
        if label == "Missed":
            strip_missed.add((today + datetime.timedelta(days=i - today_i)).isoformat())
    assert cal_missed == strip_missed, "the calendar and the week strip disagree about missed days"


def test_the_calendar_does_not_invent_misses_before_a_job_existed(realm):
    r = reader.read(str(realm))
    today = datetime.date.today()
    evs = webui._jobcal_events(r, str(realm), today - datetime.timedelta(days=20), today)
    born = today - datetime.timedelta(days=1)
    for e in evs:
        assert e["ts"][:10] >= born.isoformat(), \
            f"{e['job']} reported an occurrence on {e['ts']}, before the job was written"
