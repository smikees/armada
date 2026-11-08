from types import SimpleNamespace
from armada.webui import attention


def test_attention_links_repair_failures_and_approvals(monkeypatch, tmp_path):
    today = attention.clock.today().isoformat()
    agents = [SimpleNamespace(id='healthy', display='<Synthetic>', record_error=None, history_errors=[], jobs=[]),
              SimpleNamespace(id='broken', display='Damaged', record_error='Invalid JSON', history_errors=[], jobs=[])]
    calls = []
    def runs(root, agent, *, since):
        calls.append((agent, since))
        return [{'ts': today+'T12:00:00', 'status': 'failed'}, {'ts': '2000-01-01', 'status': 'failed'}]
    monkeypatch.setattr(attention, '_runs', runs)
    monkeypatch.setattr(attention.jobs, 'count_pending', lambda _: 2)
    monkeypatch.setattr(attention.capabilities, 'count_requests', lambda _: 1)
    html = attention.panel(SimpleNamespace(agents=agents), tmp_path)
    assert calls == [('healthy', today)]
    assert '&lt;Synthetic&gt;: 1 failed or interrupted runs today' in html
    assert '/agent/broken' in html and 'work is held' in html
    assert '2 job proposals' in html and '1 capability requests' in html
    assert 'href="/approvals"' in html and 'not a live provider health check' in html


def test_unreadable_review_source_is_visible_not_an_all_clear(monkeypatch, tmp_path):
    def fail(_):
        raise OSError('synthetic read failure')
    monkeypatch.setattr(attention.jobs, 'count_pending', fail)
    monkeypatch.setattr(attention.capabilities, 'count_requests', lambda _: 0)
    html = attention.panel(SimpleNamespace(agents=[]), tmp_path)
    assert 'Could not read job proposals' in html
    assert 'no failed runs' not in html
