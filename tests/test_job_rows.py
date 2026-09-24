"""Agent job rows, brought into line with capability rows — and a job you can switch off.

The two lists did the same thing and looked unrelated: one opened with a text caret, the other with
an icon; one had an on/off toggle, the other did not. And a job could only be stopped by deleting it
or editing its cron away, neither of which is "pause this for a bit".
"""
import datetime
import json
from pathlib import Path

import pytest

from armada import reader, scheduler
from armada.webui import agentframe as AF
from armada.webui import layout as LAY

WEBUI = Path(AF.__file__).parent


def _job(d, jid, **kw):
    base = {"id": jid, "name": jid.title(), "prompt": "do the thing", "cron": "0 9 * * *"}
    base.update(kw)
    (d / f"{jid}.json").write_text(json.dumps(base), encoding="utf-8")


@pytest.fixture
def realm(tmp_path):
    r = tmp_path / "Cabinet-realm"
    jd = r / "agents" / "finance" / "jobs"
    jd.mkdir(parents=True)
    (r / "realm.json").write_text(json.dumps({"name": "Cabinet"}), encoding="utf-8")
    (r / "agents" / "finance" / "agent.json").write_text(
        json.dumps({"id": "finance", "display": "Warren"}), encoding="utf-8")
    _job(jd, "alpha", summary="Does alpha things.")
    _job(jd, "beta", enabled=False)
    _job(jd, "gamma")
    return r


class _H:
    def __new__(cls, r):
        from armada import serve
        h = object.__new__(serve.Handler)
        h.realm = str(r)
        return h


# --------------------------------------------------------------------------- enabled

def test_a_job_is_on_unless_it_says_otherwise(realm):
    """Absent must mean on — jobs written by hand or before the toggle existed should still run."""
    jobs = {j.id: j for j in reader.read(str(realm)).agents[0].jobs}
    assert jobs["alpha"].enabled is True
    assert jobs["gamma"].enabled is True
    assert jobs["beta"].enabled is False


def test_the_scheduler_skips_a_job_that_is_off(realm):
    """dry_run so nothing is actually invoked — we only care which jobs it *would* fire."""
    fired = scheduler.tick(realm, dry_run=True, grace_min=10_000)
    ids = {f.get("job") for f in fired}
    assert "beta" not in ids, "a switched-off job fired"
    assert "alpha" in ids and "gamma" in ids, f"the enabled ones stopped firing too: {ids}"


def test_off_is_a_pause_not_a_disable(realm):
    """Run now has to keep working, or the toggle is a delete with extra steps."""
    src = (Path(scheduler.__file__)).read_text(encoding="utf-8")
    assert "enabled" in src and "due_now" in src
    i_en = src.index('job.get("enabled")')
    assert "run_job" not in src[:i_en].rsplit("for agent_id", 1)[-1], "the skip must precede the run"


def test_toggling_writes_the_file(realm):
    h = _H(realm)
    assert h._job_enable({"agent": "finance", "job": "alpha", "enabled": False})["ok"]
    d = json.loads((realm / "agents" / "finance" / "jobs" / "alpha.json").read_text(encoding="utf-8"))
    assert d["enabled"] is False
    assert d["prompt"] == "do the thing", "an unrelated field was clobbered"
    assert h._job_enable({"agent": "finance", "job": "alpha", "enabled": True})["ok"]
    d = json.loads((realm / "agents" / "finance" / "jobs" / "alpha.json").read_text(encoding="utf-8"))
    assert "enabled" not in d, "on is the default; don't litter every file with true"


# --------------------------------------------------------------------------- delete

def test_deleting_removes_the_job_but_keeps_the_history(realm):
    runs = realm / "agents" / "finance" / "runs"
    runs.mkdir()
    (runs / "finance.jsonl").write_text('{"task":"alpha","status":"ok"}\n', encoding="utf-8")
    assert _H(realm)._delete_job({"agent": "finance", "job": "alpha"})["ok"]
    assert not (realm / "agents" / "finance" / "jobs" / "alpha.json").exists()
    assert (runs / "finance.jsonl").exists(), "the record of what actually ran was destroyed"


