"""Release validation must fail before publishing on stale or unsuccessful evidence."""
import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from tools import publish_release, release_gate
from tools import sandbox_test


def test_process_guard_preserves_the_subclass_contract():
    class Child(subprocess.Popen):
        pass
    assert issubclass(Child, subprocess.Popen)


def test_vm_report_sharing_violation_can_be_retried(tmp_path, monkeypatch):
    report = tmp_path/'report.txt'
    report.write_text('DONE',encoding='utf-8')
    with monkeypatch.context() as patch:
        def locked(*a,**kw): raise PermissionError('VM is writing')
        patch.setattr(Path,'read_text',locked)
        assert sandbox_test.read_report(report) == ''
    assert sandbox_test.read_report(report) == 'DONE'


@pytest.mark.parametrize('text,passed', [('SHA256: exact\nPASS ok\nDONE',True),
    ('SHA256: stale\nPASS ok\nDONE',False),('SHA256: exact\nFAIL dependency\nDONE',False),
    ('SHA256: exact\nPASS incomplete',False)])
def test_vm_evidence_requires_completion_success_and_exact_artifact(tmp_path,text,passed):
    assert sandbox_test.save_evidence(tmp_path,Path('setup.exe'),'exact',tmp_path/'report.txt',text) == passed
    assert json.loads((tmp_path/'evidence.json').read_text())['passed'] == passed


@pytest.mark.parametrize('method', ['connect', 'connect_ex'])
def test_default_tests_refuse_external_connections(method):
    with socket.socket() as client, pytest.raises(pytest.fail.Exception, match='non-loopback'):
        getattr(client, method)(('203.0.113.1', 443))


@pytest.mark.parametrize('command', [['claude.exe'], ['codex.cmd'], ['agy'],
    ['node.exe', 'C:/temp/node_modules/@openai/codex/bin/codex.js']])
def test_default_tests_refuse_provider_launches(command):
    with pytest.raises(pytest.fail.Exception, match='real provider'):
        subprocess.Popen(command)


def test_gate_uses_a_private_home_and_propagates_failure(monkeypatch):
    monkeypatch.setattr(release_gate, 'verify_dependencies', lambda: None)
    def fail(command, **kw):
        assert kw['env']['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] == '1'
        assert kw['env']['ARMADA_NO_EXTERNAL_NOTIFY'] == '1'
        assert 'ARMADA_TEST_REALM' not in kw['env']
        assert Path(kw['env']['HOME']).is_dir()
        assert kw['check'] and 'error::pytest.PytestUnhandledThreadExceptionWarning' in command
        raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(subprocess, 'run', fail)
    with pytest.raises(subprocess.CalledProcessError): release_gate.run()


@pytest.mark.parametrize('ci', [[], [{'head_sha':'old','event':'push','status':'completed','conclusion':'success'}],
    [{'head_sha':'current','event':'push','status':'completed','conclusion':'failure'}],
    [{'head_sha':'current','event':'pull_request','status':'completed','conclusion':'success'}]])
def test_publish_refuses_absent_stale_failed_or_pr_only_ci(monkeypatch, ci):
    monkeypatch.setitem(sys.modules, 'release_gate', release_gate)
    monkeypatch.setattr(release_gate, 'run', lambda: None)
    def fake_run(*args, **kw):
        if args[:2] == ('git', 'status'): return ''
        if args[:2] == ('git', 'fetch'): return ''
        if args[:2] == ('git', 'rev-parse'): return 'current'
        if 'api' in args: return json.dumps({'workflow_runs':ci})
        pytest.fail('Publishing must not be reached')
    monkeypatch.setattr(publish_release, '_run', fake_run)
    wait=publish_release.wait_for_ci
    monkeypatch.setattr(publish_release,'wait_for_ci',lambda sha:wait(sha,timeout=0))
    with pytest.raises(SystemExit, match='Windows CI'): publish_release.main()


def test_publish_waits_for_pending_exact_source_ci(monkeypatch):
    responses=iter(['in_progress','completed'])
    def read(*args):
        status=next(responses)
        return json.dumps({'workflow_runs':[{'head_sha':'current','event':'push',
            'status':status,'conclusion':'success' if status=='completed' else None}]})
    sleeps=[]
    monkeypatch.setattr(publish_release,'_run',read)
    monkeypatch.setattr(publish_release.time,'sleep',sleeps.append)
    publish_release.wait_for_ci('current')
    assert len(sleeps)==1
