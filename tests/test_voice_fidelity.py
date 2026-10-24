"""The audible conversation must survive independently of the backend wording."""
import threading
import time
import pytest

from armada import thread_windows, voice_turns
from armada.threads import Thread
from tests.test_voice_preview import realm, start, wait_reply  # noqa: F401
from tests.test_voice_work import work, wait_idle  # noqa: F401


def test_native_words_replace_conversational_answer_but_preserve_work_evidence(realm):
    call, transport = start(realm)
    transport.segment('user', 'Explain the result', 'question')
    call.flush_speech(force=True)
    wait_reply(call)
    th = Thread(realm/'agents/a')
    before = th._messages()[-1]
    assert before['content'] == '' and before['voice_state'] == 'pending'
    identity = call.snapshot()['reply_ready']
    call.play_reply(identity)
    call.playback_received(identity)
    transport.emit('thread/realtime/transcript/delta', {'role':'assistant', 'delta':'Here is what happened.'})
    live = thread_windows.state(realm, 'a', 'main')['html']
    assert 'Here is what happened.' in live and 'Work result' in live
    transport.segment('assistant', 'Here is what happened.', 'spoken-one')
    transport.segment('assistant', 'Here is what happened.', 'spoken-one')
    call.playback_finished(identity)
    wait_idle()
    after = th._messages()[-1]
    assert after['content'] == 'Here is what happened.'
    assert after['work_result'] == before['work_result']
    assert after.get('status', 'ok') == before.get('status', 'ok')
    assert after['voice_state'] == 'spoken' and len(after['voice_segments']) == 1
    assert 'You: Here is what happened.' in th.render()
    assert before['work_result'] not in th.render()
    assert len(th._messages()) == 4
    from armada.webui.thread_window import render
    assert 'Here is what happened.' in render(realm, 'a', 'main')


def test_followup_waits_for_spoken_history_and_does_not_repeat_backend_wording(work):
    root, th, started, release, requests = work
    delivered = threading.Event()
    first = voice_turns.submit(root,'a','main','First question', voice_session='call',
        voice_item='one', spoken_reply=True, reply=lambda result: delivered)
    assert started.wait(2)
    second = voice_turns.submit(root,'a','main','Repeat what you said', voice_session='call', voice_item='two')
    release.set()
    deadline = time.monotonic()+3
    while len(th._messages()) < 5 and time.monotonic()<deadline:
        time.sleep(.01)
    assert len(requests)==1
    assert th.voice_segment(first, 'native-1', 'The proof is ready for you.')
    assert th.finish_voice(first)
    delivered.set()
    wait_idle()
    assert len(requests)==2
    assert 'You: The proof is ready for you.' in requests[1].prompt
    assert 'You: Actual tool work finished.' not in requests[1].prompt
    assert (root/'agents/a/proof.txt').read_text() == 'cobalt completed'


def test_ending_audio_keeps_partial_spoken_words_and_ignores_late_native_text(realm):
    call, transport = start(realm)
    transport.segment('user', 'Question', 'one')
    call.flush_speech(force=True)
    wait_reply(call)
    call.play_reply(call.snapshot()['reply_ready'])
    call.playback_received(call.playing)
    transport.emit('thread/realtime/transcript/delta', {'role':'assistant','delta':'You can start with'})
    call.set_mode('dictation')
    transport.segment('assistant', 'You can start with something never played.', 'late')
    wait_idle()
    th = Thread(realm/'agents/a')
    answer = th._messages()[-1]
    assert answer['content']=='You can start with' and answer['voice_state']=='interrupted'
    assert 'partial transcript' in th.render() and 'never played' not in th.render()
    assert 'Speech interrupted' in thread_windows.state(realm,'a','main')['html']


def test_audio_end_before_result_uses_explicit_text_fallback(work):
    root, th, started, release, _ = work
    delivery = threading.Event()
    voice_turns.submit(root,'a','main','Do it',voice_session='call',voice_item='one',
                       spoken_reply=True,reply=lambda result: None)
    assert started.wait(2)
    release.set()
    wait_idle()
    answer = th._messages()[-1]
    assert answer['voice_state']=='unspoken' and answer['work_result']=='Actual tool work finished.'
    assert 'Agent work result (not spoken)' in th.render()
    html = thread_windows.state(root,'a','main')['html']
    assert 'Text result · not spoken' in html and 'Actual tool work finished.' in html


@pytest.mark.parametrize('action', ['end', 'dictation'])
def test_generated_transcript_without_output_audio_is_not_conversation(realm, action):
    call, transport = start(realm)
    transport.segment('user', 'Question', 'one')
    call.flush_speech(force=True)
    wait_reply(call)
    call.play_reply(call.snapshot()['reply_ready'])
    call.playback_received('stale-reply')
    transport.segment('assistant', 'Words that never reached the audio player.', 'unheard')
    th = Thread(realm/'agents/a')
    assert not th._messages()[-1]['content']
    if action == 'end':
        call.stop()
    else:
        call.set_mode('dictation')
    wait_idle()
    answer = th._messages()[-1]
    assert answer['voice_state'] == 'unspoken' and not answer['content']
    assert 'never reached' not in th.render()
    assert 'Agent work result (not spoken)' in th.render()
    assert 'Text result · not spoken' in thread_windows.state(realm,'a','main')['html']


def test_voice_update_does_not_recreate_deleted_turn_or_drop_new_messages(realm):
    th = Thread(realm/'agents/a')
    turn = th.begin_turn('Question')
    th.complete_turn(turn,'Backend result',spoken_reply=True,outputs=[{'name':'proof'}],status='error')
    th.append('Another question', 'Another answer')
    assert th.voice_segment(turn,'part','Spoken failure explanation')
    assert th._messages()[-1]['content']=='Another answer'
    original = next(m for m in th._messages() if m.get('voice_state'))
    assert original['status']=='error' and original['outputs']==[{'name':'proof'}]
    th.truncate(2)
    assert not th.voice_segment(turn,'late','Do not recreate this')
    assert len(th._messages())==2


def test_pending_voice_result_is_not_compacted(realm):
    from armada.engine import MockEngine
    th = Thread(realm/'agents/a')
    turn = th.begin_turn('Question')
    th.complete_turn(turn,'Result',spoken_reply=True)
    th.compact_if_needed(MockEngine(), threshold_chars=1, keep_recent_pairs=0)
    assert any(m.get('turn')==turn for m in th._messages())
    assert th.voice_segment(turn,'native','Still here')
