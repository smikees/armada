import datetime as dt
import json
import threading
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from armada import app, reader, runner, token_cost
from armada.execution import _LiveTextRenderer
from armada.webui import pages
from armada.webui._core import _totals_30d, _usage_data


def test_last_delta_is_rendered_and_checkpointed_during_provider_pause():
    painted, checkpoints, ready = [], [], threading.Event()
    def sink(event):
        painted.append(event)
        if 'full sentence.' in event['html']:
            ready.set()
    render = _LiveTextRenderer(sink, interval=.025, checkpoint=checkpoints.append)
    try:
        render.update('A full')
        render.update('A full sentence.')
        assert ready.wait(1), 'The last delta must not wait for a tool event or terminal answer'
        assert checkpoints[-1] == 'A full sentence.'
    finally:
        render.close()
    render.update('late event')
    assert 'late event' not in str(painted)


@pytest.mark.parametrize('model,expected', [
    ('gpt-6.1-sol', 12.1), ('codex:gpt-6-sol', 12.2),
    ('gemini:gemini-3.8-flash', 4.575), ('gemini:gemini-3.1-pro', 14.2),
    ('claude-opus-5-5', 24.2), ('claude-fable-5-1', 60.25),
])
def test_api_equivalent_prices_all_engines_without_double_counting(model, expected):
    assert token_cost.estimate(model, {'input': 1_000_000, 'output': 1_000_000,
                                      'cache_read': 1_000_000, 'reasoning': 900_000}, '2026-10-01') == expected


def test_unknown_costs_stay_unknown_and_reported_costs_win():
    assert token_cost.estimate('codex:default', {'input': 1, 'output': 1}) is None
    assert token_cost.estimate('gpt-6-sol', {'input': 10}) is None
    assert token_cost.estimate('gpt-6-sol', {'input': -10, 'output': 1}) is None
    assert token_cost.for_run({'model': 'unknown', 'tokens': {'api_equiv_usd': 0}}) == 0
    assert token_cost.estimate('gemini-3.8-flash', {'input': 1_000_000, 'output': 0}, '2027-01-01') == 1.5


@pytest.mark.skipif(shutil.which('node') is None, reason='Node required for pending-state checks')
def test_connector_loaders_finish_for_every_provider():
    script = (Path(pages.__file__).parent / 'static/js/connmodal.js').read_text(encoding='utf-8')
    script = script[script.index('const MC_CONN_LABEL'):script.index('async function mcCodexConnect')]
    harness = r'''
const assert=require('assert');
const badges=['claude','codex','gemini'].map(provider=>({dataset:{cap:'ibkr',provider},
  mark:{dataset:{},innerHTML:'<svg class="loader"></svg>',textContent:'',setAttribute(){}},querySelector(){return this.mark;}}));
global.document={querySelectorAll:s=>s.includes('badge')?badges.filter(b=>!s.includes('checking')||b.dataset.state==='checking'):[]};
let resolve;global.fetch=()=>new Promise(r=>resolve=r);
''' + script + r'''
(async()=>{
const pending=mcCapConnectionsRefresh();
assert(badges.every(b=>b.dataset.state==='checking'&&b.mark.innerHTML.includes('loader')));
resolve({ok:true,json:async()=>({providers:{},connectors:{ibkr:{claude:'missing',codex:'ready',gemini:'unsupported'}}})});
await pending;assert(badges.every(b=>b.dataset.state!=='checking'));
assert.equal(badges[1].mark.textContent,'✓');assert.equal(badges[1].mark.innerHTML,'');
assert(badges[2].title.includes('Not configured in Gemini'));
fetch=async()=>{throw Error('offline')};await mcCapConnectionsRefresh();
assert(badges.every(b=>b.dataset.state==='unknown'&&b.mark.textContent==='?'));
})().catch(e=>{console.error(e);process.exit(1)});
'''
    proc = subprocess.run([shutil.which('node')], input=harness, text=True, encoding='utf-8', capture_output=True)
    assert proc.returncode == 0, proc.stderr


