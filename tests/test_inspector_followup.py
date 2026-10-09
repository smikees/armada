"""Narrow managed inspector outputs/delivery, preserving draft-only model turns."""
import concurrent.futures
import json
import os
from pathlib import Path
import zipfile

import pytest

from armada import appconfig, dry_run_pairs, inspection, job_access, job_history, notify, telegram, util
from armada.engine.base import RunResult
from armada.managed_tools import ManagedTools
from tests.test_draft_review import _wait_pair
from tests.test_dry_runs import realm, approve_inspector, DraftEngine


def approved_job(root, folder):
    approve_inspector(root)
    folder.mkdir(parents=True, exist_ok=True)
    job = {'id': 'review', 'kind': 'agent', 'inspector': True, 'allow_tools': True, 'prompt': 'Review synthetic models.'}
    util.write_json_atomic(root / 'agents/inspector/jobs/review.json', job)
    inspection._set('job_access', job_access.identity(root, 'inspector', job['id']),
        {'fingerprint': job_access.fingerprint(job), 'roots': [str(folder)], 'network': True,
         'checks': [{'kind': 'http_status', 'url': 'https://must-not-fetch.invalid/'}]})
    return job


def test_own_running_grant_atomic_write_and_revocation(realm, tmp_path, monkeypatch):
    approved = tmp_path / 'approved'
    job = approved_job(realm, approved)
    tools = ManagedTools(realm, 'inspector', inspector=True, job=job)
    text = '12.34 · Проба · 测试\n'
    result = tools.call('write_file', {'path': str(approved / 'review.md'), 'content': text})
    assert Path(result['path']).read_text(encoding='utf-8') == text
    assert result['bytes'] == len(text.encode('utf-8'))
    tools.call('write_draft', {'path': 'own.md', 'content': 'kept working'})
    assert (realm / 'agents/inspector/artifacts/own.md').read_text() == 'kept working'
    with pytest.raises(ValueError):
        tools.call('write_draft', {'path': str(approved / 'draft.md'), 'content': 'x'})
    def fail(*args):
        raise OSError('synthetic replace failure')
    with monkeypatch.context() as changes:
        changes.setattr(os, 'replace', fail)
        with pytest.raises(OSError):
            tools.call('write_file', {'path': result['path'], 'content': 'changed'})
    assert Path(result['path']).read_text(encoding='utf-8') == text
    inspection._set('job_access', job_access.identity(realm, 'inspector', 'review'), None)
    with pytest.raises(ValueError):
        tools.call('write_file', {'path': result['path'], 'content': 'revoked'})
    tools.call('write_file', {'path': 'still-own.md', 'content': 'own artifacts remain'})
    assert len(tools.seal()['writes']) == 3
    with pytest.raises(ValueError, match='expired'):
        tools.call('write_file', {'path': 'after.md', 'content': 'x'})


@pytest.mark.parametrize('name', ['../outside.txt', 'nested/../../outside.txt', 'NUL', 'COM1.txt',
    'review.txt:stream', 'review. ', 'agent.json', 'AGENT.JSON', 'jobs/test.json', 'memory/test.md',
    '.armada/state.json', '.codex/config.toml', 'realm.json', 'final-answer.md'])
def test_output_aliases_traversal_and_control_names_are_refused(realm, name):
    approve_inspector(realm)
    tools = ManagedTools(realm, 'inspector', inspector=True)
    for tool in ('write_file', 'write_draft'):
        with pytest.raises(ValueError):
            tools.call(tool, {'path': name, 'content': 'x'})


def test_broad_root_cannot_admit_foreign_agents_or_realm_state(realm, tmp_path):
    job = approved_job(realm, tmp_path)
    tools = ManagedTools(realm, 'inspector', inspector=True, job=job)
    foreign = tmp_path / 'foreign'
    foreign.mkdir(); (foreign / 'realm.json').write_text('{}')
    for path in (realm / 'agents/writer/artifacts/report.md', realm / 'agents/inspector/mandate.md',
                 realm / 'realm.json', realm / 'memory/core.md', appconfig._path(), foreign / 'shared/report.md'):
        with pytest.raises(ValueError):
            tools.call('write_file', {'path': str(path), 'content': 'forbidden'})
    tools.call('write_file', {'path': str(realm / 'shared/reviews/report.md'), 'content': 'approved'})
    # Another job's roots cannot be claimed with a synthetic prompt.
    with pytest.raises(ValueError):
        ManagedTools(realm, 'inspector', inspector=True, job={**job, 'prompt': 'different'})
    util.mutate_json(realm / 'agents/inspector/jobs/review.json', lambda j: j.update(prompt='changed'))
    with pytest.raises(ValueError):
        tools.call('write_file', {'path': str(tmp_path / 'report.md'), 'content': 'x'})


