"""Saved settings, exact run inputs and encoding must agree without a weekly wait."""
import hashlib
import json

import pytest

from armada import activerealm, clock, memory, reader, runner, util
from armada.engine import MockEngine
from armada.engine.base import RunResult
from armada.serve import Handler
from armada.threads import Thread


class H(Handler):
    def __init__(self, root):
        self.realm = str(root)


@pytest.fixture
def realm(tmp_path, monkeypatch):
    util.write_json_atomic(tmp_path / 'realm.json', {'name': 'Synthetic realm'})
    for aid in ('a', 'b'):
        util.write_json_atomic(tmp_path / f'agents/{aid}/agent.json', {'id': aid})
    monkeypatch.setattr(memory, 'probe_environment', lambda: {'Machine': 'detected-host', 'CPU': 'detected CPU'})
    return tmp_path


def test_save_environment_updates_digest_and_utf8(realm):
    env = {'Machine': 'Mini PC — always on', 'Operating system': 'Test OS',
           'GPU': 'Saved GPU', 'Notes': 'Dedicated to this realm.\nΔοκιμή · 日本語'}
    assert H(realm)._save_realm_settings({'env': env})['ok']
    assert json.loads((realm / 'realm.json').read_bytes().decode('utf-8'))['env'] == env
    for aid in ('a', 'b'):
        core = memory.assemble_core(realm, realm / f'agents/{aid}', {})
        assert all(line in core for value in env.values() for line in value.splitlines())
        assert 'Last regenerated:' in core and 'detected-host' not in core
    assert H(realm)._save_realm_settings({'env': {'Notes': 'Revised'}})['ok']
    assert 'Mini PC — always on' in memory.system_digest(realm)


def test_blank_override_returns_to_detection_without_reviving_old_gpu(realm):
    H(realm)._save_realm_settings({'env': {'Machine': 'Owner label', 'GPU': 'Old GPU'}})
    H(realm)._save_realm_settings({'env': {'Machine': '', 'GPU': ''}})
    body = memory.system_digest(realm)
    assert 'detected-host' in body
    assert 'Old GPU' not in body and 'Owner label' not in body


@pytest.mark.parametrize('env', [[], {'Notes': 4}, {'Notes': 'x' * 4001}, {'Machine': '\x00'}, {'unknown': 'x'}])
def test_invalid_environment_does_not_modify_settings(realm, env):
    before = (realm / 'realm.json').read_bytes()
    assert not H(realm)._save_realm_settings({'env': env})['ok']
    assert (realm / 'realm.json').read_bytes() == before


