"""Paired drafts share frozen inputs; A/B identity is private until scores are committed."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
import secrets
import shutil
import tempfile
import uuid
import zipfile

from . import appconfig, draft_inputs, inspection, util

KEY = 'dry_run_pairs'


def _key(root, pair_id):
    return str(Path(root).resolve()).casefold() + '|' + util.safe_seg(pair_id, 'pair')


def _private(root, pair_id):
    value = appconfig.get(KEY, {}).get(_key(root, pair_id))
    if not isinstance(value, dict):
        raise ValueError('No paired comparison with this ID in this realm.')
    return value


def directory(root, pair_id):
    return inspection.checked_path(Path(root).resolve() / '.armada' / 'dry-run-pairs' /
                                  util.safe_seg(pair_id, 'pair'), [Path(root).resolve()])


def _result_dir(root, pair_id):
    key = hashlib.sha256(_key(root, pair_id).encode()).hexdigest()
    return inspection.checked_path(appconfig._path().parent / 'draft-comparisons' / key, [appconfig._path().parent])


def start(root, agent, job_id, model_a, model_b, *, requested_by='user', effort_a=None, effort_b=None, engines=None):
    from . import dry_runs, memory, realmops, runner
    from .engine.selection import model_provider
    root = Path(root).resolve()
    util.safe_seg(agent, 'agent'); util.safe_seg(job_id, 'job')
    if requested_by != 'user' and not inspection.enabled(root, requested_by):
        raise ValueError('Inspector access is not enabled for this agent.')
    available = {m['id'] for m in dry_runs.models(root)}
    if not isinstance(model_a, str) or not isinstance(model_b, str) or model_a not in available or model_b not in available:
        raise ValueError('Choose two available models for this paired test.')
    if any(e is not None and e not in (*runner._EFFORT_LEVELS, 'auto') for e in (effort_a, effort_b)):
        raise ValueError('Choose a supported effort or auto.')
    with dry_runs._LOCK, util.file_lock(dry_runs.base(root) / 'admission', validate_state=False):
        realmops.assert_active(root)
        live = [p for p in dry_runs.base(root).glob('*/*/*/run.json') if (lambda r:
            r.get('status') in ('queued', 'running') and util.pid_alive(r.get('owner_pid', 0)))(dry_runs._read_info(root, p))]
        if live:
            raise ValueError('A paired comparison needs both dry-run slots. Wait for active tests to finish.')
        jp = inspection.checked_path(root / 'agents' / agent / 'jobs' / (job_id + '.json'), [root], must_exist=True)
        job = util.read_json_state(jp); job.setdefault('id', job_id)
        days = dry_runs.settings(job)
        if dry_runs.is_command(job):
            raise ValueError('Blind model comparisons require an agent job.')
        ad = root / 'agents' / agent
        cfg = util.read_json_state(ad / 'agent.json')
        context = (cfg, memory.assemble_core(root, ad, cfg))
        pair_id = uuid.uuid4().hex
        folder = directory(root, pair_id)
        folder.mkdir(parents=True)
        try:
            manifest = draft_inputs.freeze(root, agent, job, folder / 'inputs')
        except BaseException:
            folder.rmdir()
            raise
        candidates = [(model_a, effort_a, (engines or (None, None))[0]),
                      (model_b, effort_b, (engines or (None, None))[1])]
        if secrets.randbits(1):
            candidates.reverse()
        private = {'pair_id': pair_id, 'agent': agent, 'job': job_id, 'requested_by': requested_by,
            'started': dt.datetime.now(dt.timezone.utc).isoformat(), 'keep_days': days,
            'mapping': {label: {'model': item[0], 'provider': model_provider(item[0]), 'effort': item[1]}
                        for label, item in zip(('A', 'B'), candidates)}, 'runs': {}, 'scores': None}
        inspection._set(KEY, _key(root, pair_id), private)
        try:
            for label, (model, effort, engine) in zip(('A', 'B'), candidates):
                run = dry_runs.start(root, agent, job_id, model, requested_by=requested_by, effort=effort,
                    engine=engine, _admitted=True, _frozen=folder / 'inputs', _job=job,
                    _pair=(pair_id, label), _context=context)
                private['runs'][label] = run['run_id']
                inspection._set(KEY, _key(root, pair_id), private)
        except BaseException:
            for run_id in private['runs'].values():
                dry_runs.stop(root, agent, job_id, run_id)
            private['launch_error'] = 'Could not launch both candidates. Stop/wait and retry a new pair.'
            inspection._set(KEY, _key(root, pair_id), private)
            raise
        util.write_json_atomic(folder / 'pair.json', {'pair_id': pair_id, 'agent': agent, 'job': job_id,
            'started': private['started'], 'requested_by': requested_by, 'labels': ['A', 'B'],
            'input_files': len(manifest['files']), 'input_bytes': sum(f['bytes'] for f in manifest['files'])})
        return read(root, pair_id)


def paired_run(root, run_id):
    prefix = str(Path(root).resolve()).casefold() + '|'
    return next((p['pair_id'] for key, p in appconfig.get(KEY, {}).items()
                 if key.startswith(prefix) and run_id in p.get('runs', {}).values()), None)


def anonymize(root, info, text):
    from . import models
    mapping = _private(root, info['pair_id'])['mapping']
    ids = {m['model'] for m in mapping.values()}
    names = ids | {label for mid, label in models.options(root) if mid in ids}
    import re
    for name in sorted(names, key=len, reverse=True):
        text = re.sub(re.escape(name), '[model withheld]', text, flags=re.IGNORECASE)
    return text


def private_result(root, info, transcript):
    from . import dry_runs
    folder = _result_dir(root, info['pair_id'])
    folder.mkdir(parents=True, exist_ok=True)
    util.write_json_atomic(folder / (info['pair_label'] + '.json'), {'run': {k: v for k, v in info.items() if not k.startswith('_')},
                                                                  'transcript': transcript})
    original = dry_runs.directory(root, info['agent'], info['job'], info['run_id']) / 'output'
    saved = folder / info['pair_label']
    saved.mkdir(exist_ok=True)
    for file in dry_runs.output_files(original.parent):
        target = saved / file['name']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(file['path'], target)


def anonymize_outputs(root, info, output):
    for path in output.rglob('*'):
        path = inspection.checked_path(path, [output], must_exist=True)
        if path.is_file():
            if path.stat().st_size > 1024 * 1024:
                continue
            try:
                text = path.read_text(encoding='utf-8-sig')
            except UnicodeDecodeError:
                continue
            util.write_text_atomic(path, anonymize(root, info, text))
    for path in sorted(output.rglob('*'), key=lambda p: len(p.parts), reverse=True):
        path = inspection.checked_path(path, [output], must_exist=True)
        name = anonymize(root, info, path.name)
        if name != path.name:
            target = path.with_name(name)
            if target.exists():
                target = path.with_name('[model withheld]-' + uuid.uuid4().hex[:12] + path.suffix)
            path.rename(target)


def read(root, pair_id):
    from . import dry_runs
    private = _private(root, pair_id)
    inspection.checked_path(directory(root, pair_id) / 'inputs' / 'manifest.json', [Path(root).resolve()], must_exist=True)
    result = {k: private[k] for k in ('pair_id', 'agent', 'job', 'requested_by', 'started', 'scores')}
    result['candidates'] = {}
    for label, run_id in private['runs'].items():
        run = dry_runs.read(root, private['agent'], private['job'], run_id)
        files = [] if run['status'] in ('queued', 'running') or not run.get('blind_ready') else dry_runs.output_files(dry_runs.directory(root, private['agent'], private['job'], run_id))
        result['candidates'][label] = {'status': run['status'], 'files': [{k: f[k] for k in ('name', 'bytes', 'sha256')} for f in files]}
        answer = next((f for f in files if f['name'] == 'final-answer.md'), None)
        if answer:
            result['candidates'][label]['final_answer'] = Path(answer['path']).read_text(encoding='utf-8')
    if private['scores'] is not None:
        result['mapping'] = private['mapping']
        for label in private['runs']:
            path = _result_dir(root, pair_id) / (label + '.json')
            if path.exists():
                data = util.read_json_state(inspection.checked_path(path, [_result_dir(root, pair_id)], must_exist=True))
                result['candidates'][label]['diagnostics'] = data['run']
                result['mapping'][label].update(actual_model=data['run'].get('actual_model'),
                    effective_effort=data['run'].get('effective_effort', 'auto'))
    result['limitations'] = 'ARMADA withholds model metadata and masks explicit selected model labels in UTF-8 artifacts up to 1 MiB. Binary artifacts are preserved; author metadata or writing style may suggest identity.'
    if private.get('launch_error'):
        result['error'] = private['launch_error']
    return result


def read_file(root, pair_id, label, name):
    from . import dry_runs
    private = _private(root, pair_id)
    if label not in ('A', 'B') or label not in private['runs']:
        raise ValueError('Choose candidate A or B.')
    run = dry_runs.read(root, private['agent'], private['job'], private['runs'][label])
    if run['status'] in ('queued', 'running'):
        raise ValueError('Wait for this candidate to finish before reading its anonymous files.')
    if not run.get('blind_ready'):
        raise ValueError('Anonymous artifacts could not be prepared. Record scores to reveal private diagnostics.')
    folder = dry_runs.directory(root, private['agent'], private['job'], private['runs'][label]) / 'output'
    return inspection.checked_path(folder / name, [folder], must_exist=True)


def record_scores(root, pair_id, score_a, score_b, notes=''):
    if any(type(s) not in (float, int) or not 0 <= s <= 100 for s in (score_a, score_b)):
        raise ValueError('Record finite scores from 0 to 100 for A and B.')
    if not isinstance(notes, str) or len(notes) > 20000:
        raise ValueError('Score notes must be text up to 20,000 characters.')
    state = read(root, pair_id)
    if len(state['candidates']) != 2 or any(c['status'] in ('queued', 'running') for c in state['candidates'].values()):
        raise ValueError('Wait for both candidates to finish before recording scores.')
    p = appconfig._path()
    with util.file_lock(p):
        cfg = appconfig._read()
        private = cfg[KEY][_key(root, pair_id)]
        if private['scores'] is not None:
            raise ValueError('Scores are already committed and cannot be changed after the identity reveal.')
        private['scores'] = {'A': score_a, 'B': score_b, 'notes': notes,
                             'recorded': dt.datetime.now(dt.timezone.utc).isoformat()}
        util.write_json_atomic(p, cfg)
    return read(root, pair_id)


def export(root, pair_id, output, *, unpacked=False):
    from . import dry_runs
    private = _private(root, pair_id)
    state = read(root, pair_id)
    if len(state['candidates']) != 2 or any(c['status'] in ('queued', 'running') for c in state['candidates'].values()):
        raise ValueError('Wait for both candidates before exporting the blind pair.')
    if any(not dry_runs.read(root, private['agent'], private['job'], rid).get('blind_ready') for rid in private['runs'].values()):
        raise ValueError('Anonymous artifacts could not be prepared. Export is unavailable for this pair.')
    if type(unpacked) is not bool:
        raise ValueError('unpacked must be true or false.')
    parent = inspection.checked_path(output, [Path(root).resolve()])
    output = inspection.checked_path(parent / ('blind-pair-' + pair_id + '.zip'), [parent])
    output.parent.mkdir(parents=True, exist_ok=True)
    # Unique staging names keep concurrent exporters from sharing a partial archive.
    temporary = inspection.checked_path(parent / ('.pair-' + uuid.uuid4().hex + '.tmp'), [parent])
    staging = None
    folder = None
    files = []
    try:
        if unpacked:
            staging = inspection.checked_path(tempfile.mkdtemp(prefix='.pair-', dir=parent), [parent])
            folder = inspection.checked_path(parent / ('blind-pair-' + pair_id + '-' + uuid.uuid4().hex[:12]), [parent])
            for label in ('A', 'B'):
                (staging / label).mkdir()
        def add(archive, name, data):
            archive.writestr(name, data)
            if staging:
                target = inspection.checked_path(staging / name, [staging])
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)  # Private staging; the complete tree is renamed atomically.
                files.append(str(folder / name))
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            manifest = util.read_json_state(directory(root, pair_id) / 'inputs' / 'manifest.json')
            add(archive, 'comparison.json', json.dumps({'pair_id': pair_id, 'labels': ['A', 'B'],
                'inputs': [{'sha256': f['sha256'], 'bytes': f['bytes']} for f in manifest['files']],
                'scoring': 'Review A and B; record scores 0–100 for both before requesting model identity.'}, indent=2).encode('utf-8'))
            for label, run_id in private['runs'].items():
                for file in dry_runs.output_files(dry_runs.directory(root, private['agent'], private['job'], run_id)):
                    data = Path(file['path']).read_bytes()
                    if len(data) <= 1024 * 1024:
                        try:
                            data = anonymize(root, {'pair_id': pair_id}, data.decode('utf-8-sig')).encode('utf-8')
                        except UnicodeDecodeError:
                            pass
                    add(archive, label + '/' + Path(file['name']).as_posix(), data)
        inspection.checked_path(output, [parent])
        temporary.replace(output)
        if staging:
            inspection.checked_path(folder, [parent])
            staging.rename(folder)  # Only a complete folder becomes visible under its final name.
            staging = None
    finally:
        temporary.unlink(missing_ok=True)
        if staging:
            inspection.checked_path(staging, [parent], must_exist=True)
            shutil.rmtree(staging)
    return {'path': str(output), 'bytes': output.stat().st_size, 'pair_id': pair_id,
            **({'folder': str(folder), 'files': files} if unpacked else {})}


def prune(root, *, now):
    from . import dry_runs
    prefix = str(Path(root).resolve()).casefold() + '|'
    removed, errors = 0, []
    for key, private in appconfig.get(KEY, {}).items():
        if not key.startswith(prefix):
            continue
        try:
            runs = [dry_runs.read(root, private['agent'], private['job'], rid) for rid in private['runs'].values()]
            if any(r['status'] in ('queued', 'running') for r in runs):
                continue
            finished = max(dt.datetime.fromisoformat(r.get('finished') or r['started']) for r in runs) if runs else dt.datetime.fromisoformat(private['started'])
            if now - finished < dt.timedelta(days=private['keep_days']):
                continue
            folders = [directory(root, private['pair_id']), _result_dir(root, private['pair_id'])]
            folders += [dry_runs.directory(root, private['agent'], private['job'], rid) for rid in private['runs'].values()]
            for folder in folders:
                if folder.exists():
                    for p in folder.rglob('*'):
                        inspection.checked_path(p, [folder], must_exist=True)
            for folder in folders:
                if folder.exists():
                    shutil.rmtree(folder)
            inspection._set(KEY, key, None)
            removed += 1
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
    return {'removed': removed, 'errors': errors}
