import pytest
from armada import system_memory, appconfig, memory, util
from armada.alexander import prompt as alexander_prompt


def test_default_is_shared_and_never_written_on_read(tmp_path):
    assert 'process_after' in system_memory.prompt()
    assert 'process_after' in memory.assemble_core(tmp_path, tmp_path / 'agents/a', {})
    assert 'process_after' in alexander_prompt()
    assert system_memory.load().path.read_text(encoding='utf-8') == system_memory.load().text
    assert not appconfig._path().exists()


def test_legacy_owner_instructions_are_preserved_across_realms(tmp_path):
    appconfig.save({'system_memory': 'Synthetic owner instructions'})
    for name in ('realm-one', 'realm-two'):
        assert 'Synthetic owner instructions' in memory.assemble_core(tmp_path / name, tmp_path / name / 'agents/a', {})
    assert 'Synthetic owner instructions' in alexander_prompt()
    assert system_memory.load().path == appconfig._path()
    appconfig.save({'system_memory': ''})
    assert not system_memory.prompt()


@pytest.mark.parametrize('value', [None, {}, 'x' * 16001, 'x\x00y'])
def test_invalid_legacy_memory_is_rejected(value):
    appconfig.save({'system_memory': value})
    with pytest.raises(ValueError):
        system_memory.load()


def test_corrupt_app_configuration_is_not_silently_dropped(tmp_path):
    appconfig._path().parent.mkdir(parents=True, exist_ok=True)
    appconfig._path().write_text('{broken', encoding='utf-8')
    with pytest.raises(util.StateError):
        memory.assemble_core(tmp_path, tmp_path / 'agents/a', {})
    with pytest.raises(util.StateError):
        system_memory.load()
    assert appconfig._path().read_text() == '{broken'


def test_reader_escapes_owner_text():
    from armada.webui.system_memory import reader
    appconfig.save({'system_memory': '</textarea><script>alert(1)</script>'})
    html = reader()
    assert '&lt;/textarea&gt;&lt;script&gt;' in html
    assert '<script>alert(1)</script>' not in html


def test_reveal_uses_the_active_source_and_the_old_write_route_is_gone(monkeypatch):
    from armada.serve import Handler
    handler = object.__new__(Handler)
    monkeypatch.setattr(handler, '_reveal', lambda body: body['path'])
    assert handler._reveal_system_memory({'path': 'ignored'}) == str(system_memory.DEFAULT_PATH)
    appconfig.save({'system_memory': 'Synthetic owner instructions'})
    assert handler._reveal_system_memory({}) == str(appconfig._path())
    assert '/api/save-system-memory' not in Handler._POST_JSON


@pytest.mark.parametrize('provider', ['claude', 'codex', 'gemini'])
def test_each_provider_receives_app_memory(tmp_path, monkeypatch, provider):
    from armada import runner
    from armada.engine import get_engine
    from armada.engine.base import RunResult
    util.write_json_atomic(tmp_path / 'realm.json', {'name': 'Synthetic'})
    ad = tmp_path / 'agents/a'
    ad.mkdir(parents=True)
    util.write_json_atomic(ad / 'agent.json', {'id': 'a'})
    appconfig.save({'system_memory': 'Synthetic global rule'})
    engine = get_engine(provider)
    seen = []
    def stream(**kw):
        seen.append(kw['system'])
        return RunResult(ok=True, output='Synthetic answer')
    monkeypatch.setattr(engine, 'run_stream', stream)
    if provider == 'codex':
        monkeypatch.setattr(engine, '_execution_probe', lambda *a: {'ok': True, 'reason': ''})
    result = runner.chat(tmp_path, 'a', 'main', 'hello', engine=engine)
    assert result['status'] == 'ok'
    assert len(seen) == 1 and 'Synthetic global rule' in seen[0]
