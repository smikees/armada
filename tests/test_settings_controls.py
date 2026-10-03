"""Regressions in the embedded new-realm flow and unsaved appearance previews."""
from pathlib import Path
import shutil
import subprocess

import pytest

from armada import appconfig, reader, serve, util
from armada.webui import pages, provider_settings


@pytest.fixture
def realm(tmp_path):
    util.write_json_atomic(tmp_path / "realm.json", {"name": "Test"})
    return reader.read(tmp_path)


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is needed for browser script checks")
@pytest.mark.parametrize("control", ["newrealm", "appearance"])
def test_browser_controls_run_with_the_rendered_dependencies(realm, control):
    html = pages.render_new_realm(realm, embed=True) if control == "newrealm" else pages.render_settings(
        realm, realm.root, False, "", [])
    result = subprocess.run(["node", str(Path(__file__).with_name("settings_controls_harness.js")), control],
        input=html, capture_output=True, text=True, encoding="utf-8", timeout=15)
    assert result.returncode == 0, result.stderr


def test_saved_colour_mode_persists_and_invalid_values_preserve_it():
    handler = object.__new__(serve.Handler)
    assert handler._save_appearance({"mode": "dark"})["ok"]
    assert appconfig.get("appearance") == "dark"
    assert not handler._save_appearance({"mode": "invalid"})["ok"]
    assert appconfig.get("appearance") == "dark"
    assert handler._save_appearance({"mode": "light"})["ok"]
    assert appconfig.get("appearance") == "light"


def test_provider_grid_is_used_in_app_settings_only():
    assert 'class="mc-provider-grid"' in provider_settings.connections()
    assert 'class="mc-provider-grid"' not in provider_settings.connections(setup=True)


def test_subscription_line_is_below_provider_heading_in_settings():
    html = provider_settings.connections()
    for provider in ('claude', 'codex'):
        card = html.split(f'data-connection="{provider}"', 1)[1].split('mc-provider-login-url', 1)[0]
        assert card.index('</strong>') < card.index(f'id="provider-{provider}-plan"') < card.index(f'id="provider-{provider}-status"')
    assert 'data-plan-prefix="ChatGPT"' in html


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is needed for browser script checks")
def test_subscription_names_and_visibility_follow_live_connection():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(['node', str(Path(__file__).with_name('provider_plans_harness.js')),
                             str(root / 'armada/webui/static/js/providers.js')],
                            capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is needed for browser script checks")
def test_settings_menus_keep_values_events_and_provider_updates():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(['node', str(Path(__file__).with_name('settings_dropdowns_harness.js')),
                             str(root / 'armada/webui/static/js/fdrop.js')],
                            capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('linked', [True, False])
def test_telegram_connection_details_share_the_heading(monkeypatch, linked):
    from armada import telegram
    monkeypatch.setattr(telegram, 'status', lambda: {
        'linked': linked, 'configured': linked, 'chat_name': 'Test user', 'bot': 'TestBot', 'source': 'ARMADA', 'env_file': ''})
    html = pages._telegram_box()
    heading = html.split('class="mc-telegram-head"', 1)[1].split('Message your agents', 1)[0]
    assert '<strong>Telegram</strong>' in heading and 'mc-telegram-details' in heading
    assert ('@TestBot' if linked else 'Not connected') in heading
    if linked:
        assert html.index('@TestBot') < html.index('Message your agents') < html.index('Send a test message')
