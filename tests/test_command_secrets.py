import json
import os
import pytest
from armada import command_secrets as secrets, run_policy, util


@pytest.fixture
def realm(tmp_path, monkeypatch):
    util.write_json_atomic(tmp_path/'realm.json',{'name':'Synthetic'})
    util.write_json_atomic(tmp_path/'agents/a/agent.json',{'id':'a','name':'A'})
    monkeypatch.setattr('armada.provider_keys._crypt', lambda value, decrypt=False: bytes(b ^ 77 for b in value))
    return tmp_path


@pytest.mark.skipif(os.name!='nt',reason='Windows DPAPI store')
def test_secret_never_saved_to_realm_and_requires_sealed_command(realm):
    value='private-example-credential'
    assert secrets.save(realm,'ibkr_read',value)==['ibkr_read']
    assert value not in secrets._path().read_text()
    job={'id':'read','kind':'command','run':'echo test','secrets':['ibkr_read']}
    util.write_json_atomic(realm/'agents/a/jobs/read.json',job)
    with pytest.raises(ValueError,match='approve'): secrets.environment(realm,'a',job)
    run_policy.seal_job(realm,'a',job)
    assert secrets.environment(realm,'a',job)=={'ARMADA_SECRET_IBKR_READ':value}
    assert 'ARMADA_SECRET_IBKR_READ' not in os.environ
    assert all(value not in p.read_text() for p in realm.rglob('*.json'))
    assert secrets.redact('stdout '+value+' stderr '+value,[value])=='stdout [secret redacted] stderr [secret redacted]'
    with pytest.raises(ValueError,match='changed'):
        secrets.environment(realm,'a',{**job,'run':'changed'})
    assert secrets.save(realm,'ibkr_read','')==[]


def test_secret_names_and_non_command_use_rejected(realm):
    with pytest.raises(ValueError): secrets.save(realm,'../key','example')
    with pytest.raises(ValueError,match='Only command jobs'):
        run_policy.validate_job({'kind':'agent','secrets':['ibkr_read']})
    with pytest.raises(ValueError,match='lowercase'):
        run_policy.validate_job({'kind':'command','secrets':['Bad-Name']})


@pytest.mark.skipif(os.name!='nt',reason='Windows DPAPI store')
def test_command_environment_and_saved_output_are_redacted(realm,monkeypatch,capsys):
    from armada import runner
    from armada.engine.process import ProcessResult
    value='synthetic-private-command-key'
    secrets.save(realm,'ibkr_read',value)
    job={'id':'read','kind':'command','run':['synthetic-reader'],'secrets':['ibkr_read']}
    util.write_json_atomic(realm/'agents/a/jobs/read.json',job)
    run_policy.seal_job(realm,'a',job)
    def run(argv,**kwargs):
        assert kwargs['env']['ARMADA_SECRET_IBKR_READ']==value
        assert 'ARMADA_SECRET_IBKR_READ' not in os.environ
        return ProcessResult(returncode=1,stdout=value,stderr=value,error='Error '+value)
    monkeypatch.setattr('armada.engine.process.supervise_command',run)
    result=runner._run_command(realm,'a','read',job,realm/'agents/a')
    assert value not in json.dumps(result)
    assert value not in capsys.readouterr().out
    for path in realm.rglob('*'):
        if path.is_file():
            assert value.encode() not in path.read_bytes()
