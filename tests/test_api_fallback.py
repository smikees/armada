"""Console-budget fallback: scoped owner keys, critical grants, replay and no worker."""
import json
from pathlib import Path
from types import SimpleNamespace
import urllib.error
import pytest
from armada import api_fallback, billing, provider_keys, run_policy, util, worker
from armada.engine.base import RunResult
from armada.engine.contracts import RunRequest

ENGINE_KEY = 'sk-ant-synthetic-engine-key-never-live'
AGENT_KEY = 'sk-ant-synthetic-agent-key-never-live'


@pytest.mark.parametrize('provider_error, expected', [
    ('You have reached your specified API usage limits', 'spending limit reached'),
    ('Your credit balance is too low to access the Anthropic API', 'credit is exhausted'),
])
def test_provider_budget_stops_without_retries_or_echoing_upstream_body(monkeypatch, provider_error, expected):
    from armada.api_gateway import Gateway
    from io import BytesIO
    import urllib.request
    calls = []
    def denied(self, path, body, headers):
        calls.append(path)
        raise urllib.error.HTTPError('https://api.anthropic.com'+path, 400, 'declined', {},
            BytesIO(json.dumps({'error': {'message': provider_error+' '+ENGINE_KEY}}).encode()))
    monkeypatch.setattr(Gateway, '_open', denied)
    with Gateway(ENGINE_KEY, None) as gateway:
        request = urllib.request.Request(gateway.env['ANTHROPIC_BASE_URL']+'/v1/messages',
            data=json.dumps({'model': 'new-model', 'max_tokens': 10, 'messages': []}).encode(),
            headers={'x-api-key': gateway.token})
        with pytest.raises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=5)
        assert caught.value.headers['x-should-retry'] == 'false'
        response = caught.value.read().decode()
        assert expected in response and ENGINE_KEY not in response
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(request, timeout=5)
        assert calls == ['/v1/messages']


def test_provider_managed_proxy_accepts_new_models_without_local_price_guesses(monkeypatch):
    from armada.api_gateway import Gateway
    from io import BytesIO
    import urllib.request
    calls = []
    class Response(BytesIO):
        status = 200
        headers = {'Content-Type': 'application/json'}
    def reply(self, path, body, headers):
        assert self._key == AGENT_KEY and self.budget is None
        calls.append((path, body))
        return Response(b'{"content":[],"stop_reason":"end_turn","usage":{"input_tokens":1,"output_tokens":1}}')
    monkeypatch.setattr(Gateway, '_open', reply)
    body = {'model': 'a-future-claude-model', 'new_feature': True, 'messages': [], 'max_tokens': 10}
    with Gateway(AGENT_KEY, None) as gateway:
        request = urllib.request.Request(gateway.env['ANTHROPIC_BASE_URL']+'/v1/messages',
            data=json.dumps(body).encode(), headers={'x-api-key': gateway.token})
        with urllib.request.urlopen(request, timeout=5) as response:
            assert response.status == 200
            assert json.loads(response.read())['stop_reason'] == 'end_turn'
    assert calls == [('/v1/messages', body)], 'No local price or token-count admission may block Console-budget mode'


@pytest.fixture
def realm(tmp_path, monkeypatch):
    # Also isolate when stabilization supplies a shared ARMADA_DATA_DIR override.
    monkeypatch.setenv('ARMADA_DATA_DIR', str(tmp_path/'account'))
    root = tmp_path/'realm'
    util.write_json_atomic(root/'realm.json', {'provider': 'claude'})
    for agent in ('a', 'b'):
        util.write_json_atomic(root/'agents'/agent/'agent.json', {'id': agent, 'model': 'claude-fable-5-2'})
    return root


def critical(root, agent='a'):
    job = {'id': 'desk', 'kind': 'agent', 'prompt': 'Synthetic critical work', 'critical': True}
    util.write_json_atomic(root/'agents'/agent/'jobs/desk.json', job)
    run_policy.seal_job(root, agent, job)
    return job


