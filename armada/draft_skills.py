"""Owner-fingerprinted skill bundles, executed only in Windows draft isolation."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading

from . import appconfig, capabilities, inspection, skills, util


def _bundles(root, agent, job):
    own = {s.id: s for s in skills.load(root, agent)}
    cfg = util.read_json_state(Path(root) / 'agents' / agent / 'agent.json')
    # The legacy skill manifest and the current capability catalogue both declare own skills.
    own_caps = {capabilities.cap_key(c): c for c in capabilities.usable(root, cfg)['skills']}
    available = set(own) | set(own_caps)
    allowed = job.get('allowed_skills', sorted(available))
    if not isinstance(allowed, list) or any(not isinstance(s, str) for s in allowed):
        raise ValueError('Allowed skills must be a list of skill IDs.')
    paths = {}
    for sid in allowed:
        util.safe_seg(sid, 'skill')
        if sid not in available:
            continue
        source = own[sid].source if sid in own else own_caps[sid].get('path', '')
        candidates = [Path(root) / 'agents' / agent / 'skills' / sid, Path(root) / 'skills' / sid,
                      Path.home() / '.agents' / 'skills' / sid, Path.home() / '.claude' / 'skills' / sid]
        if source.startswith('path:'):
            candidates.insert(0, Path(source[5:]))
        for path in candidates:
            if (path / 'SKILL.md').is_file():
                paths[sid] = inspection.checked_path(path.absolute(), [path.absolute()], must_exist=True)
                break
    return paths


def _inventory(path):
    result, total = {}, 0
    for current, dirs, names in os.walk(path, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in ('.git', '__pycache__', 'node_modules'))
        for d in dirs:
            inspection.checked_path(Path(current) / d, [path], must_exist=True)
        for name in sorted(names):
            p = inspection.checked_path(Path(current) / name, [path], must_exist=True)
            total += p.stat().st_size
            if total > 20 * 1024 * 1024 or len(result) >= 2000:
                raise ValueError('Approved skill bundle exceeds 20 MiB / 2,000 files. Vendor only its required dependencies.')
            if name.startswith('.env') or name.lower() in ('auth.json', 'credentials.json'):
                raise ValueError('Credentials cannot be included in an approved skill bundle.')
            result[p.relative_to(path).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return result


def fingerprint(root, agent, job):
    declarations = job.get('dry_run_scripts', [])
    if not isinstance(declarations, list) or any(not isinstance(s, str) for s in declarations):
        raise ValueError('Dry-run scripts must be a list of skill-id/script-path entries.')
    bundles = _bundles(root, agent, job)
    entries = {}
    for declaration in declarations:
        sid, separator, relative = declaration.partition('/')
        if not separator or sid not in bundles:
            raise ValueError('Choose a script from this job’s own allowed skills: skill-id/scripts/example.py.')
        script = inspection.checked_path(bundles[sid] / relative, [bundles[sid]], must_exist=True)
        if not script.is_file() or script.suffix not in ('.py', '.js', '.cjs', '.mjs'):
            raise ValueError('Approved scripts must be Python or Node.js files.')
        entries[sid] = {'path': str(bundles[sid]), 'files': _inventory(bundles[sid])}
    sealed = {'id': job.get('id'), 'prompt': job.get('prompt'), 'allowed_skills': job.get('allowed_skills'),
              'dry_run_inputs': job.get('dry_run_inputs'), 'scripts': declarations, 'bundles': entries}
    return {'sha256': hashlib.sha256(json.dumps(sealed, sort_keys=True).encode()).hexdigest(), **sealed}


def _key(root, agent, job):
    return inspection.identity(root, agent) + '|' + util.safe_seg(job['id'], 'job')


def approve(root, agent, job):
    value = fingerprint(root, agent, job) if job.get('dry_run_scripts') else None
    inspection._set('dry_run_scripts', _key(root, agent, job), value)


def approved(root, agent, job):
    saved = appconfig.get('dry_run_scripts', {}).get(_key(root, agent, job))
    if not saved or saved != fingerprint(root, agent, job):
        raise ValueError('Dry-run script approval is missing or changed. Review and save the scripts in Job settings.')
    disk = util.read_json_state(Path(root) / 'agents' / agent / 'jobs' / (job['id'] + '.json'))
    if fingerprint(root, agent, disk) != saved:
        raise ValueError('The saved job or its skill bundle changed. Re-approve before running scripts.')
    return saved


def stage(root, agent, job, folder):
    if not job.get('dry_run_scripts'):
        return None
    grant = approved(root, agent, job)
    code = folder / 'scripts'
    code.mkdir()
    for sid, bundle in grant['bundles'].items():
        target = code / sid
        target.mkdir()
        for relative, digest in bundle['files'].items():
            source = inspection.checked_path(Path(bundle['path']) / relative, [bundle['path']], must_exist=True)
            data = source.read_bytes()
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError('Skill bundle changed during staging. Re-approve it before retrying.')
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
    return grant


def _runtime(kind, folder):
    target = folder / kind
    target.mkdir()
    if kind == 'python':
        original = Path(getattr(sys, '_base_executable', sys.executable))
        if original.name.lower() == 'pythonw.exe':
            original = original.with_name('python.exe')
        if not original.is_file() or original.name.lower() not in ('python.exe', 'python3.exe'):
            raise ValueError('A standalone Python runtime is required for approved scripts.')
        source = original.parent
        for path in source.iterdir():
            if path.is_file() and path.suffix.lower() in ('.dll', '.exe', '.zip', '._pth', '.pyd'):
                shutil.copy2(path, target / path.name)
        for name in ('Lib', 'DLLs'):
            if (source / name).is_dir():
                shutil.copytree(source / name, target / name, ignore=shutil.ignore_patterns('site-packages', '__pycache__'))
        for config in target.glob('*._pth'):
            # The embedded app normally adds its own packages and site hooks.
            # Draft scripts receive only the staged standard library.
            config.write_text('\n'.join(p.name for p in target.glob('python*.zip')) + '\n.\nLib\nDLLs\n', encoding='utf-8')
        return target / original.name
    source = shutil.which('node')
    if not source or Path(source).suffix.lower() != '.exe':
        raise ValueError('Install Node.js 22 or newer for approved JavaScript scripts.')
    shutil.copy2(source, target / 'node.exe')
    return target / 'node.exe'


def execute(broker, script, arguments):
    from .engine.process import supervise_command
    from .engine.skill_sandbox import SkillSandbox
    if broker.inspector or not broker.job or not broker.snapshot or not broker.script_grant:
        raise ValueError('Approved scripts are available only in dry-run turns.')
    if script not in broker.script_grant['scripts']:
        raise ValueError('This script is not in the owner-approved set.')
    if not isinstance(arguments, list) or len(arguments) > 32 or any(not isinstance(x, str) or len(x) > 4096 for x in arguments):
        raise ValueError('Supply up to 32 text arguments.')
    if broker.script_calls >= 8:
        raise ValueError('Eight approved script calls are allowed per dry-run turn.')
    approved(broker.root, broker.agent, broker.job)  # Content, grants and saved job rechecked on every call.
    code = broker.output.parent / 'scripts'
    sid, relative = script.split('/', 1)
    path = inspection.checked_path(code / sid / relative, [code], must_exist=True)
    for bundle_id, bundle in broker.script_grant['bundles'].items():
        if _inventory(code / bundle_id) != bundle['files']:
            raise ValueError('Staged approved scripts changed. Refusing to execute.')
    broker.script_calls += 1
    kind = 'python' if path.suffix == '.py' else 'node'
    with tempfile.TemporaryDirectory(prefix='runtime-', dir=broker.output.parent) as temporary:
        exe = _runtime(kind, Path(temporary))
        if kind == 'python':
            args = [str(exe), '-I', '-B', '-c',
                    'import sys,runpy,os;sys.path.insert(0,sys.argv[1]);sys.path.insert(0,os.path.dirname(sys.argv[2]));sys.argv=sys.argv[2:];runpy.run_path(sys.argv[0],run_name="__main__")',
                    str(code / sid), str(path), *arguments]
        else:
            args = [str(exe), '--permission', '--preserve-symlinks', '--preserve-symlinks-main',
                    '--allow-fs-read=' + str(code), '--allow-fs-read=' + str(broker.snapshot),
                    '--allow-fs-read=' + str(broker.output), '--allow-fs-write=' + str(broker.output), str(path), *arguments]
        env = {k: os.environ[k] for k in ('SystemRoot', 'WINDIR', 'USERPROFILE', 'LOCALAPPDATA', 'APPDATA') if k in os.environ}
        env.update(TEMP=str(broker.output), TMP=str(broker.output), ARMADA_DRY_RUN='1',
                   ARMADA_DRY_RUN_DIR=str(broker.output), ARMADA_INPUT_DIR=str(broker.snapshot),
                   ARMADA_INPUT_MANIFEST=str(broker.snapshot / 'manifest.json'),
                   PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
        with SkillSandbox(readonly=[Path(temporary), code, broker.snapshot], writable=broker.output) as sandbox:
            done = threading.Event()
            def bind(handle):
                broker.script_process = handle
                def watch():
                    while not done.wait(.1):
                        if broker.closed or broker.cancelled():
                            handle.kill()
                            break
                threading.Thread(target=watch, daemon=True).start()
            try:
                result = supervise_command(args, cwd=str(broker.output), env=env,
                    timeout=min(120, int(broker.job.get('timeout', 120)) or 120), launch=sandbox, on_proc=bind)
            finally:
                done.set()
                broker.script_process = None
    return {'ok': not result.error and result.returncode == 0, 'exit_code': result.returncode,
            'stdout': result.stdout, 'stderr': result.stderr, 'error': result.error,
            'timed_out': result.timed_out, 'cancelled': result.cancelled}
