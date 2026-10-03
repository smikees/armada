"""First run (launch plan 5.3): with no realm to open, the app shows a welcome page instead of
exiting with a sentence nobody sees (pythonw has no console).

Drives a real server started with no realm, because the thing under test is the server's
behaviour in that mode: which routes answer, what every other route does, and the hand-over into
the normal app once a realm exists.
"""
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from golden_support import ServedRealm
from armada import schedsvc, serve


@pytest.fixture
def srv(monkeypatch):
    started = []
    monkeypatch.setattr(schedsvc, "ensure_running", lambda root: started.append(root) or {"ok": True})
    with ServedRealm("") as s:
        s.scheduler_started = started
        yield s
    serve.Handler.realm = "."
    serve.Handler.welcome_note = ""


def _status(srv, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(srv.base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def test_every_page_is_the_setup_wizard(srv):
    for path in ("/", "/settings", "/jobs", "/agent/pm"):
        html = srv.get(path)
        assert "Welcome to ARMADA" in html and "ARMADA’s folder" in html, path
        for step in ("welcome", "checks", "home", "team"):
            assert f'class="mc-su-pane" data-step="{step}"' in html, (path, step)
        assert all(f'data-connection="{provider}"' in html for provider in ('claude', 'codex', 'gemini'))
        assert 'Install Antigravity CLI' in html
        assert "mcConnection" in html and "provider’s website" in html


def test_static_assets_still_load(srv):
    code, body = _status(srv, "GET", "/static/js/setup.js")
    assert code == 200 and "mcSuAppoint" in body
    with urllib.request.urlopen(srv.base + "/static/alexander.png", timeout=10) as r:
        assert r.status == 200 and r.read(4) == b"\x89PNG"


def test_other_api_calls_are_refused_not_crashed(srv):
    assert _status(srv, "GET", "/api/realms")[0] == 409
    code, body = _status(srv, "POST", "/api/save-user", {"name": "x"})
    assert code == 409 and json.loads(body)["ok"] is False


def test_create_needs_the_folder_first(srv):
    r = srv.post("/api/first-realm", {"name": "Home"})
    assert r["ok"] is False and "folder first" in r["error"]


def test_wizard_requires_a_connected_provider_before_creating_files(srv, tmp_path, monkeypatch):
    from armada import providers
    monkeypatch.setattr(providers, "statuses", lambda **kw: {
        "claude": {"connected": False}, "codex": {"connected": False}})
    root = tmp_path / "ARMADA"
    srv.post("/api/set-approot", {"root": str(root), "create": True})
    result = srv.post("/api/first-realm", {"name": "Home", "owner": "Alex", "wizard": True, "check_providers": True})
    assert not result["ok"] and "Connect a provider" in result["error"]
    assert not (root / "Home").exists()


@pytest.mark.parametrize('provider,model', [('codex', 'gpt-6-sol'), ('gemini', 'gemini:auto')])
def test_wizard_rechecks_preflight_after_applying_provider_defaults(srv, tmp_path, monkeypatch, provider, model):
    from armada import providers, preflight
    monkeypatch.setattr(providers, "statuses", lambda **kw: {
        p: {"connected": p == provider} for p in ('claude', 'codex', 'gemini')})
    checked = []
    def check(root):
        cfg = json.loads((Path(root) / "realm.json").read_text())
        checked.append(cfg.get("default_model"))
        return {"ok": cfg.get("default_model") == model, "checks": []}
    monkeypatch.setattr(preflight, "apply_hold", check)
    srv.post("/api/set-approot", {"root": str(tmp_path / "ARMADA"), "create": True})
    result = srv.post("/api/first-realm", {"name": "Home", "owner": "Alex", "wizard": True, "check_providers": True})
    assert result["ok"] and result["preflight"]["ok"]
    assert len(checked) == 2 and checked[-1] == model


def test_the_suggested_folder_is_created_but_not_a_whole_tree(srv, tmp_path):
    r = srv.post("/api/set-approot", {"root": str(tmp_path / "ARMADA"), "create": True})
    assert r["ok"] and (tmp_path / "ARMADA").is_dir()
    r = srv.post("/api/set-approot", {"root": str(tmp_path / "no" / "such" / "place"), "create": True})
    assert r["ok"] is False and not (tmp_path / "no").exists()


def test_first_realm_lands_in_the_root_named_after_itself(srv, tmp_path):
    root = tmp_path / "ARMADA"
    srv.post("/api/set-approot", {"root": str(root), "create": True})
    r = srv.post("/api/first-realm", {"name": "  My   Team ", "template": "scratch"})
    assert r["ok"], r
    assert Path(r["path"]) == (root / "My Team").resolve() and (root / "My Team" / "realm.json").exists()
    r2 = srv.post("/api/first-realm", {"name": "My Team"})
    assert Path(r2["path"]).name == "My Team 2"          # never over an existing folder
    r3 = srv.post("/api/first-realm", {"name": 'a/b:c?'})
    assert Path(r3["path"]).name == "abc"                # no path tricks through the name
    assert srv.post("/api/first-realm", {"name": "///"})["ok"] is False


def test_switching_into_the_new_realm_leaves_welcome_mode(srv, tmp_path):
    srv.post("/api/set-approot", {"root": str(tmp_path / "ARMADA"), "create": True})
    r = srv.post("/api/first-realm", {"name": "Work"})
    srv.get("/switch?path=" + urllib.request.quote(r["path"], safe=""))
    html = srv.get("/")
    assert "Welcome to ARMADA" not in html and 'id="mc-schedbar"' in html
    assert srv.scheduler_started == [r["path"]]          # the launch-time start had nothing to start for


def test_known_realms_are_offered_when_none_was_remembered(srv, tmp_path):
    from armada.routes._shared import _reg_ensure
    srv.post("/api/set-approot", {"root": str(tmp_path / "ARMADA"), "create": True})
    a = srv.post("/api/first-realm", {"name": "Alpha"})["path"]
    _reg_ensure(a, "Alpha")
    html = srv.get("/")
    assert "Pick up where you left off" in html and "Alpha" in html and "/switch?path=" in html


def test_cli_opens_the_welcome_page_instead_of_exiting(monkeypatch, tmp_path):
    from armada import cli
    calls = []
    monkeypatch.setattr(serve, "serve", lambda realm, port: calls.append(realm))
    monkeypatch.setenv("HOME", str(tmp_path)); monkeypatch.setenv("USERPROFILE", str(tmp_path))
    try:
        assert cli.main(["serve", str(tmp_path / "gone")]) == 0
        assert calls == [""]
        assert "isn't a realm folder" in serve.Handler.welcome_note
    finally:
        serve.Handler.welcome_note = ""


# ---- the setup wizard's second half (6.4) --------------------------------------------------------

def _wizard_realm(srv, tmp_path, **extra):
    srv.post("/api/set-approot", {"root": str(tmp_path / "ARMADA"), "create": True})
    r = srv.post("/api/first-realm", {"name": "Home", "template": "company", "owner": "Mihai",
                                      "wizard": True, **extra})
    assert r["ok"], r
    srv.get("/switch?path=" + urllib.request.quote(r["path"], safe=""))
    srv.realm = r["path"]
    return Path(r["path"])


def test_a_wizard_realm_resumes_setup_until_it_is_finished(srv, tmp_path):
    root = _wizard_realm(srv, tmp_path)
    cfg = json.loads((root / "realm.json").read_text("utf-8"))
    assert cfg["setup"]["step"] == "capabilities" and cfg["user"]["name"] == "Mihai"
    html = srv.get("/")                                   # redirected to /setup
    assert 'data-step="capabilities"' in html and "Add and continue" in html and "Low risk" in html
    assert srv.post("/api/setup-step", {"step": "tour"})["ok"]
    assert json.loads((root / "realm.json").read_text("utf-8"))["setup"]["step"] == "tour"
    assert srv.post("/api/setup-step", {"step": "nowhere"})["ok"] is False
    assert srv.post("/api/setup-finish", {})["ok"]
    assert "setup" in json.loads((root / "realm.json").read_text("utf-8"))
    assert 'id="mc-schedbar"' in srv.get("/")             # the normal app from now on
    assert not srv.post("/api/setup-step", {"step": "home"})["ok"]
    assert 'id="mc-schedbar"' in srv.get("/setup")        # stale wizard URL returns to the app
    assert json.loads((root / "realm.json").read_text("utf-8"))["setup"].get("step") is None


def test_the_wizard_builds_the_team_on_the_server(srv, tmp_path):
    root = _wizard_realm(srv, tmp_path, keep=["cfo"], extra=[{"display": "Ada Lovelace", "role": "Engines"},
                                                           {"display": "<script>", "role": ""}])
    ids = sorted(p.name for p in (root / "agents").iterdir())
    assert ids == ["cfo", "custom-0-ada-lovelace", "custom-1-script"]
    coords = [json.loads((root / "agents" / i / "agent.json").read_text("utf-8"))["coordinator"] for i in ids]
    assert coords.count(True) == 1                          # someone always leads
    mandate = (root / "agents" / "cfo" / "mandate.md").read_text("utf-8")
    assert len(mandate) > 40                                # the template's instructions, not the page's


def test_only_recommended_capabilities_go_through_the_wizard(srv, tmp_path):
    _wizard_realm(srv, tmp_path)
    r = srv.post("/api/setup-capability", {"key": "marketplace:claude-plugins-official/desktop-commander"})
    assert r["ok"] is False and "recommended" in r["error"]


def test_an_empty_team_is_refused(srv, tmp_path):
    srv.post("/api/set-approot", {"root": str(tmp_path / "ARMADA"), "create": True})
    r = srv.post("/api/first-realm", {"name": "Empty", "template": "scratch", "keep": [], "extra": [], "owner": "Alex", "wizard": True})
    assert r["ok"] is False and "at least one" in r["error"]


def test_wizard_requires_owner_before_any_realm_write(srv, tmp_path):
    root = tmp_path / 'ARMADA'
    srv.post('/api/set-approot', {'root': str(root), 'create': True})
    result = srv.post('/api/first-realm', {'name': 'Home', 'owner': '  ', 'wizard': True})
    assert not result['ok'] and 'your name' in result['error']
    assert not (root / 'Home').exists()


def test_state_roster_copies_full_personalized_profiles_and_avatars(srv, tmp_path):
    root = _wizard_realm(srv, tmp_path, template='state', owner='Zoë', keep=['hand', 'education'], extra=[])
    for aid in ('hand', 'education'):
        folder = root / 'agents' / aid
        mandate = (folder / 'mandate.md').read_text(encoding='utf-8')
        assert 'Zoë' in mandate and 'Mihai' not in mandate and '{owner}' not in mandate
        assert len((folder / 'soul.md').read_text(encoding='utf-8')) > 1000
        assert len((folder / 'tenets.md').read_text(encoding='utf-8')) > 100
        assert (folder / 'avatar.png').read_bytes().startswith(b'\x89PNG')
        assert json.loads((folder / 'agent.json').read_text(encoding='utf-8'))['model'] is None


def test_scaffolding_succeeds_with_cp1252_stdout_and_unicode_names(monkeypatch, tmp_path):
    import io, sys
    from armada.setup import scaffold
    output = io.TextIOWrapper(io.BytesIO(), encoding='cp1252', errors='strict')
    monkeypatch.setattr(sys, 'stdout', output)
    root = scaffold(tmp_path / 'realm', 'scratch', '東京 → Zoë')
    assert json.loads((root / 'realm.json').read_text(encoding='utf-8'))['name'] == '東京 → Zoë'


def test_custom_unicode_profile_is_preserved_without_path_or_tool_injection(srv, tmp_path):
    root = _wizard_realm(srv, tmp_path, template='scratch', keep=[], extra=[{
        'display': '李明', 'role': 'Research', 'mandate': 'Help Zoë.', 'voice': 'Calm',
        'tenets': 'Verify sources.', 'avatar': '../../secret.png', 'autonomy': 'full',
        'skills': [{'id': 'untrusted'}]}])
    folder = root / 'agents' / 'custom-0-agent'
    agent = json.loads((folder / 'agent.json').read_text(encoding='utf-8'))
    assert agent['display'] == '李明' and agent['autonomy'] == 'propose'
    assert (folder / 'soul.md').read_text(encoding='utf-8').strip() == 'Calm'
    assert json.loads((folder / 'skills.json').read_text()) == []

def test_splash_is_unlisted_and_alexander_welcome_is_step_one(srv):
    import re
    html = srv.get('/')
    assert 'data-step="intro" hidden' in html and 'Start setup' in html
    steps = re.findall(r'class="mc-su-rstep [^"]*" data-step="([^"]+)"', html)
    assert len(steps) == 9 and steps[:5] == ['welcome', 'checks', 'home', 'naming', 'team'] and 'intro' not in steps
    assert "I&#x27;m Alexander" in html
    assert 'class="mc-su-team-heading"' in html
    assert 'id="su-owner"' in html and 'id="su-naming-next"' in html
    assert 'onclick="mcSuNaming()"' in html


def test_starter_rosters_have_full_profiles_and_reference_links():
    from armada.starter_profiles import roster

    state = roster('state')
    assert [(a['id'], a['display']) for a in state if a['id'] in ('finance', 'strategy')] == [
        ('finance', 'Benjamin'), ('strategy', 'David')]
    assert next(a for a in state if a['id'] == 'finance')['avatar'] == 'state-finance.png'
    assert next(a for a in state if a['id'] == 'strategy')['avatar'] == 'state-strategy.png'
    development = next(a for a in state if a['id'] == 'development')
    assert (development['display'], development['avatar']) == ('Josiah', 'state-development.png')
    assert (Path(__file__).resolve().parents[1] / 'armada/webui/static/avatars' / development['avatar']).read_bytes().startswith(b'\x89PNG')
    assert [a['id'] for a in roster('company')] == ['ceo', 'cfo', 'cmo', 'cpo']
    assert [a['id'] for a in roster('crew')] == ['captain', 'navigator', 'quartermaster']
    for agent in state + roster('company') + roster('crew'):
        assert agent['wikipedia'].startswith('https://en.wikipedia.org/wiki/')
        assert all(len(agent[field].split()) >= 190 for field in ('mandate', 'voice', 'tenets'))
        assert '{owner}' in agent['mandate']


def test_setup_connections_persist_under_user_but_never_claim_authenticated(srv, tmp_path, monkeypatch):
    from armada import catalogue, capabilities
    from armada.webui.capabilities import _cap_card
    monkeypatch.setattr(catalogue.realm, 'find', lambda key: None)
    root = _wizard_realm(srv, tmp_path)
    for key in ('workspace-mcp/connectors/google-workspace', 'cursortouch/extensions/windows-mcp'):
        result = srv.post('/api/setup-capability', {'key': key})
        assert result['ok'] and result['pending_setup']
        assert srv.post('/api/setup-capability', {'key': key})['ok']  # retry is idempotent
    items = [it for _, it in capabilities.catalogue_flat(root)]
    for cid, publisher, kind in [('google-workspace', 'Taylor Wilsdon', 'connectors'), ('windows-mcp', 'CursorTouch', 'extensions')]:
        matches = [it for it in items if it['id'] == cid]
        assert len(matches) == 1
        it = matches[0]
        assert it['enabled'] is False and it['status'] != 'connected'
        html = _cap_card(it, kind=kind)
        assert 'Setup guide' in html and publisher in html and '(community)' in html
        assert 'High risk' in html  # both execute local code; Windows also exposes a shell


def test_setup_skills_are_downloaded_enabled_and_visible_in_user(srv, tmp_path, monkeypatch):
    from armada import catalogue, capabilities
    root = _wizard_realm(srv, tmp_path)
    monkeypatch.setattr(catalogue.realm, 'find', lambda key: None)
    def fetch(entry, dest):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / 'SKILL.md').write_text('# Write documents', encoding='utf-8')
        return {'ok': True}
    monkeypatch.setattr(catalogue.realm, 'fetch_skill', fetch)
    assert srv.post('/api/setup-capability', {'key': 'anthropic-skills/skills/docx'})['ok']
    item = next(it for _, it in capabilities.catalogue_flat(root) if it['id'] == 'docx')
    assert item['enabled'] and item['made_by'] == 'Anthropic'
    assert (root / 'skills/docx/SKILL.md').is_file()
    html = srv.get('/setup')
    assert 'mc-toolrow' in html and 'Anthropic skills' in html
    assert 'mcSkillView(' not in html  # previews never link to unavailable content controls


def test_invalid_draft_avatar_is_rejected_before_realm_creation(srv, tmp_path):
    folder = tmp_path / 'ARMADA'
    srv.post('/api/set-approot', {'root': str(folder), 'create': True})
    result = srv.post('/api/first-realm', {'name': 'Bad portrait', 'owner': 'Alex', 'wizard': True,
        'template': 'scratch', 'keep': [], 'extra': [{'display': 'Ada', 'avatar_data': 'data:image/svg+xml;base64,AA=='}]})
    assert not result['ok'] and not (folder / 'Bad portrait').exists()


def test_setup_adds_disabled_skills_and_can_change_initial_state(srv, tmp_path, monkeypatch):
    from armada import catalogue, capabilities
    root = _wizard_realm(srv, tmp_path)
    monkeypatch.setattr(catalogue.realm, 'find', lambda key: None)
    def fetch(entry, dest):
        dest.mkdir(parents=True, exist_ok=True)
        (dest / 'SKILL.md').write_text('# Skill', encoding='utf-8')
        return {'ok': True}
    monkeypatch.setattr(catalogue.realm, 'fetch_skill', fetch)
    key = 'anthropic-skills/skills/docx'
    for enabled in (False, True, False):
        assert srv.post('/api/setup-capability', {'key': key, 'enabled': enabled})['ok']
        items = [it for _, it in capabilities.catalogue_flat(root) if it['id'] == 'docx']
        assert len(items) == 1 and items[0]['enabled'] is enabled
        assert (root / 'skills/docx/SKILL.md').is_file()
    assert not srv.post('/api/setup-capability', {'key': key, 'enabled': 'false'})['ok']


def test_setup_connector_enable_choice_does_not_claim_authentication(srv, tmp_path, monkeypatch):
    from armada import catalogue, capabilities
    root = _wizard_realm(srv, tmp_path)
    monkeypatch.setattr(catalogue.realm, 'find', lambda key: None)
    key = 'workspace-mcp/connectors/google-workspace'
    result = srv.post('/api/setup-capability', {'key': key, 'enabled': True})
    assert result['ok'] and result['pending_setup']
    item = next(it for _, it in capabilities.catalogue_flat(root) if it['id'] == 'google-workspace')
    assert item['enabled'] is True and item['status'] == 'planned'


def test_custom_portrait_and_prime_minister_survive_scaffolding(srv, tmp_path):
    import base64
    import struct, zlib
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    avatar = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 256, 256, 8, 2, 0, 0, 0))
              + chunk(b'IDAT', zlib.compress((b'\x00' + b'\x88' * 768) * 256)) + chunk(b'IEND', b''))
    data = 'data:image/png;base64,' + base64.b64encode(avatar).decode()
    root = _wizard_realm(srv, tmp_path, template='state', keep=['hand'], extra=[{'display':'Ada','avatar_data':data}])
    assert (root / 'agents/custom-0-ada/avatar.png').read_bytes() == avatar
    marcus = json.loads((root / 'agents/hand/agent.json').read_text(encoding='utf-8'))
    assert marcus['role'] == 'Prime Minister'


