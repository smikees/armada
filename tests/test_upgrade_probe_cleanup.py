"""Release-test helpers must not outlive their isolated process tree."""
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest

from armada import restart_worker as worker
from armada.background import process_options
from tools import upgrade_probe


@pytest.mark.skipif(os.name != 'nt', reason='Windows Job Object ownership')
@pytest.mark.parametrize('failure', [False, True])
def test_probe_reaps_detached_descendants_without_status_files(tmp_path, failure):
    receipt = tmp_path/'descendant.json'
    script = tmp_path/'probe.py'
    script.write_text('import subprocess,sys,json\nfrom pathlib import Path\n'
        'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(120)"],creationflags=0x08000000)\n'
        'Path(sys.argv[1]).write_text(json.dumps({"pid":p.pid}))\n')
    unrelated = subprocess.Popen([sys._base_executable, '-c', 'import time;time.sleep(120)'],
                                  **process_options())
    descendant = None
    try:
        def exercise():
            nonlocal descendant
            with upgrade_probe.probe_process([sys._base_executable, str(script), str(receipt)],
                                             tmp_path, dict(os.environ)) as process:
                process.wait(timeout=10)  # Parent exited; no monitor/instance status survives.
                descendant = json.loads(receipt.read_text())['pid']
                assert worker.alive(descendant)
                receipt.unlink()
                if failure: raise RuntimeError('Injected probe failure')
        if failure:
            with pytest.raises(RuntimeError, match='Injected probe failure'): exercise()
        else:
            exercise()
        assert not worker.alive(descendant), 'Detached test helpers must be gone before cleanup returns.'
        assert unrelated.poll() is None, 'Test cleanup must leave other processes untouched.'
    finally:
        unrelated.kill(); unrelated.wait(timeout=10)


@pytest.mark.skipif(os.name != 'nt', reason='Windows suspended launch')
def test_probe_assignment_failure_closes_the_suspended_process(tmp_path, monkeypatch):
    from armada.engine import windows_job
    tree = Mock()
    children = []
    def fail(process):
        children.append(process)
        raise OSError('Cannot assign test process')
    tree.attach_and_resume.side_effect = fail
    monkeypatch.setattr(windows_job, 'WindowsJob', lambda:tree)
    with pytest.raises(OSError, match='Cannot assign test process'):
        with upgrade_probe.probe_process([sys._base_executable, '-c', 'raise AssertionError("resumed")'],
                                         tmp_path, dict(os.environ)):
            pytest.fail('Unowned process must never run')
    tree.close.assert_called_once()
    assert children[0].poll() is not None


@pytest.mark.skipif(os.name != 'nt', reason='Windows failure dialog')
def test_probe_mutes_dialog_but_retains_restart_failure(tmp_path, monkeypatch, caplog):
    plan = {'log':str(tmp_path/'startup.log'), 'status':str(tmp_path/'status.json'), 'nonce':'failure-test'}
    path = tmp_path/'plan.json'; path.write_text(json.dumps(plan))
    monkeypatch.setattr(sys, 'argv', ['restart_worker.py', str(path)])
    monkeypatch.setenv('ARMADA_NO_EXTERNAL_NOTIFY', '1')
    monkeypatch.setattr(worker, 'supervise', Mock(side_effect=OSError('Specific test failure')))
    monkeypatch.setattr(worker, 'ready_if_reachable', lambda plan:False)
    monkeypatch.setattr(worker, 'recover_failure', lambda *a:False)
    dialog = Mock()
    monkeypatch.setattr(worker.ctypes.windll.user32, 'MessageBoxW', dialog)
    # main redirects process streams; restore the test harness after invocation.
    with monkeypatch.context() as streams:
        streams.setattr(sys, 'stdout', sys.stdout); streams.setattr(sys, 'stderr', sys.stderr)
        worker.main()
    state = json.loads(Path(plan['status']).read_text())
    assert state['phase'] == 'error' and state['message'] == 'Specific test failure'
    assert state['startup_log'] == plan['log'] and Path(plan['log']).exists()
    assert 'Specific test failure' in caplog.text
    dialog.assert_not_called()
    monkeypatch.delenv('ARMADA_NO_EXTERNAL_NOTIFY')
    worker.failure_dialog('Real restart failure')
    dialog.assert_called_once_with(None, 'Real restart failure', 'ARMADA restart needs attention', 0x10)