def test_approved_parent_name_is_not_confused_with_realm_control_folder(realm, tmp_path):
    folder = tmp_path / 'jobs' / 'approved-review'
    job = approved_job(realm, folder)
    tools = ManagedTools(realm, 'inspector', inspector=True, job=job)
    result = tools.call('write_file', {'path': str(folder / 'report.md'), 'content': 'approved'})
    assert Path(result['path']).read_text() == 'approved'


def test_write_limit_is_utf8_bytes_and_link_escape_is_refused(realm, tmp_path):
    folder = tmp_path / 'approved'
    job = approved_job(realm, folder)
    tools = ManagedTools(realm, 'inspector', inspector=True, job=job)
    tools.call('write_file', {'path': str(folder / 'limit.txt'), 'content': 'x' * (1024 * 1024)})
    with pytest.raises(ValueError, match='1 MiB'):
        tools.call('write_file', {'path': str(folder / 'too-large.txt'), 'content': 'é' * (512 * 1024 + 1)})
    outside = tmp_path / 'outside'; outside.mkdir()
    link = folder / 'escape'
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        if os.name != 'nt':
            raise
        import subprocess
        subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(outside)], check=True, capture_output=True)
    with pytest.raises(ValueError):
        tools.call('write_file', {'path': str(link / 'escaped.txt'), 'content': 'x'})
    assert not (outside / 'escaped.txt').exists()
    # Root links cannot disappear during grant_for's normal path resolution.
    inspection._set('job_access', job_access.identity(realm, 'inspector', 'review'),
        {'fingerprint': job_access.fingerprint(job), 'roots': [str(link)], 'network': False, 'checks': []})
    with pytest.raises(ValueError):
        tools.call('write_file', {'path': str(outside / 'escaped.txt'), 'content': 'x'})


def test_fixed_owner_plaintext_delivery_and_concurrent_turn_limit(realm, monkeypatch):
    approve_inspector(realm)
    monkeypatch.setattr(notify, 'muted', lambda: False)
    monkeypatch.setattr(telegram, 'creds', lambda: ('synthetic-token', 'owner-only', 'test'))
    payloads = []
    def api(token, method, payload):
        payloads.append(payload)
        assert token == 'synthetic-token' and method == 'sendMessage'
        return {'ok': True, 'result': {'message_id': len(payloads)}}
    monkeypatch.setattr(telegram, 'api', api)
    tools = ManagedTools(realm, 'inspector', inspector=True)
    def send(i):
        try:
            return tools.call('notify_owner', {'text': f'Review {i}: **literal text** <data>'})
        except ValueError:
            return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        sent = [r for r in pool.map(send, range(4)) if r]
    assert len(sent) == len(payloads) == 2
    assert all(p['chat_id'] == 'owner-only' and p['disable_web_page_preview'] for p in payloads)
    assert all(set(p) == {'chat_id', 'text', 'disable_web_page_preview'} for p in payloads)
    assert all(r['status'] == 'sent' and r['channel'] == 'telegram' for r in sent)
    assert len(tools.seal()['notifications']) == 2


@pytest.mark.parametrize('text', ['', ' ', 'x' * 1001, 'https://t.me/somewhere', 'tg://resolve?domain=elsewhere',
    'telegram.me/join', 'contact @another_chat', 'text\x00bad'])
def test_notification_limits_and_chat_links(realm, text):
    approve_inspector(realm)
    tools = ManagedTools(realm, 'inspector', inspector=True)
    with pytest.raises(ValueError):
        tools.call('notify_owner', {'text': text})
    assert not tools.notifications
    with pytest.raises(ValueError):
        tools.call('notify_owner', {'text': 'valid', 'chat_id': 'other'})


def test_muted_delivery_and_desktop_fallback_are_audited(realm, monkeypatch):
    approve_inspector(realm)
    tools = ManagedTools(realm, 'inspector', inspector=True)
    monkeypatch.setattr(telegram, 'ready', lambda: True)
    assert tools.call('notify_owner', {'text': 'x' * 1000})['status'] == 'suppressed'
    monkeypatch.setattr(telegram, 'ready', lambda: False)
    toasted = []
    monkeypatch.setattr(notify, 'toast', lambda title, body, **kw: toasted.append(body) or True)
    assert tools.call('notify_owner', {'text': 'Desktop review'})['status'] == 'dispatched'
    assert toasted == ['Desktop review']
    with pytest.raises(ValueError, match='two'):
        tools.call('notify_owner', {'text': 'third'})
    audit = tools.seal()
    assert [n['channel'] for n in audit['notifications']] == ['telegram', 'desktop']


def test_drafts_and_stopped_turns_cannot_use_inspector_owner_actions(realm):
    approve_inspector(realm)
    draft = ManagedTools(realm, 'writer', output=realm / 'drafts')
    for name, arguments in [('write_file', {'path': 'report.md', 'content': 'x'}),
                            ('notify_owner', {'text': 'x'})]:
        with pytest.raises(ValueError):
            draft.call(name, arguments)
        stopped = ManagedTools(realm, 'inspector', inspector=True, cancelled=lambda: True)
        with pytest.raises(ValueError, match='stopped'):
            stopped.call(name, arguments)
        assert not stopped.writes and not stopped.notifications