def test_back_navigation_resumes_saved_realm_without_recreating_it(srv, tmp_path):
    from armada import setupflow
    from armada.alexander.wizard_script import STEPS
    from html.parser import HTMLParser

    class Panes(HTMLParser):
        def __init__(self):
            super().__init__()
            self.current = None
            self.back = {}
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if attrs.get('class') == 'mc-su-pane':
                self.current = attrs['data-step']
            if tag == 'button' and attrs.get('class') == 'btn btn-secondary':
                self.back.setdefault(self.current, []).append(attrs.get('onclick'))

    root = _wizard_realm(srv, tmp_path, owner='Alex', keep=['cfo'], extra=[])
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*')
              if p.is_file() and p.name != 'realm.json'}
    steps = ['intro'] + [sid for sid, _ in STEPS]
    for step in reversed(steps):
        assert srv.post('/api/setup-step', {'step': step})['ok']
        assert setupflow.current_step(root) == step
        html = srv.get('/setup')
        assert '"first": "' + step + '"' in html
    panes = Panes()
    panes.feed(html)
    for index, step in enumerate(steps[1:], 1):
        assert f"mcSuGo('{steps[index - 1]}')" in panes.back[step]
    assert '"savedTeam":' in html
    assert 'id="su-appoint"' in html
    assert 'mcSuHome(this)' in html
    assert srv.post('/api/setup-step', {'step': 'capabilities'})['ok']
    assert list(root.parent.glob('*/realm.json')) == [root / 'realm.json']
    assert before == {p.relative_to(root): p.read_bytes() for p in root.rglob('*')
                      if p.is_file() and p.name != 'realm.json'}