def enable():
    return api_fallback.save('claude', enabled=True, api_key=ENGINE_KEY)


def execute(root, invoke, *, job=None, agent='a', run_id='fallback-test', events=None):
    return billing.execute(SimpleNamespace(name='claude'), RunRequest('system', 'work'),
        root=root, agent=agent, job=job, run_id=run_id, on_event=(events.append if events is not None else lambda event: None),
        on_proc=lambda proc: None, invoke=invoke)


def refusal(text="You've hit your session limit · resets 11:59pm (Europe/Madrid)"):
    return RunResult(ok=False, error=text, raw={'api_error_status': 429})


def test_setup_needs_no_worker_or_realms_secret_and_returns_only_metadata(realm, monkeypatch):
    monkeypatch.setattr(worker, 'require', lambda: pytest.fail('Setup must not require worker activation'))
    config = enable()
    assert config['ready'] and not worker.enabled()
    assert provider_keys.key('claude') == ENGINE_KEY
    assert ENGINE_KEY not in json.dumps(config)
    assert ENGINE_KEY not in api_fallback._path().read_text()
    assert not list(realm.glob('**/provider-secrets.json'))
    if __import__('os').name == 'nt':
        assert ENGINE_KEY not in provider_keys._path().read_text()
    assert not run_policy._ledger_path('claude').exists(), 'New setup must not create a second authoritative budget'


@pytest.mark.parametrize('text', ["You've hit your session limit", "You've hit your weekly limit", "You've hit your 5-hour limit", "You've hit your hourly limit"])
def test_approved_critical_job_falls_back_once_on_the_same_provider(realm, monkeypatch, text):
    job = critical(realm)
    enable()
    monkeypatch.setattr(worker, 'require', lambda: pytest.fail('Fallback must not need a new Windows identity'))
    calls = []
    def invoke(engine, request, **callbacks):
        calls.append(request)
        if len(calls) == 1:
            assert not request.env
            return refusal(text)
        assert engine.name == 'claude'
        assert request.env['ANTHROPIC_API_KEY'] != ENGINE_KEY
        assert request.env['ANTHROPIC_API_KEY'].startswith('armada-run-')
        assert request.env['ANTHROPIC_BASE_URL'].startswith('http://127.0.0.1:')
        assert request.env['ANTHROPIC_AUTH_TOKEN'] == ''
        assert request.max_budget_usd is None
        return RunResult(ok=True, output='Finished', raw={'total_cost_usd': .64})
    result = execute(realm, invoke, job=job)
    assert result.ok and len(calls) == 2
    assert result.raw['billing']['lane'] == 'api'
    assert result.raw['billing']['real_cost_usd'] == .64
    assert result.raw['billing']['refused_attempt']['attempt_id'] == 'fallback-test-plan'
    assert run_policy.credit()['budget_managed'] == 'provider'
    assert run_policy.credit()['cap_usd'] is None


@pytest.mark.parametrize('job_type', ['chat', 'ordinary-job', 'changed-critical'])
def test_noncritical_or_unapproved_work_cannot_activate_paid_fallback(realm, job_type):
    enable()
    job = None
    if job_type != 'chat':
        job = critical(realm)
        job['critical'] = False
        if job_type == 'ordinary-job':
            run_policy.seal_job(realm, 'a', job)
    calls = []
    def invoke(*args, **kwargs):
        calls.append(args)
        return refusal()
    if job_type == 'changed-critical':
        with pytest.raises(ValueError, match='changed after approval'):
            execute(realm, invoke, job=job)
        assert not calls
    else:
        result = execute(realm, invoke, job=job)
        assert not result.ok and len(calls) == 1
        assert result.raw['billing']['lane'] == 'plan'
        assert 'critical jobs' in result.error