def test_inspector_report_contains_host_actions_even_when_provider_fails(realm, tmp_path, monkeypatch):
    from armada import runner
    from armada.execution import TurnCoordinator, TurnRequest
    from armada.request_context import RunContext
    job = approved_job(realm, tmp_path / 'approved')
    monkeypatch.setattr(notify, 'owner_message', lambda *args: {'ok': False, 'channel': 'telegram', 'status': 'failed'})
    class Review(DraftEngine):
        def run_stream(self, **kw):
            assert not self.writable_roots and not self.network_access and not self.allowed_mcp_ids
            broker = self.managed_tools
            assert broker.job == job
            broker.call('write_file', {'path': str(tmp_path / 'approved/review.md'), 'content': '12.34'})
            broker.call('notify_owner', {'text': 'Exact review <data>\n12.34'})
            for name in ('run_skill', 'shell', 'web', 'publish', 'save_job'):
                with pytest.raises(ValueError):
                    broker.call(name, {})
            return RunResult(ok=False, error='synthetic provider failure')
    monkeypatch.setattr(runner, '_select_engine', lambda *a, **kw: Review())
    request = TurnRequest(RunContext.capture(realm, 'inspector', job_history.thread_name('review')), 'Review',
        task='review', job=job)
    report = TurnCoordinator(request).run()
    audit = report['inspector']
    assert report['status'] == 'error' and audit['notifications'][0]['text'] == 'Exact review <data>\n12.34'
    assert audit['notifications'][0]['status'] == 'failed'
    assert len(audit['writes']) == 1
    transcript = util.read_json_state(realm / 'agents/inspector/runs/output' / report['output_file'])
    assert transcript['inspector'] == audit and transcript['outputs'][0]['path'] == audit['writes'][0]['path']
    assert inspection.artifacts(realm)[0]['path'] == audit['writes'][0]['path']
    from armada.webui.jobresults import result_html
    html = result_html(report, transcript)
    assert 'Owner messages' in html and '&lt;data&gt;' in html and '<data>' not in html


def test_unpacked_export_matches_anonymous_zip_before_and_after_reveal(realm):
    approve_inspector(realm)
    pair = dry_run_pairs.start(realm, 'writer', 'digest', 'gpt-6-sol', 'claude-sonnet-5', engines=(DraftEngine(), DraftEngine()))
    _wait_pair(realm, pair)
    tools = ManagedTools(realm, 'inspector', inspector=True)
    for revealed in (False, True):
        if revealed:
            tools.call('record_scores', {'pair_id': pair['pair_id'], 'score_a': 80, 'score_b': 90})
        result = tools.call('export_dry_run_pair', {'pair_id': pair['pair_id'], 'unpacked': True})
        folder = Path(result['folder'])
        assert (folder / 'A').is_dir() and (folder / 'B').is_dir()
        with zipfile.ZipFile(result['path']) as archive:
            assert {str(p.relative_to(folder)).replace('\\', '/') for p in folder.rglob('*') if p.is_file()} == set(archive.namelist())
            for name in archive.namelist():
                data = (folder / name).read_bytes()
                assert data == archive.read(name)
                assert b'gpt-6-sol' not in data and b'claude-sonnet-5' not in data
        assert len(result['files']) == len(archive.namelist())
    with pytest.raises(ValueError):
        tools.call('export_dry_run_pair', {'pair_id': pair['pair_id'], 'unpacked': 'true'})
    assert not list(folder.parent.glob('.pair-*'))


def test_unpacked_export_failure_preserves_existing_zip_and_hides_partial_folder(realm, monkeypatch):
    approve_inspector(realm)
    pair = dry_run_pairs.start(realm, 'writer', 'digest', 'gpt-6-sol', 'claude-sonnet-5', engines=(DraftEngine(), DraftEngine()))
    _wait_pair(realm, pair)
    tools = ManagedTools(realm, 'inspector', inspector=True)
    exported = tools.call('export_dry_run_pair', {'pair_id': pair['pair_id']})
    archive = Path(exported['path']); before = archive.read_bytes()
    write = zipfile.ZipFile.writestr
    count = 0
    def fail(self, *args, **kwargs):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError('synthetic interrupted export')
        return write(self, *args, **kwargs)
    monkeypatch.setattr(zipfile.ZipFile, 'writestr', fail)
    with pytest.raises(OSError, match='interrupted'):
        tools.call('export_dry_run_pair', {'pair_id': pair['pair_id'], 'unpacked': True})
    assert archive.read_bytes() == before
    assert not list(archive.parent.glob('.pair-*'))
    assert not [p for p in archive.parent.glob('blind-pair-*') if p.is_dir()]
