"""The {workspace} token: what makes a realm survive a change of machine.

191 of the live realm's 193 absolute path references were in job prompts, and every one hung off a
single root. The token turns those 193 literals back into the one variable they always were.
"""
import json

import pytest

from armada import runner, workspace


def _realm(tmp_path, ws=None, jobs=None):
    r = tmp_path / "realm"
    (r / "agents" / "warren" / "jobs").mkdir(parents=True)
    cfg = {"name": "R"}
    if ws is not None:
        cfg["workspace"] = ws
    (r / "realm.json").write_text(json.dumps(cfg), encoding="utf-8")
    (r / "agents" / "warren" / "agent.json").write_text(json.dumps({"id": "warren"}), encoding="utf-8")
    for jid, prompt in (jobs or {}).items():
        (r / "agents" / "warren" / "jobs" / f"{jid}.json").write_text(
            json.dumps({"id": jid, "prompt": prompt}), encoding="utf-8")
    return r


# ---------------------------------------------------------------- reading the setting

def test_root_reads_the_realm_setting(tmp_path):
    assert workspace.root(_realm(tmp_path, ws="D:\\Work")) == "D:\\Work"
    assert workspace.root(_realm(tmp_path / "b")) == ""


def test_unconfigured_realm_is_not_an_error(tmp_path):
    r = _realm(tmp_path)
    assert workspace.configured(r) is False
    assert workspace.exists(r) is False


def test_exists_reports_whether_the_root_is_on_this_machine(tmp_path):
    here = tmp_path / "here"
    here.mkdir()
    assert workspace.exists(_realm(tmp_path / "a", ws=str(here))) is True
    assert workspace.exists(_realm(tmp_path / "b", ws=str(tmp_path / "gone"))) is False


# ---------------------------------------------------------------- expansion

def test_expand_substitutes_the_root(tmp_path):
    r = _realm(tmp_path, ws="D:\\Work")
    assert workspace.expand("open {workspace}\\Finance\\q1.xlsx", r) == "open D:\\Work\\Finance\\q1.xlsx"


def test_expand_survives_a_windows_root(tmp_path):
    """re.sub reads escapes in a string replacement; D:\\Work would be mangled at the \\W."""
    r = _realm(tmp_path, ws="D:\\Work")
    assert workspace.expand("{workspace}", r) == "D:\\Work"
    r2 = _realm(tmp_path / "2", ws="C:\\Users\\m\\g1\\x")
    assert workspace.expand("{workspace}", r2) == "C:\\Users\\m\\g1\\x"


def test_expand_is_forgiving_about_how_the_token_is_typed(tmp_path):
    r = _realm(tmp_path, ws="D:\\Work")
    for tok in ["{workspace}", "{WORKSPACE}", "{ workspace }", "{Workspace}"]:
        assert workspace.expand(tok, r) == "D:\\Work", tok


def test_expand_handles_several_occurrences(tmp_path):
    r = _realm(tmp_path, ws="/srv/work")
    out = workspace.expand("cp {workspace}/a {workspace}/b", r)
    assert out == "cp /srv/work/a /srv/work/b"


def test_a_trailing_separator_on_the_root_is_not_doubled(tmp_path):
    r = _realm(tmp_path, ws="D:\\Work\\")
    assert workspace.expand("{workspace}\\Finance", r) == "D:\\Work\\Finance"


def test_unset_workspace_leaves_the_token_visible(tmp_path):
    """Expanding to '' would turn {workspace}\\Finance into \\Finance — a path that looks real and
    isn't. A prompt that still says {workspace} at least names its own problem."""
    r = _realm(tmp_path)
    assert workspace.expand("{workspace}\\Finance", r) == "{workspace}\\Finance"


def test_expand_leaves_ordinary_text_alone(tmp_path):
    r = _realm(tmp_path, ws="D:\\Work")
    for s in ["", "no token here", "{other}", "{ws}"]:
        assert workspace.expand(s, r) == s


# ---------------------------------------------------------------- tokenizing (the migration)

@pytest.mark.parametrize("spelling", [
    "D:\\Work\\Finance\\notes.md",
    "D:\\\\Work\\\\Finance\\\\notes.md",
    "D:/Work/Finance/notes.md",
    "d:\\work\\Finance\\notes.md",
])
def test_tokenize_catches_every_spelling_of_the_root(spelling):
    out, n = workspace.tokenize(spelling, "D:\\Work")
    assert n == 1
    assert out.startswith("{workspace}"), out
    assert "Work" not in out.replace("{workspace}", ""), out


def test_tokenize_handles_the_messy_real_cases():
    """From the live realm: markdown bold running into a path, and a mixed-separator path."""
    out, n = workspace.tokenize("The folder is **D:\\Work** and D:\\Work/Hand/cabinet\\", "D:\\Work")
    assert n == 2
    assert out == "The folder is **{workspace}** and {workspace}/Hand/cabinet\\"


def test_tokenize_counts_and_replaces_all_occurrences():
    text = "D:\\Work\\a then D:\\Work\\b then D:/Work/c"
    out, n = workspace.tokenize(text, "D:\\Work")
    assert n == 3 and "D:\\Work" not in out and "D:/Work" not in out


def test_tokenize_is_a_no_op_without_a_root():
    assert workspace.tokenize("D:\\Work\\x", "") == ("D:\\Work\\x", 0)
    assert workspace.tokenize("", "D:\\Work") == ("", 0)


def test_tokenize_then_expand_is_a_round_trip(tmp_path):
    r = _realm(tmp_path, ws="E:\\Data")
    original = "read D:\\Work\\Finance\\x.csv and write D:/Work/out.md"
    tokenized, n = workspace.tokenize(original, "D:\\Work")
    assert n == 2
    assert workspace.expand(tokenized, r) == "read E:\\Data\\Finance\\x.csv and write E:\\Data/out.md"


# ---------------------------------------------------------------- detection

def test_detect_root_finds_the_dominant_root_in_job_prompts(tmp_path):
    r = _realm(tmp_path, jobs={
        "a": "work in D:\\Work\\Finance and D:\\Work\\Hand",
        "b": "also D:\\Work\\Education",
        "c": "one mention of C:\\Other\\Thing",
    })
    assert workspace.detect_root(r) == "D:\\Work"


def test_detect_root_is_empty_when_there_is_nothing_to_find(tmp_path):
    assert workspace.detect_root(_realm(tmp_path, jobs={"a": "no paths at all"})) == ""


# ---------------------------------------------------------------- wiring

def test_the_job_runner_expands_the_token():
    src = __import__("inspect").getsource(runner._run_job_inner)
    assert "workspace.expand" in src, "job prompts are not expanded — the token would reach the agent raw"


def test_the_preamble_teaches_the_token_when_a_root_is_set(tmp_path):
    r = _realm(tmp_path, ws="D:\\Work")
    pre = runner._host_preamble(r)
    assert "D:\\Work" in pre and "{workspace}" in pre


def test_the_preamble_says_nothing_about_it_when_unset(tmp_path):
    pre = runner._host_preamble(_realm(tmp_path))
    assert "{workspace}" not in pre, "don't teach a token the realm hasn't got a root for"
