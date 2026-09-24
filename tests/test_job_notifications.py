"""Job failures: finding ARMADA's own package, a workable timeout, and a readable notification.

All three came out of one evening's Telegram messages. "No module named armada" from a command
job that invokes ARMADA's CLI, "claude timed out after 300s" on a job doing real work, and
failures that said who but not what or why.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from armada import runner


# ---- command jobs can find ARMADA -----------------------------------------------------------

def test_a_command_job_can_import_armada_from_any_directory(tmp_path):
    """Python only puts the CURRENT directory on sys.path, and a command job runs in the realm —
    so `python -m armada ...` died unless the package happened to be installed into whatever
    interpreter the job named. It resolved to 'No module named armada', which reads like a broken
    virtualenv rather than a path problem."""
    agent_dir = tmp_path / "agents" / "a"
    (agent_dir / "jobs").mkdir(parents=True)
    job = {"kind": "command",
           "run": [sys.executable, "-c", "import armada; print('found', armada.__version__)"]}
    rep = runner._run_command(tmp_path, "a", "probe", job, agent_dir)
    assert rep["status"] == "ok", rep["summary"]
    assert "found" in rep["summary"]


def test_the_package_root_is_prepended_not_replaced(tmp_path):
    """A job that sets its own PYTHONPATH must keep it."""
    agent_dir = tmp_path / "agents" / "a"
    (agent_dir / "jobs").mkdir(parents=True)
    job = {"kind": "command", "env": {"MYVAR": "kept"},
           "run": [sys.executable, "-c",
                   "import os;print(os.environ['MYVAR'], len(os.environ['PYTHONPATH'].split(os.pathsep)))"]}
    rep = runner._run_command(tmp_path, "a", "probe", job, agent_dir)
    assert rep["status"] == "ok" and "kept" in rep["summary"]


# ---- the timeout ------------------------------------------------------------------------------

def test_the_engine_default_is_no_longer_five_minutes():
    """A scheduled brief that searches the web, reads files and writes a report is routinely past
    five minutes. Timing out there loses work the agent had already done."""
    from armada.engine.claude import ClaudeEngine
    assert ClaudeEngine.DEFAULT_TIMEOUT >= 900
    import inspect
    sig = inspect.signature(ClaudeEngine.run)
    assert sig.parameters["timeout"].default == ClaudeEngine.DEFAULT_TIMEOUT, \
        "the signature default must track the constant, or raising one silently misses the other"


def test_a_job_can_set_its_own_timeout(tmp_path):
    (tmp_path / "realm.json").write_text("{}", encoding="utf-8")
    assert runner._resolve_timeout(tmp_path, {"timeout": 60}) == 60


def test_a_realm_can_set_a_default_timeout(tmp_path):
    (tmp_path / "realm.json").write_text(json.dumps({"default_job_timeout": 777}), encoding="utf-8")
    assert runner._resolve_timeout(tmp_path, {}) == 777
    assert runner._resolve_timeout(tmp_path, {"timeout": 60}) == 60, "the job wins"


def test_a_missing_or_junk_timeout_leaves_the_engine_default(tmp_path):
    (tmp_path / "realm.json").write_text(json.dumps({"default_job_timeout": "soon"}), encoding="utf-8")
    assert runner._resolve_timeout(tmp_path, {}) is None
    assert runner._resolve_timeout(tmp_path, {"timeout": 0}) is None


# ---- the notification template -----------------------------------------------------------------

def test_a_failure_says_which_job_and_why():
    """It used to arrive as 'Marcus: job failed' and an exception class — not enough to act on,
    and on Telegram there's no page to click through to."""
    title, body = runner._job_note("failed", "Marcus", "Daily brief",
                                   why="claude timed out after 300s", took=301, thread="main")
    assert title == "Job failed · Marcus"
    assert "Job: Daily brief" in body
    assert "Why: claude timed out after 300s" in body
    assert "Took: 5m 01s" in body


def test_every_state_uses_the_same_shape():
    bodies = {s: runner._job_note(s, "Ray", "Thesis review", why="done", took=12, thread="main")[1]
              for s in ("started", "finished", "failed")}
    for s, b in bodies.items():
        assert b.splitlines()[0] == "Job: Thesis review", s
        assert "Agent: Ray" in b, s
    assert "Why: done" in bodies["failed"] and "Result: done" in bodies["finished"]


def test_a_failure_with_no_reason_says_so_rather_than_nothing():
    _t, body = runner._job_note("failed", "Steve", "Price watch")
    assert "Why: no reason reported" in body


def test_empty_fields_are_dropped_not_printed_blank():
    _t, body = runner._job_note("started", "Steve", "Price watch")
    assert "Took:" not in body and "Thread:" not in body


@pytest.mark.parametrize("secs,shown", [(0, "0s"), (45, "45s"), (60, "1m 00s"), (301, "5m 01s")])
def test_durations_read_as_durations(secs, shown):
    assert runner._took(secs) == shown


