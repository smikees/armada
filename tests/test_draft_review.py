"""Real draft boundaries plus synthetic paired-review and inspector regression checks."""
import datetime as dt
import json
import os
from pathlib import Path
import socket
import threading
import time
import zipfile

import pytest

from armada import appconfig, draft_inputs, draft_skills, dry_run_pairs, dry_runs, inspection, util
from armada.engine.base import RunResult
from armada.managed_tools import ManagedTools
from tests.test_dry_runs import realm, finished, DraftEngine, approve_inspector


@pytest.mark.parametrize('turn', ['chat', 'inbox', 'job'])
def test_inspector_authority_does_not_replace_normal_turn_grants(realm, monkeypatch, turn):
    from armada import runner
    from armada.execution import TurnCoordinator, TurnRequest
    from armada.request_context import RunContext
    approve_inspector(realm)
    class Ordinary(DraftEngine):
        def run_stream(self, **kw):
            assert not getattr(self, 'managed_tools', None)
            assert 'This is an ARMADA inspector job turn' not in kw['system']
            assert self.writable_roots
            return RunResult(ok=True, output='Normal conversation with normal grants.')
    monkeypatch.setattr(runner, '_select_engine', lambda *a, **k: Ordinary())
    request = TurnRequest(RunContext.capture(realm, 'inspector', 'main'), 'Ordinary work', allow_tools=True,
        task='ordinary' if turn != 'chat' else None,
        job={'id': 'ordinary'} if turn == 'job' else None)
    result = TurnCoordinator(request).run()
    assert (result.get('ok') is True) if turn == 'chat' else result['status'] == 'ok'


def test_inspector_job_requires_machine_authority(realm, monkeypatch):
    from armada import runner
    from armada.execution import TurnCoordinator, TurnRequest
    from armada.request_context import RunContext
    monkeypatch.setattr(runner, '_select_engine', lambda *a, **kw: DraftEngine())
    request = TurnRequest(RunContext.capture(realm, 'inspector', 'main'), 'Review', task='review',
                          job={'id': 'review', 'inspector': True})
    assert TurnCoordinator(request).run()['status'] == 'error'


def test_inspector_job_settings_and_effective_metadata(realm):
    approve_inspector(realm)
    util.mutate_json(realm / 'realm.json', lambda r: r.update(default_model='claude-sonnet-5', default_effort='medium'))
    util.mutate_json(realm / 'agents/writer/agent.json', lambda a: a.update(model='gpt-6-sol', effort='high'))
    broker = ManagedTools(realm, 'inspector', inspector=True)
    row = next(r for r in broker.call('list_jobs', {}) if r['job'] == 'digest')
    assert row['model'] == 'gpt-6-sol' and row['provider'] == 'codex' and row['effort'] == 'high'
    assert row['agent_default_model'] == 'gpt-6-sol' and row['agent_default_effort'] == 'high'
    assert row['schedule'] == '0 9 * * *' and row['enabled'] is False
    util.mutate_json(realm / 'agents/writer/jobs/digest.json', lambda j: j.update(model='claude-sonnet-5', effort='low'))
    row = next(r for r in broker.call('list_jobs', {}) if r['job'] == 'digest')
    assert (row['model'], row['provider'], row['effort']) == ('claude-sonnet-5', 'claude', 'low')
    for job in ({'inspector': 'true'}, {'inspector': True, 'kind': 'command'}):
        with pytest.raises(ValueError):
            dry_runs.settings(job)
    assert 'run_skill' not in {t['name'] for t in broker.tools()}


def test_dry_run_effort_override_does_not_change_saved_job(realm):
    class Effort(DraftEngine):
        def run_stream(self, **kw):
            assert kw['effort'] == 'low'
            return super().run_stream(**kw)
    before = (realm / 'agents/writer/jobs/digest.json').read_bytes()
    run = dry_runs.start(realm, 'writer', 'digest', 'gpt-6-sol', effort='low', engine=Effort())
    assert finished(realm, run)['status'] == 'completed'
    assert (realm / 'agents/writer/jobs/digest.json').read_bytes() == before
    with pytest.raises(ValueError):
        dry_runs.start(realm, 'writer', 'digest', 'gpt-6-sol', effort='unlimited', engine=Effort())