def test_agent_workspace_key_is_used_without_changing_other_agents(realm):
    enable()
    api_fallback.save('claude', root=realm, agent='a', key_source='agent', api_key=AGENT_KEY)
    assert api_fallback.credential('claude', realm, 'a') == AGENT_KEY
    assert api_fallback.credential('claude', realm, 'b') == ENGINE_KEY
    api_fallback.save('claude', root=realm, agent='a', key_source='off')
    with pytest.raises(ValueError, match='off'):
        api_fallback.credential('claude', realm, 'a')
    assert api_fallback.credential('claude', realm, 'b') == ENGINE_KEY


def test_agent_only_setup_is_possible_and_never_substitutes_an_engine_key(realm):
    config = api_fallback.save('claude', root=realm, agent='a', key_source='agent', api_key=AGENT_KEY)
    assert config['ready'] and not provider_keys.configured('claude')
    assert api_fallback.settings('claude')['ready']
    assert api_fallback.credential('claude', realm, 'a') == AGENT_KEY
    assert not api_fallback.settings('claude', realm, 'b')['ready']
    provider_keys.save('claude', '', realm, 'a', managed_externally=True)
    with pytest.raises(ValueError):
        api_fallback.credential('claude', realm, 'a')


def test_disabled_engine_and_agent_opt_out_stop_future_fallback(realm):
    job = critical(realm)
    enable()
    api_fallback.save('claude', enabled=False)
    calls = []
    result = execute(realm, lambda *args, **kw: calls.append(args) or refusal(), job=job)
    assert not result.ok and len(calls) == 1
    api_fallback.save('claude', enabled=True)
    api_fallback.save('claude', root=realm, agent='a', key_source='off')
    calls.clear()
    result = execute(realm, lambda *args, **kw: calls.append(args) or refusal(), job=job)
    assert not result.ok and len(calls) == 0  # The recorded plan refusal is still current.


def test_tool_side_effects_without_replay_evidence_prevent_restart(realm):
    job = critical(realm)
    enable()
    calls = []
    def invoke(engine, request, **kw):
        calls.append(request)
        kw['on_event']({'kind': 'tool', 'name': 'Bash', 'input': {'command': 'synthetic delivery'}})
        return refusal()
    result = execute(realm, invoke, job=job)
    assert not result.ok and len(calls) == 1 and 'replay evidence' in result.error
    assert result.raw['billing']['refused_attempt']['tools_ran'] == 1
    assert 'replay evidence' in result.raw['billing']['fallback_blocked_reason']


def test_chat_limit_explains_critical_only_policy_and_retains_partial_work(realm):
    enable()
    calls = []
    def invoke(engine, request, **kw):
        calls.append(request)
        kw['on_event']({'kind':'tool', 'name':'Bash', 'input':{}})
        result = refusal("You've hit your 5-hour limit")
        result.output = 'Partial work already completed'
        result.usage.input = 123
        return result
    result = execute(realm, invoke)
    assert len(calls) == 1 and not result.ok
    assert 'critical jobs' in result.error and 'replay evidence' not in result.error
    assert result.output == 'Partial work already completed' and result.usage.input == 123
    assert result.raw['billing']['refused_attempt']['tools_ran'] == 1
    assert 'critical jobs' in result.raw['billing']['fallback_blocked_reason']


def test_critical_mid_run_refusal_falls_back_with_valid_replay_evidence(realm):
    job = critical(realm)
    enable()
    calls = []
    def invoke(engine, request, **kw):
        calls.append(request)
        if len(calls) == 1:
            kw['on_event']({'kind':'tool', 'name':'Read', 'input':{}})
            result = refusal("You've hit your 5-hour limit")
            block = {'schema_version':1, 'run_id':'fallback-test', 'execution':'failed',
                     'audit_outcome':'not_applicable', 'delivery':[],
                     'evidence':{'outputs':[], 'findings':[], 'missing_inputs':[],
                                 'operational_errors':[], 'risk_gates':[]}}
            result.output = '<armada_job_result>'+json.dumps(block)+'</armada_job_result>'
            return result
        return RunResult(ok=True, output='Completed on API', raw={'total_cost_usd':.21})
    result = execute(realm, invoke, job=job)
    assert result.ok and len(calls) == 2 and result.raw['billing']['lane'] == 'api'
    assert result.raw['billing']['refused_attempt']['tools_ran'] == 1