def test_editing_setup_preserves_work_and_custom_agent_identity(srv, tmp_path):
    from armada import setupteam, setupflow
    root = _wizard_realm(srv, tmp_path, template='state', owner='Alex', keep=['hand', 'education'],
                         extra=[{'display': 'Ada'}, {'display': 'Grace'}])
    hand = root / 'agents' / 'hand'
    (hand / 'threads').mkdir()
    (hand / 'threads' / 'first-brief.md').write_text('Existing conversation', encoding='utf-8')
    (hand / 'memory' / 'note.md').write_text('Remember this', encoding='utf-8')
    initial = json.loads((root / 'realm.json').read_text(encoding='utf-8'))
    initial['toolkit'] = {'skills': [{'id': 'pdf', 'enabled': True}]}
    (root / 'realm.json').write_text(json.dumps(initial), encoding='utf-8')
    selection = setupteam.draft(root)
    grace = next(a for a in selection['extra'] if a['display'] == 'Grace')
    selection.update(name='New name', owner='Taylor', keep=['hand', 'health'], extra=[grace])
    result = srv.post('/api/setup-team', selection)
    assert result['ok'], result
    cfg = json.loads((root / 'realm.json').read_text(encoding='utf-8'))
    assert cfg['name'] == 'New name' and cfg['user']['name'] == 'Taylor'
    assert cfg['toolkit'] == initial['toolkit']
    assert cfg['created'] == initial['created']
    assert (hand / 'threads' / 'first-brief.md').read_text() == 'Existing conversation'
    assert (hand / 'memory' / 'note.md').read_text() == 'Remember this'
    assert "so Taylor doesn't have to" in (hand / 'mandate.md').read_text(encoding='utf-8')
    assert (root / 'agents' / grace['saved_id']).is_dir()
    assert (root / 'retired' / 'education').is_dir()
    assert len(list(root.parent.glob('*/realm.json'))) == 1
    # Repeating the save and then restoring a starter profile keeps identities and history.
    assert srv.post('/api/setup-team', selection)['ok']
    selection['keep'].append('education')
    assert srv.post('/api/setup-team', selection)['ok']
    assert (root / 'agents' / 'education').is_dir()
    assert setupflow.current_step(root) == 'capabilities'
    assert srv.post('/api/setup-finish', {})['ok']
    assert not srv.post('/api/setup-team', selection)['ok']