def test_snapshot_is_frozen_and_excludes_control_and_credentials(realm, tmp_path):
    (realm / '.env').write_text('PRIVATE=hidden')
    (realm / '.armada').mkdir(exist_ok=True)
    (realm / '.armada/secret.txt').write_text('host control')
    target = realm / '.armada/test-inputs'
    job = util.read_json_state(realm / 'agents/writer/jobs/digest.json')
    manifest = draft_inputs.freeze(realm, 'writer', job, target)
    assert not any('.env' in f['source'] or '.armada' in f['source'] for f in manifest['files'])
    (realm / 'input.json').write_text('changed')
    assert draft_inputs.map_path(target, realm / 'input.json').read_text() == '{"amount":"12.34"}'
    for bad in (realm / '.env', realm / '.armada/secret.txt', realm / '../outside.txt', appconfig._path()):
        with pytest.raises(ValueError):
            draft_inputs.map_path(target, bad)


def _skill_job(realm, suffix='py', content='print("draft")'):
    from armada.model import Skill
    from armada.skills import save
    folder = realm / 'agents/writer/skills/review'
    folder.mkdir(parents=True)
    (folder / 'SKILL.md').write_text('Synthetic reviewer skill.')
    (folder / ('test.' + suffix)).write_text(content)
    save(realm, 'writer', [Skill(id='review')])
    p = realm / 'agents/writer/jobs/digest.json'
    job = util.mutate_json(p, lambda j: j.update(allowed_skills=['review'], dry_run_scripts=['review/test.' + suffix],
                                              dry_run_inputs=[str(realm / 'input.json')]))
    return job, folder


def test_script_approval_covers_dependencies_inputs_and_saved_job(realm):
    job, folder = _skill_job(realm)
    (folder / 'helper.py').write_text('AMOUNT = "12.34"')
    with pytest.raises(ValueError):
        draft_skills.approved(realm, 'writer', job)
    draft_skills.approve(realm, 'writer', job)
    assert draft_skills.approved(realm, 'writer', job)['scripts'] == ['review/test.py']
    (folder / 'helper.py').write_text('AMOUNT = "120.34"')
    with pytest.raises(ValueError):
        draft_skills.approved(realm, 'writer', job)
    draft_skills.approve(realm, 'writer', job)
    modified = {**job, 'dry_run_inputs': [str(realm)]}
    with pytest.raises(ValueError):
        draft_skills.approved(realm, 'writer', modified)
    util.mutate_json(realm / 'agents/writer/jobs/digest.json', lambda j: j.update(prompt='Changed job'))
    with pytest.raises(ValueError):
        draft_skills.approved(realm, 'writer', job)


@pytest.mark.parametrize('declaration', ['other/test.py', 'review/../test.py', 'review/test.cmd'])
def test_script_set_cannot_escape_own_skill(realm, declaration):
    job, folder = _skill_job(realm)
    with pytest.raises((ValueError, FileNotFoundError)):
        draft_skills.fingerprint(realm, 'writer', {**job, 'dry_run_scripts': [declaration]})
    with pytest.raises(ValueError):
        draft_skills.fingerprint(realm, 'writer', {**job, 'allowed_skills': []})


