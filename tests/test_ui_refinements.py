import threading
import time
import shutil
import subprocess
from pathlib import Path

from armada import capabilities, connector_runtime, providers, reader
from armada.webui import pages, realmpages
from armada.webui.capabilities import _cap_legend


def test_slow_connector_provider_does_not_block_other_states(tmp_path, monkeypatch):
    release = threading.Event()
    calls = []
    def status(provider, **kwargs):
        calls.append(provider)
        if provider == 'codex':
            release.wait(2)
        return {'connected': False, 'enabled': True}
    monkeypatch.setattr(providers, 'status', status)
    monkeypatch.setattr(capabilities, 'catalogue', lambda root: {'connectors': [{'id': 'ibkr'}]})
    try:
        first = connector_runtime.connection_snapshot(tmp_path)
        assert first['pending'] and first['providers']['codex'] == 'checking'
        assert first['providers']['claude'] == first['providers']['gemini'] == 'unavailable'
        second = connector_runtime.connection_snapshot(tmp_path)
        assert calls.count('codex') == 1, 'Polling must not spawn duplicate checks'
        assert second['pending']
        monkeypatch.setattr(connector_runtime, '_CHECK_DEADLINE', 0)
        expired = connector_runtime.connection_snapshot(tmp_path)
        assert not expired['pending'] and expired['providers']['codex'] == 'unknown'
        assert 'timed out' in expired['connectors']['ibkr']['errors']['codex']
    finally:
        release.set()


def test_connector_probe_exception_is_an_explained_terminal_state(tmp_path, monkeypatch):
    monkeypatch.setattr(providers, 'status', lambda *a, **kw: {'connected': True})
    monkeypatch.setattr(capabilities, 'catalogue', lambda root: {'connectors': [{'id': 'ibkr'}]})
    monkeypatch.setattr(connector_runtime, 'codex_live_inventory', lambda root: (_ for _ in ()).throw(RuntimeError('Startup lock busy')))
    monkeypatch.setattr(connector_runtime, 'claude_inventory', lambda: {})
    data = connector_runtime.connection_snapshot(tmp_path)
    # Checks are asynchronous: scheduler load may leave the first response pending.
    # Verify the terminal error, without assuming the worker completes in the initial join.
    deadline = time.monotonic() + 3
    while data['providers']['codex'] == 'checking' and time.monotonic() < deadline:
        time.sleep(.01)
        data = connector_runtime.connection_snapshot(tmp_path)
    assert data['providers']['codex'] == 'unknown'
    assert data['connectors']['ibkr']['errors']['codex'] == 'RuntimeError: Startup lock busy'


def test_limits_cache_and_background_refresh():
    import pytest
    node = shutil.which('node')
    if not node:
        pytest.skip('Node required')
    root = Path(__file__).resolve().parents[1]
    subprocess.run([node, str(root/'tests/limits_cache_harness.js'),
                    str(root/'armada/webui/static/js/usage.js')], check=True)


def test_connector_badges_settle_without_global_icon_helper():
    import pytest
    node = shutil.which('node')
    if not node:
        pytest.skip('Node required')
    root = Path(__file__).resolve().parents[1]
    subprocess.run([node, str(root/'tests/connector_badges_harness.js'),
                    str(root/'armada/webui/static/js/connmodal.js')], check=True)


def test_legend_defaults_open_and_remembers_last_state():
    html = _cap_legend()
    assert '<details class="mc-cap-legend" open>' in html
    assert 'localStorage.getItem(key)!=="false"' in html
    assert 'localStorage.setItem(key,String(legend.open))' in html


def test_appointment_uses_shared_dropdowns_on_both_surfaces(tmp_path):
    (tmp_path/'realm.json').write_text('{"name":"Test"}', encoding='utf-8')
    realm = reader.read(tmp_path)
    form = realmpages._new_agent_form(realm, '')
    assert '/static/js/fdrop.js' in form
    assert '["n-model","n-effort"]' in form and 'mcFDFromSelect(select,' in form
    assert 'mcFDFromSelect' in pages.render_new_agent(realm, tmp_path)
    css = (Path(pages.__file__).parent/'static/brand.css').read_text(encoding='utf-8')
    assert 'select[data-dropdown][hidden]{display:none!important}' in css