def test_setup_team_rejects_active_turn_and_rolls_back_write_failure(srv, tmp_path, monkeypatch):
    from armada import execution, setupteam, util
    from armada.request_context import RunContext
    root = _wizard_realm(srv, tmp_path, keep=['ceo', 'cfo'], extra=[])
    selection = setupteam.draft(root)
    selection.update(name='Renamed', keep=['ceo', 'cmo'])
    with execution.RunSession(RunContext.capture(root, 'ceo')):
        result = srv.post('/api/setup-team', selection)
        assert not result['ok'] and 'current task' in result['error']
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*')
              if p.is_file() and p.suffix != '.lock'}
    write = util.write_text_atomic
    failed = []
    def fail_once(path, text, *args, **kwargs):
        if Path(path) == root / 'theme.json' and not failed:
            failed.append(True)
            raise OSError('Injected disk failure')
        return write(path, text, *args, **kwargs)
    monkeypatch.setattr(util, 'write_text_atomic', fail_once)
    assert not srv.post('/api/setup-team', selection)['ok']
    after = {p.relative_to(root): p.read_bytes() for p in root.rglob('*')
             if p.is_file() and p.suffix != '.lock'}
    assert before == after
    assert not list(root.glob('.setup-edit-*'))


def test_setup_folder_moves_existing_realm_and_remembers_destination(srv, tmp_path):
    from armada import activerealm, setupflow
    root = _wizard_realm(srv, tmp_path, keep=['ceo'], extra=[])
    work = root / 'agents' / 'ceo' / 'memory' / 'personal.md'
    work.write_text('Preserved memory', encoding='utf-8')
    destination = root.parent / 'Moved Realm'
    result = srv.post('/api/setup-folder', {'path': str(destination)})
    assert result['ok'], result
    assert not root.exists() and (destination / 'realm.json').exists()
    assert (destination / work.relative_to(root)).read_text() == 'Preserved memory'
    assert activerealm.remembered() == str(destination)
    assert setupflow.current_step(destination) == 'naming'
    assert str(destination) in srv.get('/setup')
    assert 'Moved Realm' in srv.get('/api/realms')
    assert not list(root.parent.glob('.armada-*'))


