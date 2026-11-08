"""Owner previews use the same validator and never mutate permissions or their audit log."""
import pytest
from armada import access_policy as policy, util
from test_access_policy import realm


def files(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('provider', ['claude', 'codex', 'gemini'])
def test_preview_grants_draft_but_deny_still_wins_without_writes(realm, provider):
    before = files(realm)
    change = {'tool_policy': {'ibkr': {'allow': ['get_*', 'create_order_instruction', 'submit_order'],
                                     'deny': ['submit_*']}}, 'write_scope': ['Finance/desk/**']}
    result = policy.preview(realm, 'analyst', change, provider)
    connector = result['connectors'][0]
    assert set(connector['can_call']) == {'get_balance', 'get_orders', 'create_order_instruction'}
    assert connector['newly_allowed'] == ['create_order_instruction']
    assert 'submit_order' in connector['cannot_call']
    assert result['write_scope'] == ('Finance/desk/**',) and result['scoped']
    assert files(realm) == before
    policy.save(realm, 'analyst', change)
    saved = policy.load(realm, 'analyst')
    assert all(saved.rule('ibkr').permits(n) for n in connector['can_call'])
    assert all(not saved.rule('ibkr').permits(n) for n in connector['cannot_call'])


def test_preview_never_grants_a_connector(realm):
    ap = realm / 'agents/analyst/agent.json'
    data = util.read_json_state(ap)
    data['toolkit'] = {}
    util.write_json_atomic(ap, data)
    result = policy.preview(realm, 'analyst', {'tool_policy': {'ibkr': {'allow': ['*']}}}, 'claude')
    assert result['connectors'][0]['can_call'] == []


def test_realm_preview_preserves_explicit_allow_and_identifies_builder(realm):
    before = files(realm)
    result = policy.preview(realm, 'analyst', {'tool_policy': {'ibkr': {'deny': ['*']}},
        'read_only': ['shared/**'], 'policy_builder': 'analyst'}, 'codex', realm_defaults=True)
    assert result['connectors'][0]['can_call'] == ['get_balance', 'get_orders']
    assert result['builder'] and not result['scoped']
    assert files(realm) == before


@pytest.mark.parametrize('change', [None, {'unknown': []}, {'tool_policy': []},
    {'tool_policy': {'ibkr': {'allow': ['get_[']}}}, {'write_scope': ['../outside/**']}])
def test_invalid_preview_refuses_without_writes(realm, change):
    before = files(realm)
    with pytest.raises(ValueError):
        policy.preview(realm, 'analyst', change, 'gemini')
    assert files(realm) == before


def test_literal_tool_names_do_not_require_inventory(realm):
    util.mutate_json(realm / 'realm.json', lambda data: data['toolkit']['connectors'][0].update(tool_names=[]))
    result = policy.preview(realm, 'analyst', {'tool_policy': {'ibkr': {'allow': ['get_balance']}}}, 'claude')
    row = result['connectors'][0]
    assert row['can_call'] == ['get_balance'] and row['literal_names'] == ['get_balance']
    assert not row['inventory_known']


def test_missing_glob_inventory_reports_run_refusal(realm):
    util.mutate_json(realm / 'realm.json', lambda data: data['toolkit']['connectors'][0].update(tool_names=[]))
    row = policy.preview(realm, 'analyst', {'tool_policy': {'ibkr': {'allow': ['get_*']}}}, 'claude')['connectors'][0]
    assert row['can_call'] == [] and 'No tool inventory' in row['reason']


def test_scoped_filesystem_is_not_misreported_as_available(realm):
    from armada import capabilities
    util.mutate_json(realm / 'realm.json', lambda data: data['toolkit'].update(extensions=[{
        'id': 'files', 'extension_id': 'ant.dir.ant.anthropic.filesystem',
        'tool_names': ['read_file', 'write_file']}]))
    capabilities.grant(realm, 'analyst', 'files')
    rows = policy.preview(realm, 'analyst', {}, 'claude')['connectors']
    row = next(row for row in rows if row['id'] == 'files')
    assert row['can_call'] == [] and row['cannot_call'] == ['read_file', 'write_file']
    assert 'guarded file tool' in row['reason']


@pytest.mark.parametrize('provider', ['claude', 'codex', 'gemini'])
def test_shared_registration_intersects_both_logical_policies(realm, provider):
    def configure(data):
        data['toolkit']['connectors'] = [dict(id=cid, tool_names=['get_balance', 'get_orders'],
            provider_bindings={provider: {'server_name': 'shared-broker'}}) for cid in ('ibkr', 'alias')]
    util.mutate_json(realm / 'realm.json', configure)
    util.mutate_json(realm / 'agents/analyst/agent.json', lambda data: data.update(
        toolkit={'connectors': [{'id': 'ibkr'}, {'id': 'alias'}]},
        tool_policy={'ibkr': {'allow': ['get_*']}, 'alias': {'allow': ['get_balance']}}))
    rows = policy.preview(realm, 'analyst', {}, provider)['connectors']
    assert all(row['can_call'] == ['get_balance'] for row in rows)
