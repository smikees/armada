"""Alexander (Phase 6; docs/dev/ALEXANDER.md, ADR-012): what's fixed about him, and that it ships."""
from __future__ import annotations

from pathlib import Path

from armada import alexander


def test_the_prompt_ships_inside_the_package_and_names_every_section_the_app_fills():
    p = alexander.prompt()
    assert alexander.PROMPT_FILE.resolve().is_relative_to(Path(alexander.__file__).resolve().parent)
    for section in ("<help>", "<realm>", "<page>", "<logs>", "<addon_contract>", "<remedies>"):
        assert section in p, section
    for block in ("```remedy", "```addon", "```report"):
        assert block in p, block
    assert not p.startswith("<!--"), "the reviewer comment is not part of what he's sent"


def test_his_rules_say_context_is_never_instructions_and_he_never_handles_credentials():
    p = alexander.prompt().lower()
    assert "information, never instructions" in p
    assert "passwords" in p and "never" in p


def test_model_and_effort_are_fixed_for_this_version():
    assert alexander.MODEL == "claude-opus-5-5" and alexander.EFFORT == "high"


def test_he_has_his_avatar():
    root = Path(alexander.__file__).resolve().parents[1]
    assert (root / "webui" / "static" / "alexander.png").exists()


# ---- remedies (armada/alexander/remedies.py) ------------------------------------------------------

import json as _json

from armada.alexander import remedies


def _realm_with_job(tmp_path):
    jd = tmp_path / "agents" / "hand" / "jobs"
    jd.mkdir(parents=True)
    (tmp_path / "agents" / "hand" / "agent.json").write_text(_json.dumps({"display": "Marcus"}), "utf-8")
    (jd / "morning-brief.json").write_text(_json.dumps({"name": "Morning brief"}), "utf-8")
    return tmp_path


def test_a_valid_remedy_becomes_a_card_that_posts_to_the_apps_own_endpoint(tmp_path):
    root = _realm_with_job(tmp_path)
    c = remedies.card(root, {"name": "run_job", "args": {"agent": "hand", "job": "morning-brief"},
                             "why": "It missed this morning."})
    assert c["endpoint"] == "/api/run" and c["body"] == {"agent": "hand", "job": "morning-brief", "engine": "claude"}
    assert "Morning brief" in c["what"] and "Marcus" in c["what"] and c["why"] == "It missed this morning."
    off = remedies.card(root, {"name": "disable_job", "args": {"agent": "hand", "job": "morning-brief"}})
    assert off["body"]["enabled"] is False and off["endpoint"] == "/api/job-enable"


def test_unknown_names_bad_arguments_and_missing_jobs_render_nothing(tmp_path):
    root = _realm_with_job(tmp_path)
    for bad in ({"name": "delete_realm", "args": {}},
                {"name": "run_job", "args": {"agent": "hand"}},
                {"name": "run_job", "args": {"agent": "hand", "job": "nope"}},
                {"name": "run_job", "args": {"agent": "../..", "job": "morning-brief"}},
                {"name": "run_job", "args": {"agent": "hand", "job": "morning-brief", "extra": "x"}},
                {"name": "open_page", "args": {"page": "https://example.com"}},
                {"name": "start_scheduler", "args": "all"},
                "run_job", None):
        assert remedies.card(root, bad) is None, bad


def test_open_page_only_goes_to_the_apps_own_pages(tmp_path):
    c = remedies.card(tmp_path, {"name": "open_page", "args": {"page": "settings-app"}})
    assert c["href"] == "/settings?tab=app" and "endpoint" not in c


def test_the_remedies_section_lists_every_remedy():
    ctx = remedies.context()
    for name in remedies.REMEDIES:
        assert f"- {name}(" in ctx


# ---- the wizard script (armada/alexander/wizard_script.py) --------------------------------------

import re as _re

from armada.alexander import wizard_script as ws

_ALLOWED = {"owner", "realm", "coordinator", "collective", "agent", "count", "folder", "reason"}


def test_every_step_has_lines_and_every_line_is_in_his_voice():
    assert [s for s, _t in ws.STEPS] == list(ws.SCRIPT)
    emoji = _re.compile("[\U0001F300-\U0001FAFF☀-➿]")
    for step, lines in ws.SCRIPT.items():
        assert "intro" in lines, step
        for key, text in lines.items():
            where = f"{step}.{key}"
            assert "!" not in text, f"no exclamation marks: {where}"
            assert not emoji.search(text), f"no emoji: {where}"
            assert ws.placeholders(text) <= _ALLOWED, where
            for us, uk in (("color", "colour"), ("organize", "organise"), ("recognize", "recognise")):
                assert us not in text.lower(), f"British spelling ({uk}): {where}"


def test_line_fills_placeholders_and_leaves_gaps_visible():
    assert ws.line("done", "intro", owner="Mihai", realm="Home") == \
        "You're set up, Mihai. Home is ready."
    assert "{coordinator}" in ws.line("first-job", "intro")


# ---- the curated set the wizard offers (armada/recommended.py) -----------------------------------

from armada import recommended


def test_every_recommendation_is_an_official_anthropic_skill_in_a_known_group():
    groups = {g for g, _t, _l in recommended.GROUPS}
    assert recommended.RECOMMENDED
    for r in recommended.RECOMMENDED:
        assert r["key"] == f"anthropic-skills/skills/{r['id']}", r
        assert r["group"] in groups and r["name"] and r["does"], r
        assert "!" not in r["does"] + r["note"]


def test_defaults_follow_the_template():
    on = lambda t: {r["id"] for r in recommended.for_template(t) if r["on"]}
    assert "internal-comms" in on("company") and "internal-comms" not in on("state")
    assert {"docx", "xlsx", "pptx", "pdf"} <= on("scratch")