def test_a_failed_command_reports_stderr_not_its_last_progress_line(tmp_path):
    """Taking stdout's last line first meant a crashed script reported how far it got as its
    summary, with the actual error nowhere in sight."""
    agent_dir = tmp_path / "agents" / "a"
    (agent_dir / "jobs").mkdir(parents=True)
    job = {"kind": "command",
           "run": [sys.executable, "-c",
                   "import sys;print('step 3 of 4');print('the real error', file=sys.stderr);sys.exit(2)"]}
    rep = runner._run_command(tmp_path, "a", "probe", job, agent_dir)
    assert rep["status"] == "error"
    assert "the real error" in rep["summary"]
    assert "exit code 2" in rep["summary"]


def test_a_successful_command_still_reports_its_output(tmp_path):
    agent_dir = tmp_path / "agents" / "a"
    (agent_dir / "jobs").mkdir(parents=True)
    job = {"kind": "command", "run": [sys.executable, "-c", "print('all good')"]}
    rep = runner._run_command(tmp_path, "a", "probe", job, agent_dir)
    assert rep["status"] == "ok" and rep["summary"] == "all good"


# ---- approvals ---------------------------------------------------------------------------------

def test_an_approval_says_what_is_being_asked_for():
    """It used to read 'Needs your approval' / 'hand: "x"' — the agent's folder name and the
    proposal's name, and nothing else. You cannot decide from that, and on Telegram there is no
    page to open instead."""
    title, body = runner._approval_note("Warren", "finance", {
        "id": "premium-check", "name": "Options premium check", "kind": "agent",
        "cron": "0 7 * * 1-5", "prompt": "Review open option positions and flag decayed premium."})
    assert title == "Approval needed · Warren"
    assert "Job: Options premium check" in body
    assert "Proposed by: Warren (finance)" in body
    assert "every weekday at 07:00" in body
    assert "flag decayed premium" in body
    assert "nothing runs until you say so" in body


def test_an_approval_distinguishes_a_script_from_an_agent_run():
    """One spends quota and can use tools; the other is a script. That changes the decision."""
    _t, agent = runner._approval_note("Ray", "strategy", {"name": "n", "kind": "agent", "prompt": "p"})
    _t, cmd = runner._approval_note("Ray", "strategy", {"name": "n", "run": ["python", "x.py"]})
    assert "agent job" in agent and "command job" in cmd
    assert "no agent, no tokens" in cmd
    assert "python x.py" in cmd, "a command job's 'Does' is the command itself"


def test_a_vague_proposal_still_produces_a_usable_message():
    """An agent proposing a job called 'x' with no prompt is exactly when you most want to see
    that there's nothing there."""
    _t, body = runner._approval_note("Marcus", "hand", {"id": "x", "name": "x"})
    assert "Job: x" in body
    assert "Does: (nothing specified)" in body
    assert "Runs: on demand (no schedule)" in body


def test_a_long_prompt_is_trimmed_not_dumped():
    _t, body = runner._approval_note("Ray", "strategy",
                                     {"name": "n", "prompt": "word " * 500})
    does = [ln for ln in body.splitlines() if ln.startswith("Does:")][0]
    assert len(does) < 320


@pytest.mark.parametrize("job,expect", [
    ({"cron": "0 7 * * 1-5"}, "every weekday at 07:00"),
    ({"cron": "5 5 * * *"}, "every day at 05:05"),
    ({"cron": "0 9 * * 1"}, "Mondays at 09:00"),
    ({"cron": "30 2 1 * *"}, "day 1 of each month at 02:30"),
    ({"cadence": "manual"}, "manual"),
    ({}, "on demand (no schedule)"),
    ({"cron": "nonsense"}, "cron: nonsense"),
])
def test_schedules_are_readable(job, expect):
    assert runner._cadence_text(job) == expect


def test_every_notification_goes_through_one_composer():
    """Job events and approvals used to be assembled separately, which is how they drifted."""
    src = Path(runner.__file__).read_text(encoding="utf-8")
    for fn in ("_job_note", "_approval_note"):
        block = src.split(f"def {fn}(")[1].split("\ndef ")[0]
        assert "_note(" in block, f"{fn} should compose through _note()"


def test_the_approval_reads_the_proposal_not_just_its_name():
    """status_for_agent() summarises to {id, name}; describing the proposal needs the file."""
    src = Path(runner.__file__).read_text(encoding="utf-8")
    block = src.split("def _sync_proposals(")[1].split("\ndef ")[0]
    assert "_jobs.PENDING" in block and "_approval_note" in block


def test_system_job_failures_read_like_agent_job_failures():
    src = Path(runner.__file__).with_name("sysjobs.py").read_text(encoding="utf-8")
    block = src.split('notify.emit(realm_root, "system_job_failed"')[0][-800:]
    for field in ("Job:", "Agent:", "Why:"):
        assert field in block, f"the system-job notification is missing {field}"
    assert '"Job failed · ARMADA"' in src
