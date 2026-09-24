"""Two questions a jobs list has to answer without being opened: what does this do, and when does it run.

The Agent jobs view listed names, and the names are what a job is *called*. With prompts running to
two thousand words, finding out what one does meant opening it. And the system-jobs table answered
"when" with "due now" — the scheduler's internal state, not a time anyone can plan around.
"""
import datetime
import json
from pathlib import Path

import pytest

from armada import reader
from armada.webui import agentframe as AF
from armada.webui import realmpages as RP

WEBUI = Path(RP.__file__).parent


@pytest.fixture
def realm(tmp_path):
    r = tmp_path / "Cabinet-realm"
    (r / "agents" / "finance" / "jobs").mkdir(parents=True)
    (r / "realm.json").write_text(json.dumps({"name": "Cabinet"}), encoding="utf-8")
    (r / "agents" / "finance" / "agent.json").write_text(
        json.dumps({"id": "finance", "display": "Warren"}), encoding="utf-8")
    (r / "agents" / "finance" / "jobs" / "weekly.json").write_text(json.dumps({
        "id": "weekly", "name": "Weekly Analyzer", "cron": "0 9 * * 6",
        "summary": "Sets the regime and produces the ranked shortlist.",
        "prompt": "Long prompt here."}), encoding="utf-8")
    (r / "agents" / "finance" / "jobs" / "bare.json").write_text(json.dumps({
        "id": "bare", "name": "No summary", "prompt": "x"}), encoding="utf-8")
    return r


# --------------------------------------------------------------------------- summary

def test_the_summary_is_read_off_the_job(realm):
    m = reader.read(str(realm))
    jobs = {j.id: j for j in m.agents[0].jobs}
    assert jobs["weekly"].summary == "Sets the regime and produces the ranked shortlist."


def test_a_job_without_one_is_fine(realm):
    m = reader.read(str(realm))
    assert {j.id: j for j in m.agents[0].jobs}["bare"].summary == ""


def test_the_summary_shows_beside_the_name(realm):
    m = reader.read(str(realm))
    a = m.agents[0]
    html = AF._tab_jobs(m, realm, a, datetime.date.today())
    head = html.split("Weekly Analyzer")[1].split("</summary>")[0]
    assert "Sets the regime and produces the ranked shortlist." in head
    assert "No summary" in html, "a job without a summary still lists"


def test_saving_a_job_persists_the_summary(realm):
    from armada import serve

    class _H(serve.Handler):
        def __init__(self, r):
            self.realm = str(r)

    res = _H(realm)._save_job({"agent": "finance", "job": "bare", "summary": "Now it says something."})
    assert res["ok"]
    d = json.loads((realm / "agents" / "finance" / "jobs" / "bare.json").read_text(encoding="utf-8"))
    assert d["summary"] == "Now it says something."
    assert d["prompt"] == "x", "an unrelated field was clobbered"


def test_the_editor_offers_the_field():
    src = (WEBUI / "pages.py").read_text(encoding="utf-8")
    assert 'id="j-summary"' in src
    js = (WEBUI / "static" / "js" / "job.js").read_text(encoding="utf-8")
    assert "summary:" in js, "the editor shows it but never saves it"


# --------------------------------------------------------------------------- next run

def test_next_run_is_a_wall_clock_time():
    now = datetime.datetime(2026, 9, 18, 14, 0).astimezone()
    t = (now + datetime.timedelta(days=3)).replace(hour=20, minute=0)
    assert RP._sysjob_next(t.isoformat(), False, now) == "Mon 21 Sep, 20:00"          # DESIGN_SYSTEM §9a


def test_an_overdue_job_says_when_it_will_actually_run():
    """'due now' described the scheduler's state. The daemon sweeps every minute, so the honest
    answer to 'when does it run' is: imminently."""
    now = datetime.datetime.now().astimezone()
    assert RP._sysjob_next("", True, now) == "any moment"


def test_a_job_with_no_next_time_is_not_invented():
    now = datetime.datetime.now().astimezone()
    assert RP._sysjob_next("", False, now) == "—"
    assert RP._sysjob_next("not-a-date", False, now) == "—"


def test_the_column_is_called_next_run():
    src = (WEBUI / "realmpages.py").read_text(encoding="utf-8")
    assert '"Next run"' in src and '"Next due"' not in src


def test_the_javascript_formats_it_the_same_way():
    """The cell is repainted client-side after an action; two formatters would disagree."""
    js = (WEBUI / "static" / "js" / "sysjobs.js").read_text(encoding="utf-8")
    assert "function nextRun(" in js
    assert "any moment" in js and "due now" not in js
    assert "MON[d.getMonth()]" in js and "d.getDate()" in js      # `Thu 24 Sep, 22:30`, as datefmt.moment


# --------------------------------------------------------------------------- run buttons

def test_the_mock_run_button_is_gone(realm):
    m = reader.read(str(realm))
    html = AF._tab_jobs(m, realm, m.agents[0], datetime.date.today())
    assert "Run (mock)" not in html and "'mock'" not in html
    assert "Run now" in html


def test_the_job_editor_has_no_mock_buttons_either():
    src = (WEBUI / "pages.py").read_text(encoding="utf-8")
    body = src[src.index("def render_job"):]
    assert "Run (mock)" not in body and "Test run" not in body
    assert "Run now" in body
