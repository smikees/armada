"""A sandbox child must finish exiting before the supervisor cleans up its job."""
import os
from types import SimpleNamespace

import pytest

from armada.engine.skill_sandbox import NativeProcess


def native_process(api):
    process = NativeProcess.__new__(NativeProcess)
    process.api, process._handle, process.args = api, 42, ['synthetic']
    process.returncode = None
    return process


def test_published_exit_code_does_not_mean_process_finished():
    signal = {'ready': False}
    reads = []
    def exit_code(handle, pointer):
        reads.append(handle)
        pointer._obj.value = 0
        return True
    process = native_process(SimpleNamespace(
        WaitForSingleObject=lambda handle, timeout: 0 if signal['ready'] else 258,
        GetExitCodeProcess=exit_code))
    assert process.poll() is None and not reads
    signal['ready'] = True
    assert process.poll() == 0
    signal['ready'] = False  # A cached terminal code never queries a closing handle.
    assert process.poll() == 0 and reads == [42]


@pytest.mark.parametrize('code', [0, 17, 259])
def test_signaled_process_reports_exact_exit_status(code):
    def exit_code(handle, pointer):
        pointer._obj.value = code
        return True
    process = native_process(SimpleNamespace(WaitForSingleObject=lambda *args: 0,
                                             GetExitCodeProcess=exit_code))
    assert process.poll() == code
    assert process.wait(timeout=0) == code


@pytest.mark.skipif(os.name != 'nt', reason='Windows error conversion')
@pytest.mark.parametrize('operation', ['wait', 'exit_code'])
def test_native_poll_errors_never_report_success(operation):
    from armada.engine import skill_sandbox
    def failed(*args):
        skill_sandbox.C.set_last_error(5)
        return 0xFFFFFFFF if operation == 'wait' else False
    process = native_process(SimpleNamespace(
        WaitForSingleObject=failed if operation == 'wait' else lambda *args: 0,
        GetExitCodeProcess=failed))
    with pytest.raises(OSError):
        process.poll()
    assert process.returncode is None
