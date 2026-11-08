"""Repeatable synthetic load, performance and native regression gate (Windows only)."""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from armada import util

# Gross-regression ceilings, not a UX SLA. See STABILIZATION_CONTRACTS.md.
PERFORMANCE_BUDGETS = {'realm_warm': 100, 'usage_warm': 500, 'unchanged_poll': 250,
                       'four_windows': 1000, 'metadata': 100}
FAULT_TESTS = ['test_http_limits.py', 'test_execution_admission.py', 'test_dispatch.py',
               'test_record_health.py', 'test_verified_exports.py', 'test_access_policy.py',
               'test_access_preview.py', 'test_section_snapshots.py']


def validate_performance(report):
    """Missing, nonfinite or over-budget evidence cannot pass."""
    import math
    for name, budget in PERFORMANCE_BUDGETS.items():
        value = report.get(name, {}).get('p95_ms')
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= budget:
            raise ValueError(f'{name} p95 missing/invalid or above {budget} ms: {value}')
    cold = report.get('realm_cold_ms')
    if type(cold) not in (int, float) or not math.isfinite(cold) or not 0 <= cold <= 10000:
        raise ValueError('Cold realm read missing/invalid or above 10 seconds')


def execute(command, log, env, timeout):
    """Only this gate's child process tree may be stopped on timeout."""
    with log.open('w', encoding='utf-8') as stream:
        proc = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            code = proc.wait(timeout=timeout)
        except BaseException:
            if proc.poll() is None:
                subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True, timeout=20)
                proc.wait(timeout=20)
            raise
    if code:
        raise RuntimeError(f'{log.name}: child exited {code}; inspect its synthetic log')


def run(output):
    output = output.resolve()
    # Never leave a previous successful summary behind after an early refusal.
    util.write_json_atomic(output, {'ok': False, 'status': 'preflight'})
    if os.name != 'nt':
        raise RuntimeError('The complete stabilization gate requires Windows and WebView2')
    from tools.release_gate import verify_dependencies
    verify_dependencies()
    evidence = output.parent / ('stabilization-' + datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    evidence.mkdir(parents=True, exist_ok=False)
    report = {'ok': False, 'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'source_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()),
              'evidence_directory': evidence.name, 'steps': [], 'performance_budgets_ms': PERFORMANCE_BUDGETS}
    started = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix='armada-stabilization-gate-') as directory:
            home = Path(directory)
            env = dict(os.environ)
            for name in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA'):
                env[name] = str(home / name)
                Path(env[name]).mkdir()
            env.update(ARMADA_DATA_DIR=str(home / 'account'), ARMADA_NO_MODEL_SYNC='1',
                       ARMADA_NO_EXTERNAL_NOTIFY='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
            for name in ('ARMADA_TEST_REALM', 'ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'GEMINI_API_KEY',
                         'GOOGLE_API_KEY', 'RESEND_API_KEY', 'ARMADA_RESEND_KEY', 'CODEX_HOME', 'XDG_CONFIG_HOME'):
                env.pop(name, None)
            steps = [('faults', ['-m', 'pytest', '-o', 'addopts=', '-q',
                       '-W', 'error::pytest.PytestUnhandledThreadExceptionWarning',
                       '--basetemp', str(home / 'tests'), *['tests/'+n for n in FAULT_TESTS]], 300, False),
                     ('soak', ['tools/stabilization_soak.py', '--rounds', '30'], 300, True),
                     ('history', ['tools/history_benchmark.py'], 180, True),
                     *[(f'windows-{i+1}', ['tools/thread_window_probe.py'], 240, True) for i in range(3)],
                     ('page-work', ['tools/page_work_probe.py'], 240, True),
                     ('owner-workflows', ['tools/owner_workflow_probe.py'], 240, True)]
            for name, args, timeout, has_report in steps:
                result_path = evidence / f'{name}.json'
                if has_report:
                    args += [str(result_path)] if name == 'history' else ['--output', str(result_path)]
                print(f'Starting {name}', flush=True)
                execute([sys.executable, *args], evidence / f'{name}.log', env, timeout)
                result = json.loads(result_path.read_text(encoding='utf-8')) if has_report else {}
                if name == 'history':
                    validate_performance(result)
                elif has_report and result.get('ok') is not True:
                    raise ValueError(f'{name} did not report success')
                if name == 'soak' and result['read_p95_ms'] > 5000:
                    raise ValueError('Concurrent soak read p95 exceeded 5 seconds')
                report['steps'].append({'name': name, 'ok': True, 'result': result})
                util.write_json_atomic(output, report)
                print(f'Passed {name}', flush=True)
        report['ok'] = True
        return report
    except BaseException as exc:
        report['error'] = str(exc)
        raise
    finally:
        report['elapsed_seconds'] = round(time.monotonic()-started, 2)
        util.write_json_atomic(output, report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    print(json.dumps(run(parser.parse_args().output), indent=2))