def test_deleting_a_missing_job_is_an_error_not_a_crash(realm):
    assert _H(realm)._delete_job({"agent": "finance", "job": "nope"})["ok"] is False


def test_the_delete_button_confirms_in_app(realm):
    """House rule: no browser dialogs."""
    js = (WEBUI / "static" / "js" / "run.js").read_text(encoding="utf-8")
    assert "confirm(" not in js and "window.confirm" not in js
    assert "armed" in js, "one-press delete on a job someone wrote is too easy"
    assert "run history is kept" in js


# --------------------------------------------------------------------------- the row

def test_the_row_uses_the_capability_chevron(realm):
    m = reader.read(str(realm))
    html = AF._tab_jobs(m, realm, m.agents[0], datetime.date.today())
    assert "mc-jcaret" in html
    assert "▸" not in html, "still the old text caret"
    css = (WEBUI / "static" / "brand.css").read_text(encoding="utf-8")
    assert ".mc-job[open] .mc-jcaret" in css and "rotate(90deg)" in css


def test_the_summary_is_a_subtitle(realm):
    m = reader.read(str(realm))
    html = AF._tab_jobs(m, realm, m.agents[0], datetime.date.today())
    block = html.split("Does alpha things.")[0]
    assert "display:block" in block.rsplit("<span", 1)[-1], "summary is not on its own line"


def test_the_prompt_does_not_look_editable(realm):
    m = reader.read(str(realm))
    html = AF._tab_jobs(m, realm, m.agents[0], datetime.date.today())
    assert "<textarea readonly" not in html, "a read-only textarea still looks like a field"
    pre = html.split('class="mc-prompt"')[1].split(">")[0]
    assert "resize:vertical" in pre and "overflow:auto" in pre, "lost the drag handle or the scroll"


def test_every_row_has_a_toggle(realm):
    m = reader.read(str(realm))
    html = AF._tab_jobs(m, realm, m.agents[0], datetime.date.today())
    assert html.count("mcJobEnable(") == 3
    assert "mc-job-off" in html, "the disabled one is not marked"


# --------------------------------------------------------------------------- the count

def test_the_overview_counts_active_jobs_only(realm):
    m = reader.read(str(realm))
    kpis = LAY._kpis(m)
    assert "Active jobs" in kpis
    assert "data-active-jobs>2<" in kpis, "counted the switched-off job"


def test_the_count_updates_without_a_reload():
    js = (WEBUI / "static" / "js" / "run.js").read_text(encoding="utf-8")
    assert "data-active-jobs" in js and "mcJobCount" in js


# --------------------------------------------------------------------------- cost column

def test_a_command_job_is_free(realm):
    assert "free" in AF._job_cost_pill("command", 0, 0)
    assert "quota" not in AF._job_cost_pill("command", 0, 0)


def test_an_agent_job_with_no_history_says_it_costs_without_inventing_a_number(realm):
    p = AF._job_cost_pill("agent", 0, 0)
    assert "uses quota" in p
    assert "≈" not in p, "estimated from nothing"


def test_an_agent_job_with_history_shows_the_estimate(realm):
    p = AF._job_cost_pill("agent", 26634, 5)
    assert "≈27k / run" in p
    assert "Median of 5 recorded runs" in p, "the tooltip has to say what the number is"


def test_the_estimate_is_a_median_not_a_mean(realm):
    """One first run that wrote the whole context into cache must not set the expectation."""
    runs = [{"tokens": {"total": t}} for t in (3000, 3200, 3100, 250000)]
    tok, n = AF._job_token_estimate(runs)
    assert n == 4
    assert tok < 10000, f"an outlier dragged the estimate to {tok}"


def test_runs_without_token_data_are_not_counted_as_zero(realm):
    runs = [{"tokens": {"total": 5000}}, {"status": "quiet"}, {"tokens": {}}]
    tok, n = AF._job_token_estimate(runs)
    assert (tok, n) == (5000, 1)


def test_a_job_that_never_ran_estimates_nothing(realm):
    assert AF._job_token_estimate([]) == (0, 0)


