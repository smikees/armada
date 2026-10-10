"""Engine reach: which engines a capability works with, one engine at a time, and model-change impact.

docs/dev/CAPABILITIES_UPGRADE.md. Synthetic realms only; no provider is contacted.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from armada import capabilities, capreach, connector_registry as registry, realmformat, util
from armada.routes.caps import CapabilityRoutes

IBKR = {"id": "claude_ai_Interactive_Brokers_IBKR", "name": "Interactive Brokers (IBKR)",
        "catalogue_key": "mcp-registry/connectors/com.ibkr/interactive-brokers-ibkr",
        "command": "https://api.ibkr.com/v1/api/mcp", "runs": "service"}
DOCS = {"id": "claude.ai Claude Docs", "name": "claude.ai Claude Docs",
        "command": "https://api.anthropic.com/v1/pages/mcp", "native_service": "google-drive",
        "provider_bindings": {"codex": {"app_id": "connector_5f3c8c41a1e54ad7a76272c89e2554fa"},
                              "gemini": {"disabled": True}}}
OPEN = {"id": "notion", "name": "Notion", "mcp_url": "https://mcp.notion.com/mcp"}
APP = {"id": "gmail-app", "name": "Gmail · ChatGPT app",
       "provider_bindings": {"codex": {"app_id": "connector_2128aebfecb84f64a069897515042a44"}}}


def _realm(tmp_path, connectors, agents):
    util.write_json_atomic(tmp_path / "realm.json", {"name": "Synthetic", "schema_version": 3,
                                                     "toolkit": {"connectors": connectors}})
    for aid, cfg in agents.items():
        util.write_json_atomic(tmp_path / "agents" / aid / "agent.json", {"id": aid, **cfg})
    return tmp_path


# --------------------------------------------------------------------------- reach rules

@pytest.mark.parametrize("kind,cap,scope,how", [
    ("skills", {"id": "s"}, "any", "Skill"),
    ("extensions", {"id": "e", "command": "node server.js"}, "any", "Local extension"),
    ("plugins", {"id": "p"}, "claude", "Claude Code plugin"),
    ("connectors", OPEN, "any", "Open server"),
    ("connectors", {"id": "claude.ai Docs", "command": "https://api.anthropic.com/mcp"}, "claude", "Claude connector"),
    ("connectors", APP, "codex", "ChatGPT app"),
    ("connectors", {"id": "claude.ai Something"}, "claude", "Claude connector"),
])
def test_reach_is_derived_from_what_the_record_says(kind, cap, scope, how):
    r = capreach.reach(kind, cap)
    assert (r.scope, r.how) == (scope, how)
    assert r.engines == (capreach.ENGINES if scope == "any" else (scope,))


def test_an_explicit_reach_wins_over_derivation():
    r = capreach.reach("connectors", {**OPEN, "reach": "claude"})
    assert r.scope == "claude" and not r.available_on("codex")


def test_a_connector_imported_from_claude_stays_claude_unless_it_is_portable():
    # Its address is public, but other engines can't sign in to it without service-specific setup.
    cap = {"id": "claude.ai Gmail", "command": "https://gmailmcp.googleapis.com/mcp/v1"}
    assert capreach.reach("connectors", cap).scope == "claude"
    # The same address added as an open server, or linked by the owner in another engine, is any.
    assert capreach.reach("connectors", {"id": "gmail", "mcp_url": cap["command"]}).scope == "any"
    linked = {**cap, "provider_bindings": {"codex": {"server_name": "gmail", "endpoint": cap["command"]}}}
    assert capreach.reach("connectors", linked).scope == "any"
    # A known one-engine-at-a-time service imported from Claude stays portable (it can be moved).
    assert capreach.reach("connectors", IBKR).scope == "any"


def test_interactive_brokers_is_one_engine_at_a_time_on_claude():
    r = capreach.reach("connectors", IBKR)
    assert r.scope == "any" and r.exclusive and r.engine == "claude"
    assert r.available_on("claude") and not r.available_on("codex")
    assert "one engine at a time" in r.blocked_reason("codex", "IBKR")
    assert "Interactive Brokers allows one AI platform" in r.exclusive_why


def test_moving_and_overriding_one_engine_at_a_time():
    assert capreach.reach("connectors", {**IBKR, "exclusive_engine": "codex"}).engine == "codex"
    assert not capreach.reach("connectors", {**IBKR, "exclusive": False}).exclusive
    custom = capreach.reach("connectors", {**OPEN, "exclusive": True})
    assert custom.exclusive and custom.engine == "claude" and "Marked as one engine" in custom.exclusive_why
    # A single-engine capability has nothing to move between.
    assert not capreach.reach("connectors", {**APP, "exclusive": True}).exclusive


def test_blocked_reason_names_the_engine_and_why():
    r = capreach.reach("connectors", APP)
    assert r.blocked_reason("claude", "Gmail") == "Gmail works only with Codex: it is a ChatGPT app."
    assert r.blocked_reason("codex", "Gmail") == ""


def test_catalogue_entries_have_a_reach_before_they_are_added():
    assert capreach.entry_reach({"source": "marketplace:claude-plugins-official", "kind": "plugins"}) == "claude"
    assert capreach.entry_reach({"source": "mcp-registry", "kind": "connectors",
                                 "install": {"remotes": [{"url": "https://x.example/mcp"}]}}) == "any"
    assert capreach.entry_reach({"source": "anthropic-skills", "kind": "skills"}) == "any"


# --------------------------------------------------------------------------- impact

def test_impact_lists_what_an_agent_would_lose_and_why(tmp_path):
    root = _realm(tmp_path, [IBKR, OPEN, APP], {
        "warren": {"model": "claude-opus-5-5", "display": "Warren",
                   "toolkit": {"connectors": [{"id": IBKR["id"]}, {"id": "notion"}, {"id": "gmail-app"}]}}})
    on_codex = capreach.impact(root, "warren", "codex")
    assert [x["id"] for x in on_codex] == [IBKR["id"]]
    on_claude = capreach.impact(root, "warren", "claude")
    assert [x["id"] for x in on_claude] == ["gmail-app"]
    assert capreach.impact_text("Warren", "codex", on_codex) == "On Codex, Warren can't use Interactive Brokers (IBKR)."
    assert capreach.impact_text("Warren", "gemini", []) == "All of Warren's capabilities work with Gemini."


def test_model_change_warning_lists_each_capability_lost(tmp_path):
    root = _realm(tmp_path, [IBKR, OPEN], {
        "warren": {"model": "claude-opus-5-5", "display": "Warren",
                   "toolkit": {"connectors": [{"id": IBKR["id"]}, {"id": "notion"}]}}})
    text = registry.model_change_warning(root, util.read_json_state(root / "agents/warren/agent.json"), "claude", "codex")
    assert "Moving from Claude to Codex changes what Warren can use." in text
    assert "Interactive Brokers (IBKR) is connected to Claude, one engine at a time." in text
    assert registry.model_change_warning(root, "warren", "claude", "claude") == ""


# --------------------------------------------------------------------------- enforcement

def test_policy_denies_out_of_reach_and_held_capabilities(tmp_path):
    root = _realm(tmp_path, [IBKR, APP, OPEN], {
        "a": {"toolkit": {"connectors": [{"id": IBKR["id"]}, {"id": "gmail-app"}, {"id": "notion"}]}}})
    policy = capabilities.execution_policy(root, "a")
    on_claude = capabilities.provider_policy(policy, "claude")
    assert "gmail-app" not in on_claude.allowed_mcp_ids and "mcp__gmail-app" in on_claude.denied_tools
    assert IBKR["id"] in on_claude.allowed_mcp_ids
    on_codex = capabilities.provider_policy(policy, "codex")
    assert not any("Interactive_Brokers" in s for s in on_codex.allowed_mcp_ids)
    assert any("Interactive_Brokers" in t for t in on_codex.denied_tools)


def test_after_a_move_the_old_engine_no_longer_admits_it(tmp_path):
    root = _realm(tmp_path, [{**IBKR, "exclusive_engine": "codex"}], {
        "a": {"toolkit": {"connectors": [{"id": IBKR["id"]}]}}})
    policy = capabilities.execution_policy(root, "a")
    assert IBKR["id"] not in capabilities.provider_policy(policy, "claude").allowed_mcp_ids


def test_agent_context_names_capabilities_withheld_on_this_engine(tmp_path):
    from armada import runner
    root = _realm(tmp_path, [IBKR, OPEN], {
        "a": {"toolkit": {"connectors": [{"id": IBKR["id"]}, {"id": "notion"}]}}})
    text = runner._capabilities_context(root, root / "agents" / "a", "codex")
    assert "NOT available on Codex" in text and "one engine at a time" in text
    mine = text.split("[Granted to you")[0]
    assert "Notion" in mine and "Interactive Brokers" not in mine
    # A test engine (no name) keeps the old inventory, untouched.
    assert "NOT available" not in runner._capabilities_context(root, root / "agents" / "a")


# --------------------------------------------------------------------------- migration v3 → v4

def test_a_mixed_row_is_split_and_codex_agents_keep_access(tmp_path):
    root = _realm(tmp_path, [DOCS, APP], {
        "on_codex": {"model": "gpt-6.1-sol", "toolkit": {"connectors": [{"id": DOCS["id"]}]}},
        "on_claude": {"model": "claude-opus-5-5", "toolkit": {"connectors": [{"id": DOCS["id"]}]}}})
    assert realmformat.migrate(root)["changed"]
    rows = {c["id"]: c for c in util.read_json_state(root / "realm.json")["toolkit"]["connectors"]}
    assert "codex" not in rows[DOCS["id"]]["provider_bindings"]
    new = rows["google-drive-chatgpt-app"]
    assert new["name"] == "Google Drive · Codex" and new["reach"] == "codex"
    assert new["provider_bindings"] == {"codex": {"app_id": DOCS["provider_bindings"]["codex"]["app_id"]}}
    assert rows["gmail-app"] == APP                             # app-only rows are already one service
    grants = lambda a: [g["id"] for g in util.read_json_state(root / "agents" / a / "agent.json")["toolkit"]["connectors"]]
    assert grants("on_codex") == [DOCS["id"], "google-drive-chatgpt-app"]
    assert grants("on_claude") == [DOCS["id"]]
    before = (root / "realm.json").read_bytes()
    assert not realmformat.migrate(root)["changed"]
    assert (root / "realm.json").read_bytes() == before


def test_the_migration_is_a_no_op_for_a_realm_without_mixed_rows(tmp_path):
    root = _realm(tmp_path, [OPEN, APP], {})
    realmformat.migrate(root)
    tk = util.read_json_state(root / "realm.json")["toolkit"]["connectors"]
    assert tk == [OPEN, APP]


# --------------------------------------------------------------------------- routes

class _H(CapabilityRoutes):
    def __init__(self, realm, path=""):
        self.realm, self.path, self.sent = realm, path, None

    def _json(self, code, body):
        self.sent = body


def test_move_previews_who_gains_and_loses_then_saves(tmp_path):
    root = _realm(tmp_path, [IBKR], {
        "pacioli": {"model": "claude-haiku-4-5", "display": "Pacioli", "toolkit": {"connectors": [{"id": IBKR["id"]}]}},
        "marcus": {"model": "gpt-6.1-sol", "display": "Marcus", "toolkit": {"connectors": [{"id": IBKR["id"]}]}}})
    h = _H(root)
    p = h._capability_move({"capability": IBKR["id"], "engine": "codex", "preview": True})
    assert p["ok"] and p["preview"] and p["from"] == "claude" and p["to"] == "codex"
    assert [a["name"] for a in p["loses"]] == ["Pacioli"] and [a["name"] for a in p["gains"]] == ["Marcus"]
    assert "exclusive_engine" not in json.dumps(util.read_json_state(root / "realm.json"))
    assert h._capability_move({"capability": IBKR["id"], "engine": "codex"})["ok"]
    cap = capabilities.find(root, IBKR["id"])[1]
    assert cap["exclusive_engine"] == "codex" and capreach.reach("connectors", cap).engine == "codex"


def test_move_refuses_what_cannot_move(tmp_path):
    root = _realm(tmp_path, [OPEN, APP], {})
    h = _H(root)
    assert not h._capability_move({"capability": "notion", "engine": "codex"})["ok"]
    assert not h._capability_move({"capability": "gmail-app", "engine": "claude"})["ok"]
    assert not h._capability_move({"capability": "notion", "engine": "nope"})["ok"]


def test_owner_can_mark_one_engine_at_a_time(tmp_path):
    root = _realm(tmp_path, [OPEN], {})
    assert _H(root)._capability_exclusive({"capability": "notion", "exclusive": True})["ok"]
    assert capreach.reach("connectors", capabilities.find(root, "notion")[1]).exclusive
    assert _H(root)._capability_exclusive({"capability": "notion", "exclusive": None})["ok"]
    assert "exclusive" not in capabilities.find(root, "notion")[1]


def test_engine_impact_endpoint_follows_the_chosen_model(tmp_path):
    root = _realm(tmp_path, [IBKR], {
        "warren": {"model": "claude-opus-5-5", "display": "Warren", "toolkit": {"connectors": [{"id": IBKR["id"]}]}}})
    h = _H(root, "/api/engine-impact?agent=warren&model=gpt-6.1-sol")
    h._get_engine_impact()
    assert h.sent["ok"] and h.sent["engine"] == "codex" and h.sent["lost"][0]["id"] == IBKR["id"]
    h = _H(root, "/api/engine-impact?agent=warren&model=")
    h._get_engine_impact()
    assert h.sent["engine"] == "claude" and h.sent["lost"] == []


# --------------------------------------------------------------------------- adding provider services

def test_a_provider_service_is_added_for_one_engine(tmp_path):
    root = _realm(tmp_path, [], {})
    with pytest.raises(ValueError, match="Choose which engine"):
        registry.save(root, service="gmail")
    cid = registry.save(root, service="gmail", engine="claude", account_label="Work")["capability"]
    cap = capabilities.find(root, cid)[1]
    assert cap["name"] == "Gmail · Claude · Work" and cap["reach"] == "claude"
    assert capreach.reach("connectors", cap).scope == "claude"
    # An open server stays one row for every engine.
    nid = registry.save(root, service="notion")["capability"]
    assert capreach.reach("connectors", capabilities.find(root, nid)[1]).scope == "any"


def test_a_codex_provider_service_binds_the_chatgpt_app_on_connect(tmp_path, monkeypatch):
    from armada import codex_apps
    monkeypatch.setattr(codex_apps, "service", lambda s, cwd=None: {"app_id": "connector_abc", "name": "Gmail"})
    root = _realm(tmp_path, [], {})
    cid = registry.save(root, service="gmail", engine="codex")["capability"]
    cap = capabilities.find(root, cid)[1]
    assert cap["name"] == "Gmail · Codex" and cap["reach"] == "codex"
    assert cap["provider_bindings"] == {}                   # no provider call when adding
    registry.save(root, capability=cid, service="gmail")    # what Connect on its Codex row does
    cap = capabilities.find(root, cid)[1]
    assert cap["provider_bindings"] == {"codex": {"app_id": "connector_abc"}}
    assert capreach.reach("connectors", cap).scope == "codex"
    # …and a Claude registration can't be linked onto the app's row.
    monkeypatch.setattr(registry, "inventory", lambda *a: [{"server_name": "claude.ai Gmail", "endpoint": ""}])
    with pytest.raises(ValueError, match="works only with Codex"):
        registry.save(root, provider="claude", server_name="claude.ai Gmail", capability=cid)


# --------------------------------------------------------------------------- page

def _realm_obj(root, agents):
    members = [SimpleNamespace(id=a, display=a.title(), is_coordinator=False, theme_role="") for a in agents]
    return SimpleNamespace(agents=members, members=members, coordinator=None, theme_coordinator="Coordinator")


def test_capabilities_page_is_sectioned_by_reach(tmp_path):
    from armada.webui.capabilities import _reach_sections
    root = _realm(tmp_path, [IBKR, OPEN, APP], {
        "pacioli": {"model": "gpt-6.1-sol", "toolkit": {"connectors": [{"id": IBKR["id"]}]}}})
    tk = {"connectors": capabilities.catalogue(root)["connectors"], "extensions": [], "skills": [], "plugins": []}
    html = _reach_sections(_realm_obj(root, ["pacioli"]), root, tk)
    assert 'data-reach-sec="any"' in html and 'data-reach-sec="codex"' in html
    assert html.index('data-reach-sec="any"') < html.index('data-reach-sec="codex"')
    assert 'class="mc-reach-switch"' in html and "Add a connector" not in html
    assert "One engine at a time · on Claude" in html and "Codex only" in html
    assert "can't use it" in html                           # Pacioli is on Codex; IBKR is held on Claude
    assert "Move to Codex" in html and "Move to Gemini" in html


def test_the_model_picker_hint_says_what_the_agent_keeps(tmp_path):
    from armada.webui.capabilities import _reach_hint
    root = _realm(tmp_path, [IBKR], {
        "warren": {"model": "gpt-6.1-sol", "display": "Warren", "toolkit": {"connectors": [{"id": IBKR["id"]}]}}})
    html = _reach_hint(root, "warren", "c-model")
    assert 'data-reach-for="c-model"' in html and 'data-state="loses"' in html
    assert "On Codex, Warren can&#x27;t use Interactive Brokers (IBKR)." in html
    assert "reachhint.js" in html


def test_reach_switcher_and_model_hint_scripts():
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        pytest.skip("Node required")
    root = Path(__file__).resolve().parents[1]
    subprocess.run([node, str(root / "tests/capreach_harness.js"),
                    str(root / "armada/webui/static/js/capreach.js"),
                    str(root / "armada/webui/static/js/reachhint.js")], check=True)


def test_catalogue_results_can_be_narrowed_to_what_an_engine_can_use(monkeypatch, tmp_path):
    from armada import catalogue as cat
    from armada.webui import catalogue as page
    entries = [
        {"key": "marketplace:x/plugins/p", "id": "p", "name": "A plugin", "kind": "plugins",
         "source": "marketplace:claude-plugins-official", "install": {}},
        {"key": "anthropic-skills/skills/s", "id": "s", "name": "A skill", "kind": "skills",
         "source": "anthropic-skills", "install": {}},
    ]
    monkeypatch.setattr(cat, "load", lambda: {"entries": entries, "source_labels": {}})
    monkeypatch.setattr(cat, "search_registry", lambda q, sample=False: ([], ""))
    monkeypatch.setattr(page, "_cat_installed", lambda *a, **k: {})
    realm = SimpleNamespace(agents=[], members=[])
    allr = page._cat_results(realm, tmp_path)
    assert "A plugin" in allr and "A skill" in allr and "Claude only" in allr and "Any engine" in allr
    codex = page._cat_results(realm, tmp_path, reach="codex")
    assert "A skill" in codex and "A plugin" not in codex
    every = page._cat_results(realm, tmp_path, reach="any")
    assert "A skill" in every and "A plugin" not in every


# --------------------------------------------------------------------------- 0.99.101: adding

def test_a_service_is_added_once_per_engine_and_an_address_once(tmp_path):
    root = _realm(tmp_path, [], {})
    registry.save(root, service="gmail", engine="claude")
    with pytest.raises(ValueError, match="already in this realm for Claude"):
        registry.save(root, service="gmail", engine="claude")
    registry.save(root, service="gmail", engine="codex")          # Codex's version is another row
    assert registry.added_for(root)["gmail"] == {"claude", "codex"}
    registry.save(root, name="Linear", url="https://mcp.linear.app/mcp")
    with pytest.raises(ValueError, match="already uses this address"):
        registry.save(root, name="Linear again", url="https://mcp.linear.app/mcp")


def test_a_claude_import_counts_as_the_service_added_for_claude(tmp_path):
    root = _realm(tmp_path, [{"id": "claude.ai Gmail", "name": "claude.ai Gmail", "command": "https://gmail.mcp.claude.com/mcp"}], {})
    assert registry.added_for(root)["gmail"] == {"claude"}
    with pytest.raises(ValueError, match="already in this realm for Claude"):
        registry.save(root, service="gmail", engine="claude")


def test_add_a_capability_lists_engine_connectors_with_one_add_per_engine(tmp_path, monkeypatch):
    from armada import catalogue as cat
    from armada.catalogue import sources
    from armada.webui import catalogue as ui
    monkeypatch.setattr(sources, "search_registry", lambda q, sample=False: ([], ""))
    monkeypatch.setattr(cat, "search_registry", lambda q, sample=False: ([], ""))
    monkeypatch.setattr(cat, "load", lambda: {"entries": []})
    root = _realm(tmp_path, [], {})
    registry.save(root, service="gmail", engine="claude")
    html = ui._cat_results(_realm_obj(root, []), root, q="mail")
    assert 'data-service="gmail"' in html and "Added for Claude" in html
    assert "mcCatAddService(this,&quot;gmail&quot;,&quot;codex&quot;)" in html or "Add for Codex" in html
    assert "Gemini: not available" in html
    assert 'data-service="gmail"' not in ui._cat_results(_realm_obj(root, []), root, q="mail", reach="any")
    assert 'data-service="gmail"' in ui._cat_results(_realm_obj(root, []), root, q="mail", reach="codex")
