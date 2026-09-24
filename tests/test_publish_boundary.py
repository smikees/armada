"""Agents are told where their output belongs, and ARMADA notices when a run writes elsewhere.

A working agreement, not a cage: an agent's capabilities (a shell server, say) can reach the whole
machine, and no boundary ARMADA draws changes that. What it can do is state the convention and
record when it's crossed — a stray file you know about is a filing problem, one you don't is how a
realm quietly stops being self-contained.
"""
import inspect
import json

import pytest

from armada import appconfig, approot, runner


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    cfgdir = tmp_path / "home" / ".armada"
    cfgdir.mkdir(parents=True)
    monkeypatch.setattr(appconfig, "_path", lambda: cfgdir / "config.json")
    yield


def _realm(tmp_path):
    root = tmp_path / "Work2"
    ad = root / "Cabinet-realm" / "agents" / "warren"
    (ad / "memory").mkdir(parents=True)
    (ad / "agent.json").write_text(json.dumps({"id": "warren"}), encoding="utf-8")
    (root / "Cabinet-realm" / "realm.json").write_text(json.dumps({"name": "C"}), encoding="utf-8")
    approot.set_root(str(root))
    return root / "Cabinet-realm", ad


# --------------------------------------------------------------------------- the stated rule

def test_the_preamble_names_the_root_and_the_agent_folder(tmp_path):
    realm, ad = _realm(tmp_path)
    t = runner._publish_boundary(realm, ad)
    assert approot.root() in t
    assert str(ad) in t
    assert "Do NOT write outside" in t


def test_it_says_reading_outside_is_fine(tmp_path):
    """The rule is about where output lands. Over-stating it would stop agents doing their job."""
    realm, ad = _realm(tmp_path)
    assert "Reading outside is fine" in runner._publish_boundary(realm, ad)


def test_no_root_means_no_claim(tmp_path):
    """Without a root there is no boundary to describe, and inventing one would be noise."""
    realm = tmp_path / "realm"
    (realm / "agents" / "warren").mkdir(parents=True)
    assert runner._publish_boundary(realm, realm / "agents" / "warren") == ""


def test_the_preamble_is_actually_included_in_a_tool_turn():
    src = inspect.getsource(runner._tool_preamble)
    assert "_publish_boundary" in src, "the rule is only real if agents are told it"


# --------------------------------------------------------------------------- the detection

def test_a_file_inside_the_root_is_not_flagged(tmp_path):
    realm, ad = _realm(tmp_path)
    cap = runner._TurnCapture(realm, ad, True)
    cap.on_event({"kind": "tool", "name": "Write",
                  "input": {"file_path": str(ad / "report.md")}})
    assert cap.stray == []
    assert cap.outputs[0].get("outside_root") is None


def test_a_file_elsewhere_under_the_root_is_not_flagged(tmp_path):
    """Writing into a sibling folder inside the root is normal — it's the root that matters."""
    realm, ad = _realm(tmp_path)
    other = approot.root() + "\\shared\\out.csv"
    cap = runner._TurnCapture(realm, ad, True)
    cap.on_event({"kind": "tool", "name": "Write", "input": {"file_path": other}})
    assert cap.stray == []


def test_a_file_outside_the_root_is_flagged_but_still_recorded(tmp_path):
    realm, ad = _realm(tmp_path)
    outside = tmp_path / "Work" / "Hand" / "brief.md"
    outside.parent.mkdir(parents=True)
    cap = runner._TurnCapture(realm, ad, True)
    cap.on_event({"kind": "tool", "name": "Write", "input": {"file_path": str(outside)}})
    assert cap.stray == [str(outside)]
    assert cap.outputs[0]["outside_root"] is True
    assert cap.outputs[0]["name"] == "brief.md", "flagging must not lose the artefact itself"


def test_flagging_does_not_block_the_write(tmp_path):
    """Detection, not prevention. Nothing here should look like a veto."""
    src = inspect.getsource(runner._TurnCapture._add_output)
    assert "raise" not in src and "return False" not in src


def test_nothing_is_flagged_when_no_root_is_set(tmp_path):
    realm = tmp_path / "realm"
    ad = realm / "agents" / "warren"
    ad.mkdir(parents=True)
    cap = runner._TurnCapture(realm, ad, True)
    cap.on_event({"kind": "tool", "name": "Write", "input": {"file_path": str(tmp_path / "x.md")}})
    assert cap.stray == []


def test_the_run_report_carries_the_strays():
    src = inspect.getsource(runner._run_job_inner)
    assert "outside_root" in src and "cap.stray" in src, \
        "a job that scatters files must say so where the record survives"
