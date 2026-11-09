import pytest
from armada import system_memory, appconfig, memory, util
from armada.alexander import prompt as alexander_prompt


def test_default_is_shared_and_never_written_on_read(tmp_path):
    assert 'process_after' in system_memory.prompt()
    assert 'process_after' in memory.assemble_core(tmp_path, tmp_path / 'agents/a', {})
    assert 'process_after' in alexander_prompt()
    assert not appconfig._path().exists()


def test_owner_edit_is_immediate_across_realms_and_detects_stale_save(tmp_path):
    initial = system_memory.load()
    system_memory.save('Synthetic owner instructions', initial['revision'])
    for name in ('realm-one', 'realm-two'):
        assert 'Synthetic owner instructions' in memory.assemble_core(tmp_path / name, tmp_path / name / 'agents/a', {})
    assert 'Synthetic owner instructions' in alexander_prompt()
    with pytest.raises(ValueError, match='another window'):
        system_memory.save('Stale edit', initial['revision'])
    assert system_memory.load()['text'] == 'Synthetic owner instructions'


@pytest.mark.parametrize('value', [None, {}, 'x' * 16001, 'x\x00y'])
def test_invalid_memory_is_not_saved(value):
    with pytest.raises(ValueError):
        system_memory.save(value, system_memory.load()['revision'])
    assert not appconfig._path().exists()


def test_corrupt_app_configuration_is_not_silently_dropped(tmp_path):
    appconfig._path().parent.mkdir(parents=True, exist_ok=True)
    appconfig._path().write_text('{broken', encoding='utf-8')
    with pytest.raises(util.StateError):
        memory.assemble_core(tmp_path, tmp_path / 'agents/a', {})
    with pytest.raises(util.StateError):
        system_memory.save('replacement', 'invalid')
    assert appconfig._path().read_text() == '{broken'


def test_editor_escapes_owner_text():
    from armada.webui.system_memory import editor
    system_memory.save('</textarea><script>alert(1)</script>', system_memory.load()['revision'])
    html = editor()
    assert '&lt;/textarea&gt;&lt;script&gt;' in html
    assert '<script>alert(1)</script>' not in html


@pytest.mark.parametrize('provider', ['claude', 'codex', 'gemini'])
def test_each_provider_receives_app_memory(tmp_path, monkeypatch, provider):
    from armada import runner
    from armada.engine import get_engine
    from armada.engine.base import RunResult
    util.write_json_atomic(tmp_path / 'realm.json', {'name': 'Synthetic'})
    ad = tmp_path / 'agents/a'
    ad.mkdir(parents=True)
    util.write_json_atomic(ad / 'agent.json', {'id': 'a'})
    system_memory.save('Synthetic global rule', system_memory.load()['revision'])
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
