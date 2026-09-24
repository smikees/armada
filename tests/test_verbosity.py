"""Per-agent and per-realm verbosity.

The risk this feature carries isn't a bug, it's a misreading: "be brief" is easily heard as "do
less". Most of these guard the wording that stops that, and the carve-outs that keep failures and
approvals legible no matter how terse the setting.
"""
import json

import pytest

from armada import memory, verbosity


@pytest.fixture
def realm(tmp_path):
    def _mk(realm_cfg=None, agent_cfg=None):
        cfg = {"name": "t"}
        cfg.update(realm_cfg or {})
        (tmp_path / "realm.json").write_text(json.dumps(cfg), encoding="utf-8")
        d = tmp_path / "agents" / "steve"
        d.mkdir(parents=True, exist_ok=True)
        (d / "agent.json").write_text(json.dumps(agent_cfg or {}), encoding="utf-8")
        return tmp_path
    return _mk


def test_there_are_four_levels_in_increasing_order():
    assert list(verbosity.LEVELS) == ["terse", "brief", "standard", "full"]
    assert verbosity.DEFAULT in verbosity.LEVELS


def test_the_default_is_what_agents_already_did():
    """Adding the setting must not silently change every existing realm's behaviour."""
    assert verbosity.DEFAULT == "standard"


def test_an_agent_inherits_the_realm_default(realm):
    r = realm(realm_cfg={"default_verbosity": "terse"})
    assert verbosity.realm_level(r) == "terse"
    assert verbosity.agent_level(r, "steve") == "terse"


def test_an_agent_can_override_the_realm(realm):
    r = realm(realm_cfg={"default_verbosity": "terse"}, agent_cfg={"verbosity": "full"})
    assert verbosity.agent_level(r, "steve") == "full"


def test_unknown_or_missing_values_fall_back_rather_than_break(realm):
    assert verbosity.normalise("chatty") == ""
    assert verbosity.normalise(None) == ""
    r = realm(realm_cfg={"default_verbosity": "chatty"})
    assert verbosity.realm_level(r) == verbosity.DEFAULT
    assert verbosity.agent_level(r, "nobody-here") == verbosity.DEFAULT


def test_a_broken_config_file_does_not_raise(tmp_path):
    (tmp_path / "realm.json").write_text("{not json", encoding="utf-8")
    assert verbosity.realm_level(tmp_path) == verbosity.DEFAULT


@pytest.mark.parametrize("level", list(verbosity.LEVELS))
def test_every_level_says_length_is_about_writing_not_working(level):
    """The failure mode: an agent reads 'be terse' and does a shallower job."""
    block = verbosity.prompt_block(level)
    assert "how much you WRITE, never how much you CHECK" in block


@pytest.mark.parametrize("level", list(verbosity.LEVELS))
def test_every_level_protects_failures_warnings_and_approvals(level):
    block = verbosity.prompt_block(level).lower()
    for must in ("what went wrong", "warnings", "approval", "error"):
        assert must in block, f"{level} must not allow {must!r} to be compressed"


def test_the_prompt_block_names_the_level():
    assert "(Terse)" in verbosity.prompt_block("terse")
    assert "(Detailed)" in verbosity.prompt_block("full")


def test_an_unconfigured_agent_still_gets_told_what_is_expected():
    assert verbosity.prompt_block("").strip()
    assert verbosity.label("") == verbosity.LEVELS[verbosity.DEFAULT][0]


def test_the_level_reaches_the_system_prompt(realm):
    r = realm(realm_cfg={"default_verbosity": "terse"})
    core = memory.assemble_core(r, r / "agents" / "steve", {})
    assert "# How much to write (Terse)" in core


def test_the_agent_override_reaches_the_system_prompt(realm):
    r = realm(realm_cfg={"default_verbosity": "terse"}, agent_cfg={"verbosity": "full"})
    core = memory.assemble_core(r, r / "agents" / "steve", {"verbosity": "full"})
    assert "# How much to write (Detailed)" in core
    assert "(Terse)" not in core


def test_verbosity_is_counted_as_mission_context(realm):
    """It's an instruction about voice, so it belongs in the same bucket as soul and tenets —
    otherwise the context breakdown in the UI under-reports the prompt."""
    r = realm()
    before = memory.core_breakdown(r, r / "agents" / "steve", {})
    assert before["mission"] > 0


def test_both_pages_offer_the_setting():
    from armada.webui import pages, agentframe
    assert 'id="st-verbosity"' in open(pages.__file__, encoding="utf-8").read()
    src = open(agentframe.__file__, encoding="utf-8").read()
    assert 'id="c-verbosity"' in src
    assert "inherit realm default" in src


def test_every_inherit_dropdown_names_what_you_would_get(realm):
    """'inherit' alone is a blank cheque — you have to open Realm settings to find out what it
    means. All three inherit options now read the same way and name the actual default."""
    from armada.webui import agentcommon
    r = realm(realm_cfg={"default_effort": "max", "default_model": "claude-opus-5"})
    assert 'inherit realm default (max)' in agentcommon._effort_options(r, "", inherit=True)
    assert 'inherit realm default (Claude Opus 5)' in agentcommon._model_options(r, "", inherit=True)


def test_a_realm_with_no_default_set_still_reads_sensibly(realm):
    from armada.webui import agentcommon
    r = realm()
    # effort has a built-in floor; model may genuinely have none yet, and must not say "(None)"
    assert "inherit realm default (high)" in agentcommon._effort_options(r, "", inherit=True)
    assert ">inherit realm default</option>" in agentcommon._model_options(r, "", inherit=True)


def test_the_inherit_option_is_preselected_when_nothing_is_overridden(realm):
    from armada.webui import agentcommon
    r = realm(realm_cfg={"default_effort": "high"})
    assert '<option value="" selected>' in agentcommon._effort_options(r, "", inherit=True)
    assert '<option value="" >' in agentcommon._effort_options(r, "low", inherit=True)


def test_no_page_still_offers_a_bare_inherit():
    from armada.webui import pages, agentframe, realmpages
    for mod in (pages, agentframe, realmpages):
        src = open(mod.__file__, encoding="utf-8").read()
        assert '">inherit</option>' not in src, f"{mod.__name__} still has the old bare label"


def test_both_save_paths_send_it():
    from armada.webui import pages
    agent_js = open(pages.__file__.replace("pages.py", "static/js/agent.js"), encoding="utf-8").read()
    set_js = open(pages.__file__.replace("pages.py", "static/js/settings.js"), encoding="utf-8").read()
    assert "verbosity:(document.getElementById('c-verbosity')" in agent_js
    assert "default_verbosity:(document.getElementById('st-verbosity')" in set_js
