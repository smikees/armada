"""Bounded frozen file inputs for draft scripts and paired model tests."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil

from . import appconfig, inspection, util, workspace

MAX_FILES = 10000
MAX_BYTES = 100 * 1024 * 1024
EXCLUDED = {'.armada', '.git', '.venv', '.venv-codex', 'node_modules', '__pycache__',
            '.aws', '.ssh', '.codex', '.claude', 'credentials', 'secrets'}


def permitted(path):
    path = Path(path).absolute()
    private = appconfig._path().parent.resolve()
    if path.is_relative_to(private):
        return False
    return not any(p.casefold() in EXCLUDED or p.casefold().startswith('.env')
                   or p.casefold() in ('credentials.json', 'auth.json', 'config.json.lock') for p in path.parts)


def roots(root, agent, job):
    from .job_access import grant_for
    approved = [Path(root).resolve()]
    if workspace.root(root):
        approved.append(Path(workspace.root(root)).resolve())
    approved.extend(Path(p) for p in grant_for(root, agent, job).roots)
    selected = job.get('dry_run_inputs')
    if selected is not None:
        if not isinstance(selected, list) or not selected or any(not isinstance(p, str) for p in selected):
            raise ValueError('Dry-run inputs must be a non-empty list of approved file or folder paths.')
        approved = [inspection.checked_path(workspace.expand(p, root), approved, must_exist=True) for p in selected]
    approved = sorted(set(approved), key=lambda p: len(p.parts))
    return [p for i, p in enumerate(approved) if not any(p.is_relative_to(q) for q in approved[:i])]


def freeze(root, agent, job, target):
    target = inspection.checked_path(target, [Path(root).resolve()])
    target.mkdir(parents=True, exist_ok=False)
    manifest = {'schema_version': 1, 'roots': [], 'files': []}
    total = 0
    try:
        for index, source in enumerate(roots(root, agent, job)):
            dest = target / str(index)
            if not permitted(source):
                raise ValueError('Host control and credential folders cannot be draft inputs.')
            candidates = []
            if source.is_file():
                candidates = [(source, Path(source.name))]
            else:
                dest.mkdir()
                for current, directories, names in os.walk(source, followlinks=False):
                    directories[:] = sorted(d for d in directories if permitted(Path(current) / d))
                    for d in directories:
                        inspection.checked_path(Path(current) / d, [source], must_exist=True)
                    candidates.extend((Path(current) / n, (Path(current) / n).relative_to(source))
                                      for n in sorted(names) if permitted(Path(current) / n))
                    if len(candidates) > MAX_FILES:
                        raise ValueError('Too many draft input files. Set dry_run_inputs to the required folders.')
            for path, relative in candidates:
                path = inspection.checked_path(path, [source if source.is_dir() else source.parent], must_exist=True)
                before = path.stat()
                total += before.st_size
                if total > MAX_BYTES or len(manifest['files']) >= MAX_FILES:
                    raise ValueError('Draft inputs exceed 100 MiB / 10,000 files. Set dry_run_inputs to the required folders.')
                output = dest / relative
                output.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                with path.open('rb') as src, output.open('xb') as dst:
                    while chunk := src.read(1024 * 1024):
                        digest.update(chunk)
                        dst.write(chunk)
                after = path.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise ValueError('An input changed while it was being frozen. Retry the comparison.')
                manifest['files'].append({'source': str(path), 'copy': str(output.relative_to(target)),
                                          'bytes': before.st_size, 'sha256': digest.hexdigest()})
            manifest['roots'].append({'source': str(source), 'copy': str(dest.relative_to(target)),
                                      'file': source.is_file()})
        util.write_json_atomic(target / 'manifest.json', manifest)
        return manifest
    except BaseException:
        shutil.rmtree(target)
        raise


def map_path(snapshot, path):
    snapshot = Path(snapshot)
    manifest = util.read_json_state(snapshot / 'manifest.json')
    raw = Path(path).absolute()
    if not permitted(raw):
        raise ValueError('Host control files are not draft inputs.')
    for entry in manifest['roots']:
        source = Path(entry['source'])
        if entry['file'] and raw == source:
            return inspection.checked_path(snapshot / entry['copy'] / source.name, [snapshot], must_exist=True)
        if not entry['file'] and raw.is_relative_to(source):
            return inspection.checked_path(snapshot / entry['copy'] / raw.relative_to(source), [snapshot], must_exist=True)
    raise ValueError('This file is not in the frozen input set. Live inputs are unavailable in this test.')