def test_the_cost_column_is_in_the_row(realm):
    m = reader.read(str(realm))
    html = AF._tab_jobs(m, realm, m.agents[0], datetime.date.today())
    assert "uses quota" in html
    assert "Cost" in html and "Created" not in html, "Created should have made way for Cost"


# --------------------------------------------------------------------------- 7-day health

def test_the_row_carries_a_seven_day_strip(realm):
    m = reader.read(str(realm))
    html = AF._tab_jobs(m, realm, m.agents[0], datetime.date.today())
    row = html.split('data-jid="alpha"')[1].split("</summary>")[0]
    # Missed draws a glyph rather than a rounded tile, so count the box the two branches share.
    assert row.count("width:11px;height:11px") == 7, "not seven day squares"


def test_the_legend_is_shown(realm):
    m = reader.read(str(realm))
    html = AF._tab_jobs(m, realm, m.agents[0], datetime.date.today())
    for label in ("Warning", "Failed", "Missed", "Not scheduled"):
        assert label in html, f"legend missing {label}"
    assert "-/+3D job outcome and outlook" in html


def test_health_is_computed_by_the_shared_helper(realm):
    """Two implementations is how the same job shows a different week on two pages."""
    from armada.webui import realmpages as R
    assert AF._job_health7 is R._job_health7
    assert AF._health_square is R._health_square


# --------------------------------------------------------------------------- delete icon

# --------------------------------------------------------------------------- the centred week

def _week(cadence="0 9 * * *", jruns=(), now=None):
    from armada.webui import realmpages as R
    now = now or datetime.datetime.now().astimezone()
    return R._job_health7(list(jruns), cadence, now)


def test_the_week_is_centred_on_today():
    from armada.webui import realmpages as R
    now = datetime.datetime.now().astimezone()
    wk = _week(now=now)
    assert len(wk) == 7
    labels = [d for d, _dt, _l, _w in wk]
    assert labels[3] == now.strftime("%A"), "today is not the middle square"
    assert R._WEEK_BACK == 3 and R._WEEK_FWD == 3


def test_a_future_day_can_never_be_missed():
    """The bug you get by widening the window without touching the branch: tomorrow reported as a
    day the job failed to run."""
    wk = _week()
    future = [l for _d, _dt, l, _w in wk[4:]]
    assert "Missed" not in future, f"a day that has not happened was marked missed: {future}"
    assert set(future) <= {"Scheduled", "Not scheduled"}


def test_a_past_day_that_was_due_and_did_not_run_is_missed():
    wk = _week()
    assert "Missed" in [l for _d, _dt, l, _w in wk[:3]]


def test_a_past_day_with_a_run_shows_its_status():
    now = datetime.datetime.now().astimezone()
    y = (now - datetime.timedelta(days=1)).date().isoformat()
    wk = _week(jruns=[{"ts": y + "T09:00:00+02:00", "status": "ok"}], now=now)
    assert wk[2][2] == "Success", wk[2]


def test_an_unscheduled_job_is_not_scheduled_all_week():
    assert {l for _d, _dt, l, _w in _week(cadence="manual")} == {"Not scheduled"}


def test_missed_is_visually_distinct_from_not_scheduled():
    from armada.webui import realmpages as R
    miss, none_ = R._health_square("Missed", "t"), R._health_square("Not scheduled", "t")
    # Missed is the codicon error-compact glyph; Not scheduled is a plain tinted tile.
    assert "<svg" in miss and "<svg" not in none_
    assert "M6 0C2.691" in miss, "not the codicon error-compact path"
    assert "border-radius:2px" in none_ and "border-radius" not in miss
    assert miss != none_


def test_the_header_marks_today():
    from armada.webui import realmpages as R
    h = R._health7_header(datetime.date.today())
    assert h.count("<span") == 7
    assert "today" in h and "border-bottom" in h


# --------------------------------------------------------------------------- row layout

def test_the_chevron_is_before_the_title_and_not_repeated(realm):
    m = reader.read(str(realm))
    html = AF._tab_jobs(m, realm, m.agents[0], datetime.date.today())
    row = html.split('data-jid="alpha"')[1].split("</summary>")[0]
    assert row.count("mc-jcaret") == 1, "chevron is duplicated"
    assert row.index("mc-jcaret") < row.index("Alpha"), "chevron is not before the title"