def test_subscription_only_connector_never_disappears_during_fallback(realm, monkeypatch):
    job = critical(realm)
    enable()
    monkeypatch.setattr(billing, 'connector_guard', lambda *args: ['Interactive Brokers'])
    calls = []
    result = execute(realm, lambda *a, **kw: calls.append(a) or refusal(), job=job)
    assert not result.ok and len(calls) == 1
    assert 'Interactive Brokers is a claude.ai connector' in result.error


def test_console_budget_refusal_and_api_errors_are_final_for_the_invocation(realm):
    job = critical(realm)
    enable()
    calls = []
    def invoke(engine, request, **kw):
        calls.append(request)
        return refusal() if len(calls) == 1 else RunResult(ok=False, error='You have reached your specified workspace API usage limits', raw={'api_error_status': 400})
    result = execute(realm, invoke, job=job)
    assert len(calls) == 2 and not result.ok and result.raw['billing']['final_failure']
    with pytest.raises(ValueError, match='already used'):
        api_fallback.start('claude', 'fallback-test', realm, 'a')


def test_reset_returns_next_critical_job_to_subscription_and_stop_stays_cancelled(realm):
    import time
    job = critical(realm)
    enable()
    def invoke(engine, request, **kw):
        return refusal() if not request.env else RunResult(ok=False, cancelled=True, error='Stopped by owner')
    result = execute(realm, invoke, job=job)
    assert result.cancelled and result.raw['billing']['lane'] == 'api'
    assert api_fallback.credit()['active_runs'] == 0
    util.write_json_atomic(billing._refusal_path('claude'), {'at': time.time()-3600,
        'reset_at': time.time()-1, 'reason': 'Expired weekly limit'})
    requests = []
    result = execute(realm, lambda engine, request, **kw: requests.append(request) or RunResult(ok=True, output='Plan'),
                     job=job, run_id='after-reset')
    assert result.ok and result.raw['billing']['lane'] == 'plan'
    assert len(requests) == 1 and not requests[0].env


@pytest.mark.parametrize('agent, key', [('a', AGENT_KEY), ('b', ENGINE_KEY)])
def test_api_proxy_uses_the_selected_agents_console_workspace_key(realm, monkeypatch, agent, key):
    from armada.api_gateway import Gateway
    enable()
    api_fallback.save('claude', root=realm, agent='a', key_source='agent', api_key=AGENT_KEY)
    seen = []
    original = Gateway.__enter__
    def enter(gateway):
        seen.append(gateway._key)
        return original(gateway)
    monkeypatch.setattr(Gateway, '__enter__', enter)
    result = execute(realm, lambda engine, request, **kw: refusal() if not request.env else RunResult(ok=True),
                     agent=agent, job=critical(realm, agent))
    assert result.ok and seen == [key]


def test_known_secret_is_redacted_from_live_events_and_terminal_receipts(realm):
    job = critical(realm)
    enable()
    events = []
    def invoke(engine, request, **kw):
        if not request.env:
            return refusal()
        kw['on_event']({'kind': 'tool_result', 'content': 'untrusted echo '+ENGINE_KEY})
        return RunResult(ok=False, output=ENGINE_KEY, error='untrusted '+ENGINE_KEY,
                         raw={'diagnostic': {'value': ENGINE_KEY}, 'total_cost_usd': .1})
    result = execute(realm, invoke, job=job, events=events)
    assert ENGINE_KEY not in json.dumps(events)
    assert ENGINE_KEY not in json.dumps(result.raw)+result.error+result.output
    assert ENGINE_KEY not in api_fallback._usage_path('claude').read_text()