@pytest.mark.skipif(os.name != 'nt', reason='Native Windows draft boundary')
@pytest.mark.parametrize('runtime', ['python', 'node'])
def test_real_skill_script_isolation(realm, runtime):
    import shutil
    if runtime == 'node' and not shutil.which('node'):
        pytest.skip('Node.js is not installed')
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0)); listener.listen(1)
    port = listener.getsockname()[1]
    production = realm / 'production.txt'; production.write_text('untouched')
    if runtime == 'python':
        content = '''import json,os,pathlib,socket,subprocess,sys
p=pathlib.Path(os.environ['ARMADA_INPUT_DIR']); m=json.loads((p/'manifest.json').read_text()); src=p/m['files'][0]['copy']
r={'input':src.read_text(),'cwd':os.getcwd(),'dry':os.environ['ARMADA_DRY_RUN']}
pathlib.Path('draft.txt').write_text('12.34')
for n,p in [('input_write',src),('production_write',pathlib.Path(sys.argv[1])),('production_read',pathlib.Path(sys.argv[1]))]:
 try:
  p.read_text() if n.endswith('read') else p.write_text('unsafe');r[n]='ALLOWED'
 except OSError:r[n]='denied'
try:subprocess.run([sys.executable,'-c','print(1)']);r['child']='ALLOWED'
except OSError:r['child']='denied'
try:socket.create_connection(('127.0.0.1',int(sys.argv[2])),timeout=1);r['network']='ALLOWED'
except OSError:r['network']='denied'
print(json.dumps(r))
'''
        suffix = 'py'
    else:
        content = '''const fs=require('node:fs'),cp=require('node:child_process'),net=require('node:net');
const p=process.env.ARMADA_INPUT_DIR,m=JSON.parse(fs.readFileSync(p+'/manifest.json','utf8')),src=p+'/'+m.files[0].copy;
const r={input:fs.readFileSync(src,'utf8'),cwd:process.cwd(),dry:process.env.ARMADA_DRY_RUN};fs.writeFileSync('draft.txt','12.34');
for(const[n,p]of [['input_write',src],['production_write',process.argv[2]],['production_read',process.argv[2]]]){
try{if(n.endsWith('read'))fs.readFileSync(p);else fs.writeFileSync(p,'unsafe');r[n]='ALLOWED'}catch(e){r[n]='denied'}}
try{cp.spawn(process.execPath,['-e','console.log(1)']);r.child='ALLOWED'}catch(e){r.child='denied'}
const s=net.connect(Number(process.argv[3]),'127.0.0.1');s.setTimeout(1000,()=>{r.network='denied';s.destroy();console.log(JSON.stringify(r))});
s.on('connect',()=>{r.network='ALLOWED';s.destroy();console.log(JSON.stringify(r))});s.on('error',()=>{r.network='denied';console.log(JSON.stringify(r))});
'''
        suffix = 'js'
    job, folder = _skill_job(realm, suffix, content)
    draft_skills.approve(realm, 'writer', job)
    run = dry_runs.directory(realm, 'writer', 'digest', 'native')
    output = run / 'output'; output.mkdir(parents=True)
    snapshot = run / 'inputs'; draft_inputs.freeze(realm, 'writer', job, snapshot)
    grant = draft_skills.stage(realm, 'writer', job, run)
    broker = ManagedTools(realm, 'writer', output=output, job=job, snapshot=snapshot, script_grant=grant)
    try:
        result = broker.call('run_skill', {'script': 'review/test.' + suffix, 'arguments': [str(production), str(port)]})
        assert result['ok'], result
        report = json.loads(result['stdout'])
        assert report['input'] == '{"amount":"12.34"}' and report['dry'] == '1' and Path(report['cwd']) == output
        assert all(report[k] == 'denied' for k in ('input_write', 'production_write', 'production_read', 'child', 'network'))
        assert production.read_text() == 'untouched' and (output / 'draft.txt').read_text() == '12.34'
        listener.settimeout(.1)
        with pytest.raises(TimeoutError):
            listener.accept()
    finally:
        listener.close()


def _wait_pair(root, pair):
    private = dry_run_pairs._private(root, pair['pair_id'])
    for rid in private['runs'].values():
        finished(root, {'agent': private['agent'], 'job': private['job'], 'run_id': rid})
    return dry_run_pairs.read(root, pair['pair_id'])