def test_setup_folder_same_path_advances_to_naming_and_other_realms_remain_visible(srv, tmp_path):
    from armada import setupflow
    from armada.routes._shared import _reg_ensure
    root = _wizard_realm(srv, tmp_path)
    _reg_ensure(tmp_path / 'ARMADA' / 'Existing', 'Existing')
    html = srv.get('/setup')
    assert 'Other realms on this computer' in html and 'Existing' in html
    assert srv.post('/api/setup-folder', {'path': str(root)})['ok']
    assert setupflow.current_step(root) == 'naming'
    assert (root / 'realm.json').exists()


def test_setup_folder_rejects_busy_nested_and_nonempty_targets(srv, tmp_path):
    from armada import execution
    from armada.request_context import RunContext
    root = _wizard_realm(srv, tmp_path)
    destination = root.parent / 'Occupied'
    destination.mkdir()
    (destination / 'keep.txt').write_text('Keep me')
    assert not srv.post('/api/setup-folder', {'path': str(destination)})['ok']
    assert not srv.post('/api/setup-folder', {'path': str(root / 'nested')})['ok']
    with execution.RunSession(RunContext.capture(root, 'ceo')):
        assert not srv.post('/api/setup-folder', {'path': str(root.parent / 'New')})['ok']
    assert (root / 'realm.json').exists()
    assert (destination / 'keep.txt').read_text() == 'Keep me'


