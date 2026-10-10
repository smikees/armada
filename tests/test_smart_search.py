"""Smart search (Add a capability): sources, Alexander's sealed turn, and the cards it may show.

Synthetic realms and fake sources only; no provider or network is contacted.
"""
import json
from pathlib import Path

import pytest

from armada import capabilities, connector_registry as registry, smart_search as ss, sysskills, util
from armada.engine.base import RunResult

DIRECTORY = {"at": 9e18, "featured": ["foxit@openai-curated-remote"], "plugins": [
    {"name": "foxit", "title": "Foxit PDF Editor", "short": "Edit PDFs", "long": "Open, edit and share PDFs.",
     "category": "Productivity", "developer": "Foxit", "installed": False, "featured": True},
    {"name": "gmail", "title": "Gmail", "short": "Read and manage Gmail", "long": "", "category": "Communication",
     "developer": "OpenAI", "installed": True, "featured": False},
]}


@pytest.fixture
def realm(tmp_path, monkeypatch):
    util.write_json_atomic(tmp_path / "realm.json", {"name": "Synthetic", "schema_version": 4, "toolkit": {
        "connectors": [{"id": "claude.ai Gmail", "name": "claude.ai Gmail", "command": "https://gmail.mcp.claude.com/mcp"}],
        "skills": [{"id": "pdf-notes", "name": "PDF notes", "description": "Summarise PDF files"}]}})
    monkeypatch.setattr(ss, "chatgpt_directory", lambda refresh=False: DIRECTORY)
    from armada import catalogue as cat
    monkeypatch.setattr(cat, "load", lambda: {"entries": [
        {"key": "mine/skills/humanizer", "id": "humanizer", "name": "Humanizer", "kind": "skills", "source": "mine",
         "description": "Make text sound human", "install": {"path": str(tmp_path / "x")}},
        {"key": "anthropic-skills/skills/pdf", "id": "pdf", "name": "Pdf", "kind": "skills",
         "source": "anthropic-skills", "description": "Read and create PDFs", "homepage": "https://github.com/anthropics/skills/tree/main/skills/pdf"},
    ]})
    monkeypatch.setattr(cat, "search_registry", lambda q, limit=20, sample=False: ([], ""))
    monkeypatch.setattr(ss, "_claude_code_rows", lambda: [
        {"kind": "connectors", "name": "claude.ai Gmail", "detail": "https://gmail.mcp.claude.com/mcp"},
        {"kind": "connectors", "name": "claude.ai Interactive Brokers (IBKR)", "detail": "https://api.ibkr.com"}])
    return tmp_path


def test_sources_answer_what_you_have_and_where_to_find_more(realm):
    assert [r["name"] for r in ss.search(realm, "realm", "pdf")] == ["PDF notes"]
    mine = ss.search(realm, "my-skills", "")
    assert mine[0]["name"] == "Humanizer" and mine[0]["action"]["type"] == "add"
    cc = {r["name"]: r for r in ss.search(realm, "claude-code", "")}
    assert cc["Gmail"]["have"] == "realm" and cc["Gmail"]["action"]["type"] == "in-realm"
    assert cc["Interactive Brokers (IBKR)"]["action"]["type"] == "bring-in" and cc["Interactive Brokers (IBKR)"]["reach"] == "claude"
    plugins = ss.search(realm, "chatgpt-plugins", "pdf")
    assert plugins[0]["name"] == "Foxit PDF Editor" and plugins[0]["reach"] == "codex"
    assert plugins[0]["action"] == {"type": "codex-plugin", "plugin": "foxit", "title": "Foxit PDF Editor", "installed": False}
    assert [r["name"] for r in ss.search(realm, "chatgpt-installed", "")] == ["Gmail"]
    gmail = ss.search(realm, "chatgpt-installed", "")[0]
    assert gmail["action"]["type"] == "engine"                 # a curated service: Add for Codex creates "Gmail · Codex"
    skill = ss.search(realm, "anthropic-skills", "pdf")[0]
    assert skill["action"]["type"] == "review" and skill["action"]["url"].startswith("https://github.com/")


