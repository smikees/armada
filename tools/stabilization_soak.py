"""Bounded synthetic multi-realm load. Never accepts an existing realm or account."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
import threading
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def run(output, rounds=30):
    """Twelve readers, three writers and bounded admission; output has no fixture paths."""
    sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
    with tempfile.TemporaryDirectory(prefix='armada-stabilization-') as directory, ExitStack() as stack:
        home = Path(directory)
        env = {name: str(home / name) for name in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA')}
        for value in env.values():
            Path(value).mkdir()
        env.update(ARMADA_DATA_DIR=str(home / 'account'), ARMADA_NO_MODEL_SYNC='1', ARMADA_NO_EXTERNAL_NOTIFY='1')
        stack.enter_context(patch.dict(os.environ, env))
        from golden_support import build_fixture
        from armada import util, instance, reader, thread_windows, execution_admission as admission, realm_export
        from armada.policy_tools import PolicyTools, PolicyAudit
        from armada.request_context import RunContext
        from armada.threads import Thread
        stack.enter_context(patch.object(util, 'data_dir', lambda: home / 'account'))
        stack.enter_context(patch.object(instance, '_account_directory', lambda: home / 'account'))
        stack.enter_context(patch.object(Path, 'home', lambda: home))
        roots, guards, audits = [], [], []
        for n in range(3):
            root = Path(build_fixture(home / f'realm-{n}'))
            util.mutate_json(root / 'realm.json', lambda d: d.update(read_only=['skills/**']))
            util.mutate_json(root / 'agents/captain/agent.json', lambda d: d.update(
                write_scope=['output/**', 'agents/captain/**']))
            skill = root / 'skills/soak/main.py'
            skill.parent.mkdir(parents=True, exist_ok=True)
            util.write_text_atomic(skill, 'synthetic protected code\n')
            audit = PolicyAudit(root, 'captain')
            guard = PolicyTools(root, 'captain', audit)
            audits.append(audit); guards.append(guard); roots.append(root)
            audit.offer(t['name'] for t in guard.tools())
            # Substantial but bounded histories; long-history percentiles have a separate gate.
            th = Thread(root / 'agents/captain', 'main')
            th.dir.mkdir(parents=True, exist_ok=True)
            util.write_text_atomic(th.msgs, ''.join(json.dumps({'role': 'user', 'content': f'realm-{n} message {i}',
                'ts': '2026-11-08T10:00:00'})+'\n' for i in range(300)))
        before = [(r / 'agents/captain/agent.json').read_bytes() for r in roots]
        timings, counts, lock = [], Counter(), threading.Lock()
        barrier = threading.Barrier(15)

        def read_window(n):
            root = roots[n // 4]
            barrier.wait(timeout=20)
            revision = None
            for _ in range(rounds):
                started = time.perf_counter()
                state = thread_windows.state(root, 'captain', 'main', revision)
                revision = state['revision']
                check(bool(reader.roster(root)), 'Concurrent realm roster became empty')
                with lock:
                    timings.append((time.perf_counter()-started)*1000)
                    counts['reads'] += 1

        def write_realm(n):
            root, guard = roots[n], guards[n]
            barrier.wait(timeout=20)
            for i in range(rounds):
                guard.call('write_file', {'path': f'output/{i}.txt', 'content': f'{n}:{i}'})
                for target in ('skills/soak/main.py', 'agents/captain/agent.json'):
                    try:
                        guard.call('write_file', {'path': target, 'content': 'forbidden'})
                    except PermissionError:
                        with lock:
                            counts['refusals'] += 1
                    else:
                        raise RuntimeError('Protected write unexpectedly succeeded')
                th = Thread(root / 'agents/captain', 'main')
                th.append(f'Synthetic request {i}', f'Concurrent synthetic response {i}')
                ctx = RunContext.capture(root, 'captain', f'soak-{n}')
                with admission.scope(ctx, ('claude', 'codex', 'gemini')[n]):
                    rows = [r for r in admission.snapshot() if r['state'] == 'running']
                    check(len(rows) <= admission.TOTAL, 'Execution capacity exceeded')
                    check(max(Counter(r['realm'] for r in rows).values(), default=0) <= admission.PER_REALM,
                          'Realm capacity exceeded')
                    check(max(Counter(r['provider'] for r in rows).values(), default=0) <= admission.PER_PROVIDER,
                          'Provider capacity exceeded')
                with lock:
                    counts['writes'] += 1
                    counts['admissions'] += 1

        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=15) as pool:
            futures = [pool.submit(read_window, i) for i in range(12)] + [pool.submit(write_realm, i) for i in range(3)]
            for future in futures:
                future.result(timeout=300)
        check(not admission.snapshot(), 'Admission ownership leaked after work completed')
        check(counts['reads'] == 12*rounds and counts['writes'] == 3*rounds and counts['refusals'] == 6*rounds,
              'Incomplete load evidence')
        for n, root in enumerate(roots):
            check((root / 'agents/captain/agent.json').read_bytes() == before[n], 'Control record changed')
            check((root / 'skills/soak/main.py').read_text() == 'synthetic protected code\n', 'Protected skill changed')
            for i in range(rounds):
                check((root / f'output/{i}.txt').read_text() == f'{n}:{i}', 'Output lost or crossed realm boundary')
            check(len(audits[n].report()['denied_attempts']) == 2*rounds, 'Refusal audit lost attempts')
            exported = realm_export.export(root, home / 'exports')
            check(exported.get('ok'), f'Export failed: {exported}')
            verified = realm_export.verify(exported['path'])
            check(verified.get('ok'), 'Export verification failed')
            target = home / f'restored-{n}'
            restored = realm_export.restore_copy(exported['path'], target)
            check(restored.get('ok') and restored.get('paused'), f'Restore failed: {restored}')
            check(util.read_json_state(target / 'realm.json')['archived'], 'Restored realm not paused')
            check(all(not util.read_json_state(p).get('enabled') for p in target.glob('agents/*/jobs/*.json')),
                  'Restored business job was enabled')
            check((target / 'agents/captain/agent.json').read_bytes() == before[n], 'Restored policy changed')
            counts['restores'] += 1
        timings.sort()
        result = {'ok': True, 'realms': 3, 'concurrent_readers': 12, 'concurrent_writers': 3,
                  'rounds': rounds, 'counts': dict(counts), 'elapsed_seconds': round(time.perf_counter()-started, 2),
                  'read_p50_ms': round(statistics.median(timings), 2),
                  'read_p95_ms': round(timings[min(len(timings)-1, int(len(timings)*.95))], 2),
                  'limits': 'Logical reader load, not twelve native windows; no model or external connector calls.'}
        util.write_json_atomic(output, result)
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--rounds', type=int, choices=range(1, 101), default=30)
    args = parser.parse_args()
    print(json.dumps(run(args.output.resolve(), args.rounds), indent=2))