def test_blind_pair_same_inputs_identity_reveal_export_and_retention(realm, monkeypatch):
    approve_inspector(realm)
    original = (realm / 'agents/writer/jobs/digest.json').read_bytes()
    gate = threading.Barrier(2)
    seen = []
    class Frozen(DraftEngine):
        def run_stream(self, **kw):
            gate.wait(timeout=5)
            data = self.managed_tools.call('read_input', {'path': str(realm / 'input.json')})['content']
            seen.append(data)
            self.managed_tools.call('write_draft', {'path': 'draft.txt', 'content': data + ' ' + kw['model']})
            self.managed_tools.call('write_draft', {'path': 'report-' + kw['model'] + '.txt', 'content': data})
            return RunResult(ok=True, output='Blind draft using ' + kw['model'], model=kw['model'])
    pair = dry_run_pairs.start(realm, 'writer', 'digest', 'gpt-6-sol', 'claude-sonnet-5',
                              requested_by='inspector', engines=(Frozen(), Frozen()))
    (realm / 'input.json').write_text('new production value')
    pair = _wait_pair(realm, pair)
    assert seen == ['{"amount":"12.34"}'] * 2
    serialized = json.dumps(pair)
    assert 'mapping' not in pair and 'gpt-6-sol' not in serialized and 'claude-sonnet-5' not in serialized
    broker = ManagedTools(realm, 'inspector', inspector=True)
    private = dry_run_pairs._private(realm, pair['pair_id'])
    for rid in private['runs'].values():
        with pytest.raises(ValueError):
            broker.call('get_dry_run', {'agent': 'writer', 'job': 'digest', 'run_id': rid})
        info = dry_runs.read(realm, 'writer', 'digest', rid)
        assert info['model'].startswith('Blind candidate') and 'tokens' not in info and 'actual_model' not in info
    exported = broker.call('export_dry_run_pair', {'pair_id': pair['pair_id']})
    with zipfile.ZipFile(exported['path']) as archive:
        assert {'A/draft.txt', 'B/draft.txt', 'comparison.json'} <= set(archive.namelist())
        assert all(b'gpt-6-sol' not in archive.read(n) and b'claude-sonnet-5' not in archive.read(n) for n in archive.namelist())
        assert all('gpt-6-sol' not in n and 'claude-sonnet-5' not in n for n in archive.namelist())
    with pytest.raises(ValueError):
        broker.call('record_scores', {'pair_id': pair['pair_id'], 'score_a': float('nan'), 'score_b': 90})
    revealed = broker.call('record_scores', {'pair_id': pair['pair_id'], 'score_a': 85, 'score_b': 90, 'notes': 'Correctness rubric'})
    assert {c['model'] for c in revealed['mapping'].values()} == {'gpt-6-sol', 'claude-sonnet-5'}
    with pytest.raises(ValueError):
        broker.call('record_scores', {'pair_id': pair['pair_id'], 'score_a': 100, 'score_b': 0})
    assert (realm / 'agents/writer/jobs/digest.json').read_bytes() == original
    result = dry_runs.prune(realm, now=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=8))
    assert result == {'removed': 1, 'errors': []}
    assert not dry_run_pairs.directory(realm, pair['pair_id']).exists()
    with pytest.raises(ValueError):
        dry_run_pairs.read(realm, pair['pair_id'])


def test_pair_active_files_and_early_scores_are_hidden(realm):
    release = threading.Event()
    class Waiting(DraftEngine):
        def run_stream(self, **kw):
            self.managed_tools.call('write_draft', {'path': 'partial.txt', 'content': kw['model']})
            release.wait(5)
            return RunResult(ok=True, output='draft', model=kw['model'])
    pair = dry_run_pairs.start(realm, 'writer', 'digest', 'gpt-6-sol', 'claude-sonnet-5', engines=(Waiting(), Waiting()))
    try:
        assert all(not c['files'] for c in pair['candidates'].values())
        with pytest.raises(ValueError):
            dry_run_pairs.read_file(realm, pair['pair_id'], 'A', 'partial.txt')
        with pytest.raises(ValueError):
            dry_run_pairs.record_scores(realm, pair['pair_id'], 1, 2)
        with pytest.raises(ValueError):
            dry_run_pairs.start(realm, 'writer', 'digest', 'gpt-6-sol', 'claude-sonnet-5', engines=(Waiting(), Waiting()))
        assert dry_runs.prune(realm, now=dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=30))['removed'] == 0
    finally:
        release.set(); _wait_pair(realm, pair)


