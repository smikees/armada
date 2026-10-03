from pathlib import Path
import shutil
import subprocess

import pytest

from armada import icons, reader, util, providers
from armada.webui import capabilities, layout, pages, provider_settings


def test_custom_colour_memory():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node required')
    root = Path(__file__).resolve().parents[1]
    subprocess.run([node, str(root/'tests/custom_color_harness.js'), str(root/'armada/webui/static/js/agent_color.js')], check=True)


def test_setup_provider_authentication_states():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node required')
    root = Path(__file__).resolve().parents[1]
    subprocess.run([node, str(root/'tests/setup_provider_cards_harness.js'), str(root/'armada/webui/static/js/providers.js')], check=True)


def test_setup_cards_have_separate_statuses_and_original_logos(monkeypatch):
    monkeypatch.setattr(providers, 'connected', lambda: [])
    html = provider_settings.connections(setup=True)
    assert html.count('mc-su-provider-card') == 3
    assert html.count('CLI status:') == html.count('Authentication status:') == 3
    assert html.count('data-auth-pill="true"') == 3
    assert html.count('Subscription type:') == 3
    assert html.index('Authentication status:') < html.index('Subscription type:')
    assert html.count('mc-engine-logo is-connected') == 3
    assert '#D97757' in html and 'gemini-color.svg' in html and '#000' in html
    assert 'https://learn.chatgpt.com/docs/pricing' in html
    assert 'https://antigravity.google/pricing' in html


def test_logos_and_provider_system_metadata(monkeypatch):
    monkeypatch.setattr(providers, 'connected', lambda: ['codex', 'claude', 'gemini'])
    html = provider_settings.connections()
    assert html.count('mc-engine-logo is-connected') == 3
    assert '#000' in html and '#D97757' in html and 'gemini-color.svg' in html
    system = capabilities._system_panel()
    assert system.count('Model provider</span>') == 3
    assert system.count('mc-system-provider-version') == 3
    assert '>Model providers</div>' not in system
    assert 'providers.js' in system
    assert capabilities._SCOPE_ICON['hooks'] == 'hook' and icons._ICON_VB['hook'] == '0 0 16 16'


def test_settings_and_documentation_are_highlighted(tmp_path):
    util.write_json_atomic(tmp_path/'realm.json', {'name': 'Cabinet'})
    realm = reader.read(tmp_path)
    for active, url in [('Settings', '/settings'), ('Docs', '/docs')]:
        html = layout._nav(realm, active)
        assert f'href="{url}" title="'+('Settings' if active=='Settings' else 'Documentation')+'" class="mc-nav-action" aria-current="page"' in html
    docs = pages.render_docs(realm, tmp_path)
    assert 'title="Documentation" class="mc-nav-action" aria-current="page"' in docs
