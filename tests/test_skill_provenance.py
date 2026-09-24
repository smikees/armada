"""Where a skill came from, recorded beside it and read back by the Catalogue.

There are three ways a capability reaches a realm: added from the Catalogue, written here, or
fetched from somewhere else by an agent. Only the first left any trace. The other two both landed
under "You" — so a skill pulled off a repository was presented as something the owner wrote, which
is the one claim that decides whether it gets reviewed.
"""
import datetime
import json

import pytest

from armada import catalogue as C
from armada.catalogue import _shared as CSHARED, sources as CSRC, realm as CREALM
from armada import sysskills


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    # Patched on every module that resolves the name bare, not just the package re-export — see
    # catalogue/__init__.py's module docstring on the monkeypatch/bare-name trap (Phase 2, 2.4/2.9).
    monkeypatch.setattr(C, "_dir", lambda: tmp_path / "catalogue")
    monkeypatch.setattr(CSHARED, "_dir", lambda: tmp_path / "catalogue")
    monkeypatch.setattr(CSRC, "_dir", lambda: tmp_path / "catalogue")
    monkeypatch.setattr(C, "_marketplaces_dir", lambda: tmp_path / "marketplaces")
    monkeypatch.setattr(CSRC, "_marketplaces_dir", lambda: tmp_path / "marketplaces")
    monkeypatch.setattr(CREALM, "_marketplaces_dir", lambda: tmp_path / "marketplaces")
    monkeypatch.setattr(C, "_get_json", lambda url: None)
    monkeypatch.setattr(CSHARED, "_get_json", lambda url: None)
    monkeypatch.setattr(CSRC, "_get_json", lambda url: None)
    monkeypatch.setattr(CREALM, "_get_json", lambda url: None)
    monkeypatch.setattr(C, "_known_realms", lambda: [])
    monkeypatch.setattr(CSHARED, "_known_realms", lambda: [])
    monkeypatch.setattr(CSRC, "_known_realms", lambda: [])
    monkeypatch.setattr(CREALM, "_known_realms", lambda: [])
    return tmp_path


def _skill(root, name, desc="Does a thing", record=None):
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {desc}\n---\nbody\n",
                                encoding="utf-8")
    if record is not None:
        (d / C.PROVENANCE_FILE).write_text(json.dumps(record), encoding="utf-8")
    return d


@pytest.fixture
def skills(tmp_path, monkeypatch):
    root = tmp_path / "skills"
    root.mkdir()
    monkeypatch.setattr(C, "_skill_roots", lambda: [(root, "Cabinet")])
    monkeypatch.setattr(CSRC, "_skill_roots", lambda: [(root, "Cabinet")])
    return root


def _by_id(entries):
    return {e["id"]: e for e in entries}


# --- reading the record ----------------------------------------------------------------------------

def test_a_skill_with_no_record_says_nothing(skills):
    d = _skill(skills, "quiet")
    assert C.read_provenance(d) == {}


def test_a_record_reads_back_whole(skills):
    d = _skill(skills, "fetched", record={"origin": "installed", "source": "https://x/y",
                                          "by": "marcus", "at": "2026-09-20T10:00:00+02:00",
                                          "why": "asked for"})
    p = C.read_provenance(d)
    assert p["origin"] == "installed" and p["source"] == "https://x/y" and p["by"] == "marcus"


@pytest.mark.parametrize("bad", [{"origin": "downloaded"}, {"origin": ""}, {}, [1, 2], "nope"])
def test_a_record_that_does_not_say_origin_is_no_record(skills, bad):
    """A malformed file must read as silence, not as a default. Guessing "authored" into the
    blank invents the one fact the file exists to establish."""
    d = _skill(skills, "odd")
    (d / C.PROVENANCE_FILE).write_text(json.dumps(bad), encoding="utf-8")
    assert C.read_provenance(d) == {}


# --- which source a skill lands in -------------------------------------------------------------------

def test_authored_and_unmatched_is_yours(skills):
    _skill(skills, "house-style")
    ent = _by_id(C.from_mine(known=[])[0])
    assert ent["house-style"]["source"] == C.MINE
    assert ent["house-style"]["author"] == "You"


def test_installed_is_its_own_source(skills):
    _skill(skills, "grabbed", record={"origin": "installed", "source": "https://github.com/a/b"})
    ent = _by_id(C.from_mine(known=[])[0])
    assert ent["grabbed"]["source"] == C.INSTALLED
    assert ent["grabbed"]["author"] != "You", "it is not yours just because it is on your disk"
    assert ent["grabbed"]["install"]["origin_note"] == "https://github.com/a/b"