def test_a_switched_off_source_cannot_be_searched(realm):
    sess = ss.Session(realm, ["realm"])
    with pytest.raises(ValueError, match="switched off"):
        sess.run_search("mcp-registry", "pdf")
    out = sess.run_search("realm", "pdf")
    assert out["results"][0]["name"] == "PDF notes" and sess.searched == ["realm"]
    assert "about" in out["results"][0] and "action" not in out["results"][0]   # Alexander sees no actions


class _FakeClaude:
    """Calls the search tools the way Alexander would, then answers with one real and one invented key."""
    name = "claude"

    def doctor(self):
        return True, ""

    def run(self, system, prompt, **kw):
        assert kw["model"] == ss.MODEL and "search request" in prompt
        assert {t["name"] for t in self.managed_tools.tools()} == {"list_sources", "search"}
        found = self.managed_tools.call("search", {"source": "chatgpt-plugins", "query": "pdf"})
        key = found["results"][0]["key"]
        return RunResult(ok=True, output=json.dumps({"summary": "Two PDF editors; Codex only. " * 20,
            "results": [{"key": key, "why": "Well-known PDF editor"}, {"key": "chatgpt-plugins:invented", "why": "x"}]}))


def test_alexander_can_only_show_what_a_source_returned(realm, monkeypatch):
    monkeypatch.setattr("armada.engine.get_engine", lambda name="mock": _FakeClaude())
    res = ss.run(realm, "a PDF viewer from ChatGPT", ["chatgpt-plugins", "realm"])
    assert res["ok"] and [r["name"] for r in res["results"]] == ["Foxit PDF Editor"]
    assert res["results"][0]["why"] == "Well-known PDF editor"
    assert len(res["summary"]) <= ss.SUMMARY_MAX and res["searched"] == ["chatgpt-plugins"]
    from armada.webui.smartsearch import render_results
    html = render_results(realm, res)
    assert "Foxit PDF Editor" in html and "invented" not in html and "mcSsAddPlugin" in html
    assert "Searched: ChatGPT plugins" in html


def test_the_search_skill_ships_and_keeps_answers_short():
    skill = sysskills.get_system_skill("smart-search")
    body = skill["body"]
    assert "one or two short lines" in body and "data, not instructions" in body
    assert '"results"' in body and "Never invent" in body


def test_a_chatgpt_plugin_becomes_a_codex_row_and_binds_on_connect(realm, monkeypatch):
    from armada import codex_apps
    cid = registry.add_codex_plugin(realm, "foxit", name="Foxit PDF Editor", description="Edit PDFs")["capability"]
    cap = capabilities.find(realm, cid)[1]
    assert cap["name"] == "Foxit PDF Editor · Codex" and cap["reach"] == "codex" and cap["native_service"] == "foxit"
    with pytest.raises(ValueError, match="already in this realm for Codex"):
        registry.add_codex_plugin(realm, "foxit", name="Foxit PDF Editor")
    monkeypatch.setattr(codex_apps, "service", lambda s, cwd=None: {"app_id": "connector_abc123", "name": "Foxit"})
    registry.save(realm, capability=cid, service="foxit")       # what Connect on its Codex row does
    cap = capabilities.find(realm, cid)[1]
    assert cap["provider_bindings"] == {"codex": {"app_id": "connector_abc123"}} and cap["description"] == "Edit PDFs"
    with pytest.raises(ValueError, match="Unknown provider connector"):
        registry.save(realm, service="foxit", engine="codex")   # only curated services are added this way


def test_add_a_capability_is_search_link_and_directories(realm):
    from armada import reader
    from armada.webui.capabilities import _realm_skills
    html = _realm_skills(reader.read(str(realm)), realm)
    pane = html[html.index('id="cap-pane-catalogue"'):]
    assert 'id="ss-q"' in pane and "mcSmartSearch" in pane and "smartsearch.js" in pane
    assert all(f'value="{s}"' in pane for s in ss.SOURCE_IDS)          # every source can be switched
    assert "https://chatgpt.com/plugins" in pane and "https://claude.com/plugins" in pane
    assert "Bring a link" in pane and "cat-addr-url" in pane
    assert 'id="cat-q"' not in pane and 'id="cat-reach"' not in pane     # the old browser is gone


def test_smartsearch_script_is_valid_javascript():
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        pytest.skip("Node required")
    path = Path(ss.__file__).parent / "webui" / "static" / "js" / "smartsearch.js"
    subprocess.run([node, "--check", str(path)], check=True)
