"""Real command trees must finish before timeout/cancellation is reported terminal."""
import json
import os
from pathlib import Path
import sys
import threading
import time

import pytest

from armada import execution, runner
from armada.engine import process
from test_process_lifecycle import alive


def command(code, **kwargs):
    return process.supervise_command([sys.executable, '-u', '-c', code], timeout=kwargs.pop('timeout',5), **kwargs)


def test_raw_command_preserves_whitespace_arguments_directory_and_environment(tmp_path):
    result = process.supervise_command([sys.executable,'-c',
        'import os,sys;print(repr(sys.argv[1]));print(os.getcwd());print(os.environ["PROBE"]);'
        'sys.stdout.write("\\n  tail  \\n");print("error detail",file=sys.stderr);assert sys.stdin.read()==""',
        'argument with spaces'], timeout=5,cwd=tmp_path,env={**os.environ,'PROBE':'kept'})
    assert result.returncode == 0 and not result.error
    assert result.stdout == f"'argument with spaces'\n{tmp_path}\nkept\n\n  tail  \n"
    assert result.stderr == 'error detail\n'


@pytest.mark.parametrize('channel',['stdout','stderr','blank'])
def test_output_flood_is_bounded_and_cannot_be_success(channel):
    output = "sys.stderr" if channel == 'stderr' else 'sys.stdout'
    char = "\\n" if channel == 'blank' else 'x'
    started = time.monotonic()
    result = command(f'import sys\nwhile True: {output}.write("{char}"*65536);{output}.flush()')
    assert result.error and 'limit' in result.error
    assert len(result.stdout.encode()) <= process.MAX_COMMAND_STDOUT
    assert len(result.stderr.encode()) <= process.MAX_COMMAND_STDERR
    assert time.monotonic()-started < 8


@pytest.mark.parametrize('ending',['timeout','cancel','parent-exit'])
def test_parent_child_grandchild_and_inherited_pipes_are_owned(tmp_path,ending):
    pid_file, marker = tmp_path/'descendants.json',tmp_path/'must-not-appear'
    grandchild = f'import time;from pathlib import Path;time.sleep(15);Path({str(marker)!r}).write_text("orphan")'
    child = ('import subprocess,sys,os,json,time;from pathlib import Path;'
        f'p=subprocess.Popen([sys.executable,"-c",{grandchild!r}]);'
        f'proof=Path({str(pid_file)!r});pending=proof.with_suffix(".pending");'
        'pending.write_text(json.dumps([os.getpid(),p.pid]));pending.replace(proof);time.sleep(30)')
    parent = ('import subprocess,sys,time;from pathlib import Path;'
        f'subprocess.Popen([sys.executable,"-c",{child!r}]);\n'
        f'while not Path({str(pid_file)!r}).exists():time.sleep(.01)\n'
        + ('pass' if ending == 'parent-exit' else 'time.sleep(30)'))
    handles, results = [], []
    worker = threading.Thread(target=lambda:results.append(command(parent,timeout=1.5 if ending=='timeout' else 6,
                                                                   on_proc=handles.append)))
    worker.start()
    try:
        until = time.monotonic()+5
        while not pid_file.exists() and time.monotonic()<until:time.sleep(.01)
        assert pid_file.exists()
        pids = json.loads(pid_file.read_text())
        if ending == 'cancel': handles[0].kill()
        worker.join(10)
        assert not worker.is_alive()
        result = results[0]
        assert result.timed_out if ending=='timeout' else result.cancelled if ending=='cancel' else not result.error
        assert all(not alive(pid) for pid in pids), 'A descendant outlived terminal completion'
        assert not marker.exists()
    finally:
        if worker.is_alive() and handles:handles[0].kill()
        worker.join(10)


def test_command_job_cancellation_is_registered_and_persisted(tmp_path):
    (tmp_path/'realm.json').write_text('{}')
    agent = tmp_path/'agents/a'
    (agent/'jobs').mkdir(parents=True)
    started = tmp_path/'started'
    job = {'kind':'command','run':[sys.executable,'-c',
        f'import time;from pathlib import Path;Path({str(started)!r}).touch();time.sleep(30)']}
    results = []
    worker = threading.Thread(target=lambda:results.append(runner._run_command(tmp_path,'a','probe',job,agent)))
    worker.start()
    key = None
    try:
        until=time.monotonic()+5
        while not started.exists() and time.monotonic()<until:time.sleep(.01)
        assert started.exists()
        with execution.RUNS_LOCK:
            key=next(k for k,r in execution.ACTIVE_RUNS.items() if Path(r.context.realm.root)==tmp_path)
        execution.RunSession.cancel(key)
        worker.join(10)
        assert not worker.is_alive()
        assert results[0]['result']['execution']=='cancelled'
        assert key not in execution.ACTIVE_RUNS
        assert not list((agent/'runs/.running').glob('_chat-*.json'))
    finally:
        if key:execution.RunSession.cancel(key)
        worker.join(10)