def test_delete_moved_into_the_expanded_view(realm):
    m = reader.read(str(realm))
    html = AF._tab_jobs(m, realm, m.agents[0], datetime.date.today())
    row = html.split('data-jid="alpha"')[1]
    head, body = row.split("</summary>", 1)
    assert "mcDeleteJob" not in head, "delete is still in the collapsed row"
    assert "mcDeleteJob" in body.split("</details>")[0]
    assert body.index("Edit job") < body.index("mcDeleteJob"), "delete should sit after Edit"


def test_the_column_is_next_run_not_last_run(realm):
    m = reader.read(str(realm))
    html = AF._tab_jobs(m, realm, m.agents[0], datetime.date.today())
    assert "Next run" in html and "Last run" not in html


def test_a_disabled_job_says_off_rather_than_a_time(realm):
    m = reader.read(str(realm))
    html = AF._tab_jobs(m, realm, m.agents[0], datetime.date.today())
    beta = html.split('data-jid="beta"')[1].split("</summary>")[0]
    assert ">off<" in beta, "a job that is off still advertised a next run"


def test_a_manual_job_says_on_demand(realm):
    _job(realm / "agents" / "finance" / "jobs", "manualjob", cron=None, schedule="manual")
    m = reader.read(str(realm))
    html = AF._tab_jobs(m, realm, m.agents[0], datetime.date.today())
    row = html.split('data-jid="manualjob"')[1].split("</summary>")[0]
    assert "on demand" in row


def test_next_run_uses_one_implementation():
    """A second scan would eventually disagree with the agent header about the same cron."""
    from armada.webui import schedfmt as S
    import inspect
    assert "_job_next_dt" in inspect.getsource(S._next_run_dt)


def test_the_legend_is_right_aligned(realm):
    m = reader.read(str(realm))
    html = AF._tab_jobs(m, realm, m.agents[0], datetime.date.today())
    wrap = html.split("-/+3D job outcome and outlook")[0].rsplit("<div", 2)[-2]
    assert "justify-content:flex-end" in wrap, "legend is not pushed right"


# --------------------------------------------------------------------------- a job cannot miss a
# --------------------------------------------------------------------------- day before it existed

def test_a_brand_new_job_has_no_phantom_missed_days():
    """Four jobs written today showed three red marks each while the run history said "no runs
    yet" — two true statements that together read as a fault."""
    from armada.webui import realmpages as R
    now = datetime.datetime.now().astimezone()
    today = now.date().isoformat()
    wk = R._job_health7([], "0 9 * * *", now, since=today)
    assert [l for _d, _dt, l, _w in wk[:3]] == ["Not scheduled"] * 3


def test_days_after_creation_can_still_be_missed():
    """The guard must not swallow real misses — only days before the job existed."""
    from armada.webui import realmpages as R
    now = datetime.datetime.now().astimezone()
    old = (now - datetime.timedelta(days=30)).date().isoformat()
    wk = R._job_health7([], "0 9 * * *", now, since=old)
    assert "Missed" in [l for _d, _dt, l, _w in wk[:3]]


def test_no_creation_date_behaves_as_before():
    from armada.webui import realmpages as R
    now = datetime.datetime.now().astimezone()
    assert "Missed" in [l for _d, _dt, l, _w in R._job_health7([], "0 9 * * *", now)]


def test_a_job_written_this_afternoon_did_not_miss_this_morning():
    """The day-level guard let today through: a job created at 14:00 with a 09:00 cron was still
    marked missed for today, which is the same phantom the guard was added to remove."""
    from armada.webui import realmpages as R
    now = datetime.datetime.now().astimezone().replace(hour=14, minute=0, second=0, microsecond=0)
    made = now.replace(hour=13, minute=30)
    wk = R._job_health7([], "0 9 * * *", now, since=made.isoformat())
    assert wk[3][2] == "Not scheduled", f"today marked {wk[3][2]} for a job made after its fire time"


