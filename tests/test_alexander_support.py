"""Alexander in the app (6.2/6.3/6.6; armada/alexander/support.py): what he's given, what a reply
becomes, and that nothing he writes acts without the owner."""
import json
from pathlib import Path

import pytest

from armada import sysusage, util
from armada.alexander import support
from armada.engine.base import RunResult, Usage


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(util, "data_dir", lambda: tmp_path / ".armada")
    return tmp_path


@pytest.fixture
def realm(home):
    from armada.setup import scaffold
    root = home / "ARMADA" / "Home"
    scaffold(str(root), "company", "Home")
    jd = root / "agents" / "cfo" / "jobs"
    jd.mkdir(parents=True, exist_ok=True)
    (jd / "weekly-cash.json").write_text(json.dumps({"id": "weekly-cash", "name": "Weekly cash", "schedule": "mon 09:00"}), "utf-8")
    return root


class _Engine:
    name = "fake"

    def __init__(self, output, ok=True):
        self.output, self.ok, self.calls = output, ok, []

    def run(self, **kw):
        self.calls.append(kw)
        return RunResult(ok=self.ok, output=self.output, model="claude-opus-5-5",
                         usage=Usage(input=900, output=100, cost_usd=0.02), error="" if self.ok else "boom")


def test_he_is_given_every_section_and_no_secrets(realm):
    (realm / "realm.json").write_text(json.dumps({**json.loads((realm / "realm.json").read_text("utf-8")),
                                                  "note": "sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAAAAAA"}), "utf-8")
    text = support.build(realm, support.new_id(), "why didn't my job run", page="/jobs")
    for sec in ("<help>", "<realm>", "<page>", "<logs>", "<addon_contract>", "<remedies>"):
        assert sec in text, sec
    assert "cfo/weekly-cash" in text and "Weekly cash" in text
    assert '<page name="jobs">' in text.split("<help>")[1][:200]   # the relevant page first
    assert "sk-ant" not in text


def test_a_turn_runs_sealed_on_opus_high_and_counts_as_system(realm):
    eng = _Engine("Your scheduler is off [help: jobs].\n\n```remedy\n"
                  '{"name": "start_scheduler", "args": {}, "why": "Nothing runs without it."}\n```')
    r = support.ask(realm, "", "why didn't my job run", page="/jobs", engine=eng)
    kw = eng.calls[0]
    assert kw["model"] == "claude-opus-5-5" and kw["effort"] == "high" and kw["allow_tools"] is False
    assert r["ok"] and "```" not in r["text"] and r["cards"][0]["endpoint"] == "/api/scheduler-start"
    assert sysusage.runs(realm)[-1]["task"] == "alexander"
    roles = [m["role"] for m in support.history(r["id"])]
    assert roles == ["owner", "alexander"]
    eng2 = _Engine("Still here.")
    support.ask(realm, r["id"], "thanks", engine=eng2)
    assert "<conversation>" in eng2.calls[0]["prompt"] and "why didn't my job run" in eng2.calls[0]["prompt"]


def test_only_valid_proposals_become_cards_one_of_each(realm):
    text = ("Here.\n```remedy\n{\"name\": \"format_disk\", \"args\": {}}\n```\n"
            "```remedy\n{\"name\": \"run_job\", \"args\": {\"agent\": \"cfo\", \"job\": \"weekly-cash\"}}\n```\n"
            "```remedy\n{\"name\": \"check_updates\", \"args\": {}}\n```\n"
            "```addon\n{\"armada_addon\": 1, \"id\": \"x\", \"name\": \"X\", \"provides\": {\"themes\": [{\"id\": \"t\"}]}}\n```\n"
            "```report\nnot json\n```")
    prose, cards = support.parse(text, realm)
    assert prose == "Here."
    assert [c["type"] for c in cards] == ["remedy"] and cards[0]["name"] == "run_job"


def test_a_widget_addon_card_installs_once_and_shows_on_the_overview(realm):
    m = {"armada_addon": 1, "id": "reading-list", "name": "Reading list", "version": "1.0.0",
         "provides": {"widgets": [{"id": "list", "title": "Reading list", "kind": "markdown",
                                   "body": "- **Dune**\n- <script>alert(1)</script>"}]}}
    _prose, cards = support.parse("```addon\n" + json.dumps(m) + "\n```", realm)
    assert cards[0]["type"] == "addon" and "Reading list" in cards[0]["what"]
    r = support.install_addon(realm, m, "realm")
    assert r["ok"] and r["widgets"] == ["reading-list/list"]
    assert support.install_addon(realm, m, "realm")["ok"] is False          # never overwrites
    from armada import reader
    from armada.webui import pages
    html = pages.render_dashboard(reader.read(str(realm)), realm)
    assert 'data-id="addon:reading-list/list"' in html and "<strong>Dune</strong>" in html
    assert "<script>alert(1)" not in html                                   # data, never code


def test_a_report_card_carries_his_write_up_redacted(realm):
    rep = {"summary": "Jobs page crashes", "what_happened": "C:\\Users\\mihai\\x failed",
           "context": "saw sk-ant-api03-BBBBBBBBBBBBBBBBBBBBBBBBBBBB"}
    _p, cards = support.parse("```report\n" + json.dumps(rep) + "\n```", realm)
    msg = cards[0]["message"]
    assert cards[0]["type"] == "report" and msg.startswith("Jobs page crashes")
    assert "sk-ant" not in msg and "mihai" not in msg


def test_a_failed_turn_says_why_and_still_counts(realm):
    r = support.ask(realm, "", "hello", engine=_Engine("", ok=False))
    assert r["ok"] is False and r["error"] == "boom"
    assert sysusage.runs(realm)[-1]["status"] == "failed"


def test_conversation_ids_are_checked(home):
    assert support.history("../../etc/passwd") == [] and not support.valid_id("../x")


def test_ask_alexander_appears_only_on_failed_runs_and_is_safely_quoted():
    import html
    import re
    from armada.webui._base import _ask_alexander
    assert _ask_alexander("cfo", "cash", {"status": "ok"}) == ""
    b = _ask_alexander("cfo", "cash", {"status": "error", "ts": "2026-09-25T09:00:00",
                                       "summary": "boom \"quoted\" </script><b>x</b>"})
    assert "Ask Alexander" in b and "<b>x</b>" not in b and "</script>" not in b
    arg = html.unescape(re.search(r'onclick="mcAlexAsk\((.*)\)"', b).group(1))
    assert '"job": "cash"' in arg or '"job":"cash"' in arg