def test_unexpected_api_exception_is_reported_without_logging_the_key(realm, caplog):
    enable()
    def invoke(engine, request, **kw):
        if not request.env:
            return refusal()
        raise RuntimeError('Synthetic credential-bearing transport error '+ENGINE_KEY)
    result = execute(realm, invoke, job=critical(realm))
    assert not result.ok and result.raw['billing']['final_failure']
    assert 'API key removed' in result.error and ENGINE_KEY not in caplog.text
    assert 'RuntimeError' in caplog.text and api_fallback.credit()['active_runs'] == 0


def test_unknown_usage_does_not_invent_a_cost_or_reject_a_provider_managed_job(realm):
    job = critical(realm)
    enable()
    def invoke(engine, request, **kw):
        return refusal() if not request.env else RunResult(ok=True, output='Finished without a cost counter')
    result = execute(realm, invoke, job=job)
    assert result.ok and result.raw['billing']['real_cost_usd'] is None
    assert api_fallback.credit()['unknown_runs'] == 1
    from armada import usage_snapshot
    assert 'no reported cost' in usage_snapshot.preamble(realm)
    api_fallback._usage_path('claude').write_text('{broken', encoding='utf-8')
    result = execute(realm, invoke, job=job, run_id='second')
    assert result.ok and not result.raw['billing']['accounting_available']
    assert api_fallback.credit()['spent_usd'] is None