def test_refresh_failure_is_not_reported_as_success(realm, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError('Synthetic memory write failure')
    monkeypatch.setattr(memory, 'refresh_system_memory', fail)
    result = H(realm)._save_realm_settings({'env': {'Machine': 'Saved'}})
    assert not result['ok'] and 'memory write failure' in result['error']


def test_regeneration_time_is_visible_even_when_content_is_unchanged(realm):
    with clock.frozen('2026-11-01T09:00:00+01:00'):
        memory.refresh_system_memory(realm)
    with clock.frozen('2026-11-02T10:00:00+01:00'):
        assert not memory.refresh_system_memory(realm)['changed']
    meta, _ = memory._frontmatter((realm / 'memory/core-context.md').read_text(encoding='utf-8'))
    assert meta['updated'] == '2026-11-01T09:00:00+01:00'
    assert meta['refreshed'] == '2026-11-02T10:00:00+01:00'
    assert meta['refreshed'] in memory.assemble_core(realm, realm / 'agents/a', {})
    assert not list((realm / 'memory/.system-versions').glob('*.md'))


def test_invalid_utf8_preserves_previous_digest_and_reports_error(realm):
    memory.refresh_system_memory(realm)
    before = (realm / 'memory/core-context.md').read_bytes()
    bad = b'{"env":{"Machine":"host \x97 always on"}}'
    (realm / 'realm.json').write_bytes(bad)
    with pytest.raises(util.StateError, match='encoding'):
        memory.refresh_system_memory(realm)
    with pytest.raises(util.StateError, match='encoding'):
        reader.read(realm)
    assert (realm / 'memory/core-context.md').read_bytes() == before
    assert (realm / 'realm.json').read_bytes() == bad


def test_startup_refreshes_active_and_registered_realms(realm, tmp_path, monkeypatch):
    other = tmp_path / 'other'
    util.write_json_atomic(other / 'realm.json', {'env': {'Machine': 'Other host'}})
    monkeypatch.setattr(activerealm, 'every', lambda: [str(other), str(realm)])
    memory.refresh_startup(realm)
    assert 'Other host' in (other / 'memory/core-context.md').read_text(encoding='utf-8')
    assert 'detected-host' in (realm / 'memory/core-context.md').read_text(encoding='utf-8')


def test_old_refresh_cannot_overwrite_a_newer_settings_save(realm, monkeypatch):
    import threading
    original = memory.system_digest
    built, release, saving, saved = (threading.Event() for _ in range(4))
    errors = []
    def delayed(root):
        body = original(root)
        if threading.current_thread().name == 'old-refresh':
            built.set()
            assert release.wait(5)
        return body
    monkeypatch.setattr(memory, 'system_digest', delayed)
    def refresh():
        try:
            memory.refresh_system_memory(realm)
        except Exception as exc:
            errors.append(exc)
    def save():
        saving.set()
        result = H(realm)._save_realm_settings({'env': {'Machine': 'Newest host'}})
        if not result['ok']:
            errors.append(result)
        saved.set()
    first = threading.Thread(target=refresh, name='old-refresh')
    second = threading.Thread(target=save)
    first.start()
    try:
        assert built.wait(5)
        second.start()
        assert saving.wait(5)
        # An implementation that builds outside the lock lets the new save finish
        # here; the delayed refresh would subsequently overwrite it with old facts.
        saved.wait(.25)
    finally:
        release.set()
        first.join(5)
        if second.ident is not None:
            second.join(5)
    assert not first.is_alive() and not second.is_alive() and not errors
    assert 'Newest host' in (realm / 'memory/core-context.md').read_text(encoding='utf-8')


def test_failed_refresh_stops_before_engine_and_does_not_claim_a_receipt(realm, monkeypatch):
    engine = MockEngine()
    monkeypatch.setattr(engine, 'run', lambda **kwargs: pytest.fail('Invoked with stale memory'))
    def fail(*args, **kwargs):
        raise OSError('No refresh')
    monkeypatch.setattr(memory, 'refresh_system_memory', fail)
    result = runner.chat(realm, 'a', 'main', 'Synthetic message', engine=engine)
    assert result['status'] == 'error'
    reply = Thread(realm / 'agents/a', 'main').snapshot()[1][-1]
    assert 'memory_receipt' not in reply and 'No refresh' in reply['content']


def test_realm_note_save_and_agent_isolation(realm):
    h = H(realm)
    assert h._add_memory({'scope': 'realm', 'title': 'Host note', 'text': 'Shared host fact'})['ok']
    assert h._add_memory({'scope': 'agent', 'agent': 'a', 'title': 'Private', 'text': 'Only A knows'})['ok']
    assert (realm / 'memory/host-note.md').is_file()
    for aid in ('a', 'b'):
        receipts = []
        core = memory.assemble_core(realm, realm / f'agents/{aid}', {}, receipts)
        assert 'Shared host fact' in core
        assert ('Only A knows' in core) == (aid == 'a')
        assert any(item['scope'] == 'realm' and item['title'] == 'Host note' for item in receipts)
        assert any(item['scope'] == 'agent' for item in receipts) == (aid == 'a')


@pytest.mark.parametrize('kind', ['chat', 'stream', 'job', 'inbox'])
def test_run_receipts_capture_inputs_before_later_edits(realm, monkeypatch, kind):
    from armada.job_history import thread_name
    from armada.webui.memory_receipts import render
    note = realm / 'memory/host-note.md'
    util.write_text_atomic(note, '---\ntitle: Host note\n---\nOriginal fact\n')
    util.write_json_atomic(realm / 'agents/a/jobs/work.json', {'id': 'work', 'prompt': 'Synthetic job'})
    memory.refresh_system_memory(realm)
    # An external edit must be noticed without waiting for settings, startup or the weekly job.
    util.write_json_atomic(realm / 'realm.json', {'env': {'Machine': 'Updated host'}})
    engine = MockEngine()
    seen = []
    def run(**kwargs):
        seen.append(kwargs['system'])
        assert 'Updated host' in kwargs['system']
        assert 'Original fact' in kwargs['system']
        util.write_text_atomic(note, '---\ntitle: Changed title\n---\nLater fact\n')
        return RunResult(ok=True, output='Synthetic answer')
    monkeypatch.setattr(engine, 'run', run)
    monkeypatch.setattr(engine, 'run_stream', run)
    if kind == 'job':
        result = runner.run_job(realm, 'a', 'work', engine=engine)
    elif kind == 'inbox':
        result = runner.run_job_prompt(realm, 'a', 'Synthetic message', engine=engine)
    elif kind == 'stream':
        result = runner.chat_stream(realm, 'a', 'main', 'Synthetic message', lambda ev: None, engine=engine)
    else:
        result = runner.chat(realm, 'a', 'main', 'Synthetic message', engine=engine)
    assert result['status'] == 'ok' and seen
    th = Thread(realm / 'agents/a', thread_name('work') if kind == 'job' else 'main')
    reply = [m for m in th.snapshot()[1] if m.get('role') == 'assistant'][-1]
    receipt = reply['memory_receipt']
    host = next(item for item in receipt['items'] if item['title'] == 'Host note')
    assert host['sha256'] == hashlib.sha256(b'Original fact').hexdigest()
    report = json.loads((realm / 'agents/a/runs/a.jsonl').read_text(encoding='utf-8').splitlines()[-1])
    assert report['memory_receipt'] == receipt
    assert 'Host note' in render(receipt) and 'Changed title' not in render(receipt)
    from armada.webui.threadsview import _render_turns
    from armada.webui.jobresults import result_html
    agent = next(a for a in reader.read(realm).agents if a.id == 'a')
    assert 'Memories received' in _render_turns(realm, agent, th.name)
    assert 'Memories received' in result_html(report, {'content': 'Synthetic answer'})


def test_receipt_escapes_owner_text_and_does_not_invent_old_run_inputs():
    from armada.webui.memory_receipts import render
    assert not render(None)
    html = render({'items': [{'title': '<script>bad()</script>', 'path': '<img>', 'scope': 'realm'}]})
    assert '<script>' not in html and '&lt;script&gt;' in html
