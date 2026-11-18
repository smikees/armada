"""Work clocks survive reloads and do not fabricate times for legacy transcripts."""
from armada.threads import Thread
from armada.webui.threadsview import _working_turn, _turn


def test_work_start_is_stable_and_completion_keeps_actual_duration(tmp_path, monkeypatch):
    import time
    thread = Thread(tmp_path, 'main')
    turn = thread.begin_turn('A queued request', queued=True)
    assert 'work_started_at' not in thread._messages()[0]
    monkeypatch.setattr(time, 'time', lambda: 1000.25)
    thread.start_work(turn)
    monkeypatch.setattr(time, 'time', lambda: 2000.25)
    thread.start_work(turn)
    assert thread._messages()[0]['work_started_at'] == 1000.25
    thread.complete_turn(turn, 'Completed', duration_s=1380.4)
    reloaded = Thread(tmp_path, 'main')._messages()
    assert reloaded[-1]['duration_s'] == 1380.4
    args = ('assistant', 'Completed', '', 1, False, 'a', 'main', 'Agent', False)
    assert 'Worked for 23 mins' in _turn(*args, duration_s=reloaded[-1]['duration_s'])
    assert 'Worked for' not in _turn(*args)


def test_live_clock_has_one_stable_timestamp_and_no_server_tick():
    html = _working_turn('', 'Agent', started=1000.25)
    assert 'data-work-started="1000.25"' in html
    assert _working_turn('', 'Agent', started=1000.25) == html
    assert 'data-work-started' not in _working_turn('', 'Agent')