def test_setup_folder_rolls_back_registry_and_files_if_preferences_fail(srv, tmp_path, monkeypatch):
    from armada import appconfig
    root = _wizard_realm(srv, tmp_path)
    original_config = appconfig.load()
    write = appconfig.save
    failed = []
    def fail_once(updates):
        if not failed:
            failed.append(True)
            raise OSError('Injected preferences failure')
        return write(updates)
    monkeypatch.setattr(appconfig, 'save', fail_once)
    destination = root.parent / 'New'
    result = srv.post('/api/setup-folder', {'path': str(destination)})
    assert not result['ok']
    assert (root / 'realm.json').exists() and not destination.exists()
    assert appconfig.load() == original_config
    assert not list(root.parent.glob('.armada-*'))


def test_custom_coordinator_overrides_starter_and_covenant_follows_realm_type(srv, tmp_path):
    from armada import setupteam, covenant
    root = _wizard_realm(srv, tmp_path, template='state', keep=['hand'], extra=[{'display':'Warren','coordinator':True}])
    configs = [json.loads(p.read_text(encoding='utf-8')) for p in root.glob('agents/*/agent.json')]
    assert [a['display'] for a in configs if a['coordinator']] == ['Warren']
    assert (root / 'tenets.md').read_text(encoding='utf-8') == covenant.starter('state')
    selection = setupteam.draft(root)
    selection.update(template='company', keep=['ceo'], extra=[])
    assert srv.post('/api/setup-team', selection)['ok']
    text = (root / 'tenets.md').read_text(encoding='utf-8')
    assert text.startswith('# The Memorandum') and 'your own department' in text
    for page in ('/memory', '/settings', '/ministers'):
        assert 'The Memorandum' in srv.get(page)