def test_a_fire_time_still_ahead_of_a_job_made_today_is_scheduled():
    from armada.webui import realmpages as R
    now = datetime.datetime.now().astimezone().replace(hour=14, minute=0, second=0, microsecond=0)
    made = now.replace(hour=13, minute=30)
    wk = R._job_health7([], "0 20 * * *", now, since=made.isoformat())
    assert wk[3][2] == "Scheduled"


def test_a_bare_date_since_is_still_accepted():
    """_job_created_ts falls back to a date when the job file carries one."""
    from armada.webui import realmpages as R
    now = datetime.datetime.now().astimezone()
    wk = R._job_health7([], "0 9 * * *", now, since=now.date().isoformat())
    assert [l for _d, _dt, l, _w in wk[:3]] == ["Not scheduled"] * 3


def test_both_pages_pass_the_creation_timestamp():
    """One renderer, so the guard cannot be present on one page and missing on the other."""
    r = (WEBUI / "realmpages.py").read_text(encoding="utf-8")
    assert "since=_job_created_ts" in r, "the shared row still reports phantom misses"
    assert r.count("since=_job_created_ts") == 1, "a second copy of the row has appeared"
    from armada.webui import realmpages as R
    assert AF._job_list is R._job_list, "the agent tab is no longer using the shared list"


def test_the_creation_timestamp_keeps_the_time_of_day():
    """A date would put the job at midnight, which is exactly the case this fix is about."""
    from armada.webui.agentcommon import _job_created_ts
    from pathlib import Path as _P
    got = _job_created_ts(_P("/nowhere"), "a", "b", {"created": "2026-09-18T14:05:00+02:00"})
    assert got.startswith("2026-09-18T14:05")


# --------------------------------------------------------------------------- icons

def test_missed_uses_the_codicon_glyph():
    from armada.icons import ICON_MISSED
    from armada.webui import realmpages as R
    from armada.webui.widgets import _health_legend_chips
    assert "viewBox=\"0 0 12 12\"" in ICON_MISSED, "not the 12-grid codicon"
    assert "M6 0C2.691" in R._health_square("Missed", "t")
    assert "M6 0C2.691" in _health_legend_chips(), "legend swatch disagrees with the row's mark"


def test_the_job_chevron_matches_the_capability_chevron(realm):
    """CHEVR is the up/down unfold pair and was never the disclosure icon on either page."""
    m = reader.read(str(realm))
    html = AF._tab_jobs(m, realm, m.agents[0], datetime.date.today())
    row = html.split('data-jid="alpha"')[1].split("</summary>")[0]
    assert "m9 18l6-6l-6-6" in row, "not chevron-right"
    assert "m7 15 5 5 5-5" not in row, "still the up/down unfold glyph"


def test_delete_has_a_label(realm):
    m = reader.read(str(realm))
    html = AF._tab_jobs(m, realm, m.agents[0], datetime.date.today())
    assert "Delete job</button>" in html


# --------------------------------------------------------------------------- the job edit page

def _job_page_src():
    return (WEBUI / "pages.py").read_text(encoding="utf-8")


def test_run_history_leads_the_execution_column():
    src = _job_page_src()
    body = src[src.index("def render_job"):src.index("def render_new_agent")]
    ex = body[body.index("execution = ("):]
    assert ex.index("Run history") < ex.index("j-out"), "history is still below the output pane"


def test_every_action_sits_on_one_bar_at_the_foot():
    src = _job_page_src()
    body = src[src.index("def render_job"):src.index("def render_new_agent")]
    bar = body[body.index("actions = ("):body.index("crumb = (")]
    for label in (">Save<", "Run now", "Delete job", "Back to jobs"):
        assert label in bar, f"{label} is not on the action bar"
    # and the bar is rendered after both columns
    assert "{execution}</div></div>{actions}" in body


def test_deleting_from_the_page_returns_to_the_list():
    js = (WEBUI / "static" / "js" / "job.js").read_text(encoding="utf-8")
    assert "mcDeleteJobPage" in js
    assert "confirm(" not in js
    assert "armed" in js and "run history is kept" in js
    assert "/jobs'" in js.split("mcDeleteJobPage")[1], "nowhere to go after the job is gone"