@pytest.mark.skipif(os.name != 'nt', reason='Native Windows draft process ownership')
@pytest.mark.parametrize('cancel', [False, True])
def test_skill_deadline_and_cancel_stop_the_owned_process(realm, cancel):
    job, folder = _skill_job(realm, content='import time; time.sleep(30)')
    util.mutate_json(realm / 'agents/writer/jobs/digest.json', lambda j: j.update(timeout=1 if not cancel else 20))
    job['timeout'] = 1 if not cancel else 20
    draft_skills.approve(realm, 'writer', job)
    run = dry_runs.directory(realm, 'writer', 'digest', 'lifetime')
    output = run / 'output'; output.mkdir(parents=True)
    snapshot = run / 'inputs'; draft_inputs.freeze(realm, 'writer', job, snapshot)
    grant = draft_skills.stage(realm, 'writer', job, run)
    stop = threading.Event()
    broker = ManagedTools(realm, 'writer', output=output, job=job, snapshot=snapshot, script_grant=grant, cancelled=stop.is_set)
    if cancel:
        threading.Timer(.5, stop.set).start()
    before = time.monotonic()
    result = broker.call('run_skill', {'script': 'review/test.py'})
    assert not result['ok'] and (result['cancelled'] if cancel else result['timed_out'])
    assert time.monotonic() - before < 8 and broker.script_process is None


def test_failed_script_staging_leaves_no_orphan_run(realm):
    job, folder = _skill_job(realm)
    with pytest.raises(ValueError):
        dry_runs.start(realm, 'writer', 'digest', 'gpt-6-sol', engine=DraftEngine())
    assert not list(dry_runs.base(realm).glob('*/*/*/output'))


def test_snapshot_bounds_fail_without_partial_copy(realm, monkeypatch):
    target = realm / '.armada/bounded'
    monkeypatch.setattr(draft_inputs, 'MAX_BYTES', 1)
    with pytest.raises(ValueError, match='Draft inputs exceed'):
        draft_inputs.freeze(realm, 'writer', {'dry_run_inputs': [str(realm / 'input.json')]}, target)
    assert not target.exists()


def test_script_grants_and_inspector_authority_can_be_revoked(realm):
    approve_inspector(realm)
    broker = ManagedTools(realm, 'inspector', inspector=True)
    inspection.approve(realm, 'inspector', False)
    with pytest.raises(ValueError, match='disabled'):
        broker.call('start_dry_run_pair', {'agent': 'writer', 'job': 'digest', 'model_a': 'gpt-6-sol', 'model_b': 'claude-sonnet-5'})
    job, folder = _skill_job(realm)
    draft_skills.approve(realm, 'writer', job)
    inspection._set('dry_run_scripts', draft_skills._key(realm, 'writer', job), None)
    with pytest.raises(ValueError):
        draft_skills.approved(realm, 'writer', job)


def test_anonymization_failure_never_exposes_raw_candidate_artifacts(realm, monkeypatch):
    def fail(*args):
        raise OSError('Synthetic anonymous-write failure')
    monkeypatch.setattr(dry_run_pairs, 'anonymize_outputs', fail)
    pair = dry_run_pairs.start(realm, 'writer', 'digest', 'gpt-6-sol', 'claude-sonnet-5', engines=(DraftEngine(), DraftEngine()))
    pair = _wait_pair(realm, pair)
    assert all(c['status'] == 'failed' and not c['files'] for c in pair['candidates'].values())
    with pytest.raises(ValueError, match='Anonymous artifacts'):
        dry_run_pairs.read_file(realm, pair['pair_id'], 'A', 'report.md')
    with pytest.raises(ValueError, match='Anonymous artifacts'):
        dry_run_pairs.export(realm, pair['pair_id'], realm / 'exports')
    revealed = dry_run_pairs.record_scores(realm, pair['pair_id'], 0, 0, 'Both failed')
    assert 'mapping' in revealed and revealed['candidates']['A']['diagnostics']