def test_header_counts_coordinator_and_keeps_partial_totals(tmp_path):
    (tmp_path / 'realm.json').write_text(json.dumps({'name': 'Test', 'coordinator': 'hand'}))
    for aid in ('hand', 'finance'):
        ad = tmp_path / 'agents' / aid
        ad.mkdir(parents=True)
        (ad / 'agent.json').write_text(json.dumps({'id': aid, 'display': aid, 'coordinator': aid == 'hand'}))
    now = dt.date.today().isoformat()
    for model in ('gpt-6-sol', 'gemini:gemini-3.8-flash', 'claude-opus-5-5'):
        runner._write_report(tmp_path / 'agents/finance', 'finance', {'ts': now, 'model': model,
           'tokens': {'input': 1_000_000, 'output': 1_000_000, 'total': 2_000_000}})
    runner._write_report(tmp_path / 'agents/finance', 'finance', {'ts': now, 'model': 'unknown', 'tokens': {}})
    realm = reader.read(tmp_path)
    totals = _totals_30d(realm, tmp_path, dt.date.today(), details=True)
    assert totals == {'total_30d': 6_000_000, 'usd_30d': 40.5,
                      'unknown_token_runs_30d': 1, 'unknown_cost_runs_30d': 1}
    assert _usage_data(realm, tmp_path, 'line', 'today')['usd_30d'] == 40.5
    html = pages._overview_kpis(realm, tmp_path)
    assert '6.0M+' in html and '≈$41+' in html and 'partial total: 1' in html
    assert '>2<span' in html and 'mc-skel' not in html


@pytest.mark.parametrize('ready', [True, False])
def test_native_splash_exists_before_waiting_for_server(ready):
    class Event:
        def __init__(self): self.callbacks=[]
        def __iadd__(self, callback):
            self.callbacks.append(callback)
            return self
        def emit(self):
            for callback in self.callbacks: callback()
    window = Mock(events=MagicMock())
    window.events.loaded = Event()
    webview = Mock(create_window=Mock(return_value=window))
    loader = Mock(finished=False)
    def navigated(url):
        loader.ready.assert_not_called()
        window.events.loaded.emit()
    window.load_url.side_effect = navigated
    order = []
    def wait(*args, **kwargs):
        assert webview.create_window.called
        order.append('wait')
        return ready
    def start(callback, **kwargs):
        assert 'role="progressbar"' in webview.create_window.call_args.kwargs['html']
        window.events.loaded.emit()
        loader.ready.assert_not_called()
        callback()
    webview.start.side_effect = start
    with patch.dict('sys.modules', {'webview': webview}), \
         patch.object(app, 'webview2_version', return_value='1'), \
         patch.object(app, '_retire_scheduler_run_key'), patch.object(app, '_set_app_user_model_id'), \
         patch.object(app, '_server_matches', return_value=True), \
         patch.object(app, '_wait_until_up', side_effect=wait), patch.object(app, '_apply_window_icon'), \
         patch.object(app, '_fatal') as fatal, patch.object(app.threading, 'Thread'), \
         patch('armada.serve.port_owner', return_value=0), patch('armada.tray.Tray'), \
         patch('armada.startup_splash.LoadingPanel', return_value=loader) as loading_panel, \
         patch('armada.schedsvc.stop_for_app_exit'):
        assert app.run('Test') == (0 if ready else 1)
    assert order == ['wait']
    webview.create_window.assert_called_once()
    loading_panel.assert_called_once_with(window)
    if ready:
        window.load_url.assert_called_once_with('http://127.0.0.1:8756/')
        loader.ready.assert_called_once()
    else:
        fatal.assert_called_once()
        window.destroy.assert_called_once()
        window.load_url.assert_not_called()
        loader.ready.assert_not_called()