def test_failed_key_save_does_not_activate_legacy_spending(realm, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError('Synthetic write failed')
    monkeypatch.setattr(provider_keys, 'save', fail)
    with pytest.raises(OSError):
        enable()
    assert api_fallback.managed('claude') and not api_fallback.settings()['ready']
    assert run_policy.settings(realm, 'a')['plan_limit_action'] == 'fail'


@pytest.mark.parametrize('changes', [{'started_at': 'yesterday'}, {'started_at': None}, {'started_at': 10**1000},
    {'finished_at': 'later'}, {'status': 'invalid'}])
def test_malformed_advisory_rows_cannot_turn_a_completed_api_job_into_an_error(realm, changes):
    job = critical(realm)
    enable()
    row = {'started_at': 1, 'finished_at': 2, 'status': 'finished', 'cost_usd': .1, **changes}
    util.write_json_atomic(api_fallback._usage_path('claude'), {'runs': {'damaged': row}})
    result = execute(realm, lambda engine, request, **kw: refusal() if not request.env else
                     RunResult(ok=True, output='Finished', raw={'total_cost_usd': .25}), job=job)
    assert result.ok and result.raw['billing']['real_cost_usd'] == .25
    assert not result.raw['billing']['accounting_available']
    assert api_fallback.credit()['spent_usd'] is None


def test_overflow_in_advisory_totals_is_unavailable_not_an_invented_balance(realm):
    import time
    enable()
    row = {'started_at': time.time()-10, 'finished_at': time.time(), 'status': 'finished', 'cost_usd': 1e308}
    util.write_json_atomic(api_fallback._usage_path('claude'), {'runs': {'one': row, 'two': row}})
    credit = api_fallback.credit()
    assert credit['spent_usd'] is None and not credit['accounting_available'] and credit['open']


def test_damaged_policy_leaves_plan_calls_available_but_api_closed(realm):
    enable()
    api_fallback._path().write_text('{broken', encoding='utf-8')
    assert api_fallback.managed('claude') and not api_fallback.settings()['ready']
    result = execute(realm, lambda *args, **kwargs: RunResult(ok=True, output='Plan worked'))
    assert result.ok and result.raw['billing']['lane'] == 'plan'


def test_free_key_check_never_generates_or_echoes_the_key(realm, monkeypatch):
    import urllib.request
    calls = []
    class Response:
        status = 200
        def __enter__(self):return self
        def __exit__(self, *args):pass
    class Opener:
        def open(self, request, **kw):
            calls.append(request)
            return Response()
    monkeypatch.setattr(urllib.request, 'build_opener', lambda *args: Opener())
    result = api_fallback.verify('claude', api_key=ENGINE_KEY)
    assert len(calls) == 1 and calls[0].get_method() == 'GET'
    assert calls[0].full_url == 'https://api.anthropic.com/v1/models'
    assert ENGINE_KEY not in result and not api_fallback.managed('claude')


@pytest.mark.parametrize('provider', ['codex', 'gemini'])
def test_unshipped_providers_cannot_use_the_claude_key(realm, provider):
    with pytest.raises(ValueError, match='Claude only'):
        api_fallback.save(provider, enabled=True, api_key=ENGINE_KEY)
    calls = []
    result = billing.execute(SimpleNamespace(name=provider), RunRequest('s', 'p'), root=realm,
        agent='a', job=critical(realm), run_id='other', on_event=lambda e: None, on_proc=None,
        invoke=lambda engine, request, **kw: calls.append(request) or RunResult(ok=True, output='Original provider'))
    assert result.ok and len(calls) == 1 and not calls[0].env


def test_real_runner_records_the_api_lane_without_persisting_the_key(realm):
    from armada import runner
    from armada.engine import MockEngine
    job = critical(realm)
    enable()
    calls = []
    class FakeClaude(MockEngine):
        name = 'claude'
        def execute(self, request, **callbacks):
            calls.append(request)
            if not request.env:
                return refusal()
            callbacks['on_event']({'kind': 'text', 'text': 'Completed '+ENGINE_KEY})
            return RunResult(ok=True, output='Completed '+ENGINE_KEY+'\nARMADA_JOB_RESULT: SUCCESS', raw={'total_cost_usd': .25})
    result = runner.run_job(realm, 'a', job['id'], engine=FakeClaude())
    assert len(calls) == 2
    rows = []
    for path in (realm/'agents/a/runs').glob('*.jsonl'):
        rows += [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    report = next(row for row in rows if row.get('billing', {}).get('lane') == 'api')
    assert report['billing']['real_cost_usd'] == .25
    for path in realm.rglob('*'):
        if path.is_file() and path.suffix in ('.json', '.jsonl', '.md', '.txt'):
            assert ENGINE_KEY not in path.read_text(encoding='utf-8'), path


def test_owner_endpoint_never_returns_keys_and_companions_cannot_change_them(realm, tmp_path):
    from tests.golden_support import ServedRealm, build_fixture
    import http.client
    from armada.request_context import RealmContext
    root = build_fixture(tmp_path/'served')
    with ServedRealm(root) as server:
        saved = server.post('/api/api-fallback', {'action': 'save', 'provider': 'claude', 'enabled': True, 'api_key': ENGINE_KEY})
        assert saved['ok'] and ENGINE_KEY not in json.dumps(saved)
        agent = server.post('/api/api-fallback', {'action': 'save', 'provider': 'claude', 'agent': 'captain',
            'key_source': 'agent', 'api_key': AGENT_KEY})
        assert agent['ok'] and AGENT_KEY not in json.dumps(agent)
        assert AGENT_KEY not in server.get('/agent/captain/configure')
        assert ENGINE_KEY not in server.get('/settings?tab=app')
        connection = http.client.HTTPConnection('127.0.0.1', server.port, timeout=5)
        headers = {**server.auth_headers(), 'Content-Type': 'application/json',
                   'X-Armada-Realm': RealmContext.capture(root).realm_id, 'X-Armada-Companion': 'thread'}
        try:
            connection.request('POST', '/api/api-fallback', json.dumps({'action': 'save', 'provider': 'claude', 'enabled': False}), headers)
            response = connection.getresponse();raw = response.read()
            assert not json.loads(raw)['ok']
        finally:
            connection.close()
        assert api_fallback.settings()['enabled']