def test_an_installed_skill_is_not_trusted_by_authorship(skills):
    """`curated` is what the trust badge reads. Something fetched off the internet is exactly as
    reviewed as wherever it came from, which is usually nobody."""
    _skill(skills, "grabbed", record={"origin": "installed", "source": "https://x"})
    _skill(skills, "written")
    ent = _by_id(C.from_mine(known=[])[0])
    assert ent["written"]["curated"] == C.CURATED_OFFICIAL
    assert ent["grabbed"]["curated"] == ""


def test_an_explicitly_authored_record_stays_yours(skills):
    _skill(skills, "mine-really", record={"origin": "authored", "by": "warren"})
    ent = _by_id(C.from_mine(known=[])[0])
    assert ent["mine-really"]["source"] == C.MINE


# --- the ones that were already there ------------------------------------------------------------

def test_an_undocumented_skill_the_catalogue_knows_takes_its_metadata(skills):
    """Most of what is already on disk came over from Claude Desktop. Claiming the owner wrote
    Anthropic's skill because it sits in their folder is worse than saying nothing."""
    _skill(skills, "docx", desc="")
    known = [C._entry(C.SKILLS, "skills", "docx", "Docx", "Work with Word documents",
                      author="Anthropic", homepage="https://github.com/anthropics/skills")]
    ent = _by_id(C.from_mine(known=known)[0])
    assert ent["docx"]["source"] == C.INSTALLED
    assert ent["docx"]["author"] == "Anthropic"
    assert ent["docx"]["description"] == "Work with Word documents"
    assert ent["docx"]["install"]["origin_note"] == "Anthropic skills"


def test_an_undocumented_skill_nobody_knows_is_authored(skills):
    _skill(skills, "entirely-my-own")
    known = [C._entry(C.SKILLS, "skills", "docx", "Docx", "Word", author="Anthropic")]
    ent = _by_id(C.from_mine(known=known)[0])
    assert ent["entirely-my-own"]["source"] == C.MINE


def test_a_record_beats_a_catalogue_match(skills):
    """If an agent said it wrote this, that is a statement about what happened; a name collision
    with something in the catalogue is not."""
    _skill(skills, "docx", record={"origin": "authored", "by": "warren"})
    known = [C._entry(C.SKILLS, "skills", "docx", "Docx", "Word", author="Anthropic")]
    ent = _by_id(C.from_mine(known=known)[0])
    assert ent["docx"]["source"] == C.MINE


# --- the record travels --------------------------------------------------------------------------

def test_the_record_lives_beside_the_skill(skills, tmp_path):
    """In the folder, so it survives being copied to another realm. A central ledger would be one
    more thing to fall out of step with what is actually on disk."""
    d = _skill(skills, "portable", record={"origin": "installed", "source": "https://x"})
    assert (d / C.PROVENANCE_FILE).is_file()
    import shutil
    moved = tmp_path / "elsewhere" / "portable"
    shutil.copytree(d, moved)
    assert C.read_provenance(moved)["source"] == "https://x"


# --- the system skill ------------------------------------------------------------------------------

def test_the_registry_skill_ships_with_the_app():
    ids = [s["id"] for s in sysskills.list_system_skills()]
    assert "skill-registry" in ids


def test_every_agent_is_told_to_register_without_being_granted_anything(tmp_path):
    """A register only works if everybody keeps it. One ungranted agent quietly filing nothing
    leaves the owner with a list that looks complete and isn't."""
    from armada import runner
    agent = tmp_path / "agents" / "warren"
    agent.mkdir(parents=True)
    text = runner._skill_registry_contract(agent)
    assert "armada.json" in text
    assert '"origin"' in text
    assert "warren" in text, "the agent's own id should be filled in for it"
    assert "<your-agent-id>" not in text


def test_the_contract_and_the_page_show_the_same_words():
    """The owner can read what their agents were told, and it updates when ARMADA does."""
    from pathlib import Path
    from armada import runner
    it = sysskills.get_system_skill("skill-registry")
    text = runner._skill_registry_contract(Path("agents/warren"))
    assert it["body"].strip()[:80] in text


def test_a_missing_bundle_does_not_break_a_run(tmp_path, monkeypatch):
    from armada import runner
    monkeypatch.setattr(sysskills, "get_system_skill", lambda sid: None)
    assert runner._skill_registry_contract(tmp_path) == ""
