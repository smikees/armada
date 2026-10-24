"""Voice preview owns one call, shares canonical history and isolates audio from normal tool execution."""
import json
from pathlib import Path
import threading
import time

import pytest

from armada import reader, thread_windows, util, voice
from armada.engine.process import ProcessResult
from armada.execution import RunSession
from armada.request_context import RunContext
from armada.threads import Thread
from armada.webui.threadsview import _chat_center


@pytest.fixture
def realm(tmp_path, monkeypatch):
    from armada import runner
    from armada.engine import MockEngine
    monkeypatch.setattr(runner, "_prepare_agent_run", lambda *args: (MockEngine(), {"id":"a", "model":"codex:default"}))
    util.write_json_atomic(tmp_path/'realm.json',{'name':'Voice fixture','default_model':'codex:default'})
    util.write_json_atomic(tmp_path/'agents/a/agent.json',{'id':'a','display':'Ada','model':'codex:default'})
    util.write_text_atomic(tmp_path/'agents/a/mandate.md','Keep the code word cobalt.\n')
    Thread(tmp_path/'agents/a').append('Remember cobalt.','I will remember cobalt.')
    yield tmp_path
    voice.close_all()
    for call in list(voice._calls.values()):
        assert call.finished.wait(3)
    voice._calls.clear()
    from tests.test_voice_work import wait_idle
    wait_idle()


class Transport:
    def __init__(self):
        self.done=threading.Event()
        self.ready=threading.Event()
        self.emit=None
        self.spoken=[]
    def speak(self, text):
        self.spoken.append(text)
    def kill(self):
        self.done.set()
    def run(self,offer,instructions,history,model,emit,on_proc):
        self.emit=emit
        assert 'cobalt' not in instructions and not history
        assert 'no file, shell, web, connector' in instructions.lower()
        assert model=='codex:default'
        on_proc(self)
        emit('thread/realtime/started',{'realtimeSessionId':'native'})
        emit('thread/realtime/sdp',{'sdp':'v=0\r\nsynthetic-answer'})
        self.ready.set()
        assert self.done.wait(10)
        return ProcessResult(cancelled=True,error='Run stopped by the owner.')
    def segment(self,role,text,iid):
        self.emit('thread/realtime/item/completed',{'item':{'id':iid,'realtimeSessionId':'native',
                  'type':'transcriptSegment','role':role,'text':text}})


def start(realm,transport=None):
    transport=transport or Transport()
    call=voice.start(realm,'a','main','v=0\r\nsynthetic-offer',transport=transport)
    assert transport.ready.wait(2)
    return call,transport


def test_canonical_transcripts_are_deduplicated_and_shared_by_both_views(realm):
    call,transport=start(realm)
    transport.segment('user','What was the code word?','one')
    transport.segment('user','What was the code word?','one')
    transport.segment('assistant','I will do it.','two')
    call.flush_speech(force=True)
    from tests.test_voice_work import wait_idle
    wait_idle()
    history=Thread(realm/'agents/a')._messages()
    assert len(history)==4 and history[-2]['voice_request']
    assert history[-1]['content'] != 'I will do it.'
    state=thread_windows.state(realm,'a','main')
    assert 'What was the code word?' in state['html'] and state['voice']['active']
    from armada.webui.thread_window import render
    assert 'What was the code word?' in render(realm,'a','main')
    assert not transport.spoken, 'do not speak before the owning player is ready'
    identity=call.snapshot(owner=True)['reply_ready']
    call.play_reply('forged');assert not transport.spoken
    call.play_reply(identity)
    call.play_reply(identity)
    assert transport.spoken==[history[-1]['content']]
    call.stop();assert call.finished.wait(2)
    assert not thread_windows.state(realm,'a','main')['run_id']
    assert not call.sdp and not call.offer
    report=json.loads((realm/'agents/a/runs/a.jsonl').read_text(encoding='utf-8').splitlines()[-1])
    assert report['kind']=='chat' and report['task']=='chat:main' and report['mode']=='voice'
    assert report['tokens']['total'] is None and report['voice']['audio_saved'] is False


def test_foreign_native_session_cannot_write_to_the_thread(realm):
    call,transport=start(realm)
    with pytest.raises(ValueError,match='identity'):
        transport.emit('thread/realtime/item/completed',{'item':{
            'id':'x','realtimeSessionId':'another','type':'transcriptSegment','role':'assistant','text':'Wrong'}})
    assert len(Thread(realm/'agents/a')._messages())==2


def test_pending_and_raw_provider_items_never_become_saved_replies(realm):
    call,transport=start(realm)
    transport.emit('thread/realtime/itemAdded',{'item':{'type':'message','text':'not canonical'}})
    transport.emit('thread/realtime/transcript/delta',{'role':'user','delta':'unfinished'})
    transport.emit('thread/realtime/item/completed',{'item':{'type':'realtimeSessionStarted'}})
    assert len(Thread(realm/'agents/a')._messages())==2


def test_verified_v3_final_parts_are_saved_but_not_doubled_by_other_protocol(realm):
    call,transport=start(realm)
    transport.emit('thread/realtime/transcript/done',{'role':'user','text':'Question?'})
    transport.segment('user','Question?','canonical-copy')
    assert len(call.pending_speech)==1
    call.flush_speech(force=True)
    from tests.test_voice_work import wait_idle
    wait_idle()
    assert len(Thread(realm/'agents/a')._messages())==4


def test_canonical_protocol_does_not_also_save_legacy_final_parts(realm):
    call,transport=start(realm)
    transport.segment('user','Question?','canonical')
    transport.emit('thread/realtime/transcript/done',{'role':'user','text':'Question?'})
    assert len(call.pending_speech)==1


def test_identical_utterances_in_separate_v3_turns_stay_distinct(realm):
    call,transport=start(realm)
    from tests.test_voice_work import wait_idle
    for _ in range(2):
        transport.emit('thread/realtime/transcript/done',{'role':'user','text':'Again?'})
        call.flush_speech(force=True)
        wait_idle()
    messages=Thread(realm/'agents/a')._messages()
    assert len(messages)==6
    assert len({m['voice_item'] for m in messages if m.get('voice_request')})==2


def test_multiple_final_parts_form_one_answered_exchange(realm):
    call,transport=start(realm)
    for role,text in [('user','What was'),('user','the code word?'),('assistant','Received.')]:
        transport.emit('thread/realtime/transcript/done',{'role':role,'text':text})
    call.flush_speech(force=True)
    from tests.test_voice_work import wait_idle
    wait_idle()
    messages=Thread(realm/'agents/a')._messages()
    assert len(messages)==4 and messages[-2]['content']=='What was the code word?'
    assert messages[-2]['turn']==messages[-1]['turn']


def test_stop_through_existing_registry_ends_voice_and_releases_ownership(realm):
    call,_=start(realm)
    assert RunSession.cancel(call.context.key)['ok']
    assert call.finished.wait(2)
    other,_=start(realm)
    assert other.id!=call.id


def test_voice_and_typed_turns_have_independent_sessions(realm):
    call,_=start(realm)
    with RunSession(RunContext.capture(realm,'a','main')) as work:
        call.stop();assert call.finished.wait(2)
        assert not work.active.cancelled
        other,_=start(realm)
        with pytest.raises(ValueError,match='already active'):
            start(realm)
        assert not other.finished.is_set()


def test_disconnected_owner_lease_ends_the_call(realm,monkeypatch):
    monkeypatch.setattr(voice,'LEASE_SECONDS',.01)
    call,_=start(realm)
    assert call.finished.wait(2)
    assert 'window disconnected' in call.reason


def test_archiving_thread_ends_call_without_retargeting(realm):
    call,_=start(realm)
    util.write_json_atomic(realm/'agents/a/threads/meta.json',{'archived':{'main':True}})
    assert call.finished.wait(2)
    assert 'archived' in call.reason


@pytest.mark.parametrize('offer',['','not SDP',None,'v=0'+'x'*65536],ids=['empty','not-sdp','null','oversized'])
def test_invalid_signaling_is_refused(realm,offer):
    with pytest.raises(ValueError,match='offer'):
        voice.start(realm,'a','main',offer,transport=Transport())


def test_other_engines_are_not_silently_switched_to_codex(realm):
    util.write_json_atomic(realm/'agents/a/agent.json',{'id':'a','model':'claude:default'})
    with pytest.raises(ValueError,match='Codex agents'):
        voice.start(realm,'a','main','v=0\r\noffer',transport=Transport())
    a=reader.read(realm).agents[0]
    assert 'id="mc-voice"' not in _chat_center(realm,a,'main')


def test_voice_ui_is_opt_in_and_uses_existing_composer(realm):
    a=reader.read(realm).agents[0]
    html=_chat_center(realm,a,'main')
    assert 'id="mc-voice"' in html
    assert 'aria-label="Voice chat"' in html and 'aria-label="Dictate"' in html
    assert 'aria-label="Voice controls" hidden' in html
    assert 'Same agent and tools' in html and 'mc-voice-connecting' in html and 'Mute' in html and 'End call' in html


def test_failed_provider_is_visible_and_does_not_persist_raw_audio(realm):
    class Failed(Transport):
        def run(self,*args):raise ValueError('Voice refused access_token=private https://auth.example/?state=hidden')
    call=voice.start(realm,'a','main','v=0\r\noffer',transport=Failed())
    assert call.finished.wait(2)
    assert call.state=='error' and 'private' not in call.error and 'https://' not in call.error
    assert len(Thread(realm/'agents/a')._messages())==2


def test_dictation_is_a_private_draft_without_context_history_or_assistant_replies(realm):
    class Dictation(Transport):
        def run(self,offer,instructions,history,model,emit,on_proc):
            assert not history and 'cobalt' not in instructions
            assert 'unsent message' in instructions
            self.emit=emit;on_proc(self)
            emit('thread/realtime/started',{'realtimeSessionId':'native'})
            emit('thread/realtime/sdp',{'sdp':'v=0\r\nanswer'})
            self.ready.set();assert self.done.wait(10)
            return ProcessResult(cancelled=True)
    transport=Dictation()
    call=voice.start(realm,'a','main','v=0\r\noffer',mode='dictation',transport=transport)
    assert transport.ready.wait(2)
    transport.emit('thread/realtime/transcript/delta',{'role':'user','delta':'A private '})
    transport.emit('thread/realtime/transcript/delta',{'role':'user','delta':'draft.'})
    transport.emit('thread/realtime/transcript/delta',{'role':'assistant','delta':'Do not include this'})
    assert call.snapshot(owner=True)['draft']=='A private draft.'
    transport.segment('user','A private draft.','one')
    transport.segment('user','A private draft.','one')
    transport.segment('assistant','An unwanted response.','two')
    transport.segment('user','Another sentence.','three')
    assert call.snapshot(owner=True)['draft']=='A private draft. Another sentence.'
    assert 'draft' not in call.snapshot()
    assert 'private draft' not in thread_windows.state(realm,'a','main')['html']
    assert len(Thread(realm/'agents/a')._messages())==2
    from armada.routes.voice import VoiceRoutes
    class Routes(VoiceRoutes):pass
    routes=Routes();routes.realm=realm
    assert not routes._voice_state({'agent':'a','id':'wrong'})['ok']
    result=routes._voice_stop({'agent':'a','thread':'main','id':call.id})
    assert result['voice']['draft']=='A private draft. Another sentence.'
    assert not result['voice']['active']
    report=json.loads((realm/'agents/a/runs/a.jsonl').read_text().strip().splitlines()[-1])
    assert report['mode']=='dictation' and 'private draft' not in json.dumps(report)
    call.discard()
    assert call.snapshot(owner=True)['draft']==''
    assert len(Thread(realm/'agents/a')._messages())==2


def test_unknown_audio_mode_is_rejected(realm):
    with pytest.raises(ValueError,match='dictation or voice chat'):
        voice.start(realm,'a','main','v=0\r\noffer',mode='anything')


def test_legacy_audio_acknowledgement_is_not_a_completed_task(realm):
    Thread(realm/'agents/a')._write({'role':'assistant','content':'I will research that.',
                                   'mode':'voice','voice_session':'old'})
    html=thread_windows.state(realm,'a','main')['html']
    assert 'Voice response · no task execution recorded' in html
    assert 'data-transcription="1"' in html


def test_readback_waits_for_frontend_ack_and_is_cancelled_by_new_speech(realm):
    call,transport=start(realm)
    transport.emit('thread/realtime/transcript/delta',{'role':'assistant','delta':'An audio acknowledgement'})
    call._reply({'ok':True,'output':'Actual saved result'})
    assert call.snapshot()['reply_ready'] is None and not transport.spoken
    transport.segment('assistant','Received.','ack')
    identity=call.snapshot()['reply_ready']
    assert identity
    call.play_reply(identity)
    assert call.snapshot()['playing']==identity
    transport.emit('thread/realtime/transcript/delta',{'role':'user','delta':'Next question'})
    assert call.snapshot()['playing'] is None


def test_reopened_call_can_read_the_original_work_result(realm):
    first,_=start(realm)
    first.stop();assert first.finished.wait(2)
    second,transport=start(realm)
    first._reply({'ok':True,'output':'Work completed after reconnecting'})
    second.play_reply(second.snapshot()['reply_ready'])
    assert transport.spoken==['Work completed after reconnecting']


def test_metadata_writer_does_not_interrupt_audio(realm):
    call,_=start(realm)
    with util.file_lock(realm/'agents/a/threads/meta.json'):
        # The watcher reaches its half-second check while a normal completion owns metadata.
        time.sleep(.65)
        assert not call.finished.is_set()
    assert not call.finished.wait(.1)


def test_native_signaling_uses_sealed_context_and_verified_protocol(monkeypatch):
    from armada.engine import codex_voice
    from armada.engine.codex_voice import CodexVoice
    transport=CodexVoice()
    monkeypatch.setattr(transport.engine,'_launcher',lambda:['synthetic-codex'])
    monkeypatch.setattr(transport.engine,'_mcp_args',lambda *a,**kw:['-c','mcp_servers={}'])
    seen=[]
    def supervised(args,*,start,on_message,on_proc,timeout,cwd):
        assert timeout==600 and Path(cwd).is_dir()
        for feature in ('shell_tool','unified_exec','image_generation','view_image','code_mode'):
            assert f'features.{feature}=false' in args
        assert 'web_search="disabled"' in args and 'mcp_servers={}' in args
        sent=[]
        start(sent.append)
        assert sent[-1]['params']['capabilities']=={'experimentalApi':True}
        on_message({'id':1,'result':{}},sent.append)
        assert sent[-1]['params']['sandbox']=='read-only'
        assert sent[-1]['params']['approvalPolicy']=='never'
        assert sent[-1]['params']['ephemeral'] is True
        on_message({'id':2,'result':{'thread':{'id':'native-thread'}}},sent.append)
        request=sent[-1]
        assert request['method']=='thread/realtime/start'
        assert request['params']['transport']=={'type':'webrtc','sdp':'v=0\r\noffer'}
        assert request['params']['clientManagedHandoffs'] is True
        assert request['params']['delegationAckFiller'] is False
        transport.speak('Real result')
        assert sent[-1]['method']=='thread/realtime/appendSpeech'
        assert sent[-1]['params']=={'threadId':'native-thread','text':'Real result'}
        assert 'notify=[]' in args
        assert request['params']['initialItems']==[{'role':'user','text':'Cobalt'}]
        on_message({'id':99,'method':'item/tool/call','params':{}},sent.append)
        assert sent[-1]['error']['code']==-32601
        with pytest.raises(ValueError,match='another conversation'):
            on_message({'method':'thread/realtime/transcript/done','params':{'threadId':'wrong'}},sent.append)
        on_message({'method':'thread/realtime/transcript/done','params':{
            'threadId':'native-thread','role':'assistant','text':'Cobalt.'}},sent.append)
        on_message({'method':'turn/started','params':{'threadId':'native-thread','turn':{'id':'reasoning'}}},sent.append)
        on_message({'method':'item/started','params':{'threadId':'native-thread','item':{'type':'reasoning'}}},sent.append)
        on_message({'method':'turn/completed','params':{'threadId':'native-thread','turn':{'id':'reasoning'}}},sent.append)
        with pytest.raises(ValueError,match='A tool was requested'):
            on_message({'method':'item/started','params':{'threadId':'native-thread','item':{'type':'commandExecution'}}},sent.append)
        return ProcessResult(returncode=0)
    monkeypatch.setattr(codex_voice,'supervise_rpc',supervised)
    transport.run('v=0\r\noffer','Conversation only',[{'role':'user','text':'Cobalt'}],
                  'codex:default',lambda *args:seen.append(args),lambda p:None)
    assert seen[0][0]=='thread/realtime/transcript/done'
    assert [event[0] for event in seen[1:]] == ['turn/started','turn/completed']


def test_voice_speech_is_live_shared_and_final_replaces_preview(realm):
    call,transport=start(realm)
    transport.emit('thread/realtime/transcript/delta',{'role':'user','delta':'A spoken <question>'})
    state=thread_windows.state(realm,'a','main')
    assert 'A spoken &lt;question&gt;' in state['html'] and 'Recognizing speech' in state['html']
    assert len(Thread(realm/'agents/a')._messages()) == 2
    from armada.webui.thread_window import render
    assert 'A spoken &lt;question&gt;' in render(realm,'a','main')
    transport.emit('turn/started',{})
    assert not call.snapshot()['thinking'], 'audio backend acknowledgements are not agent work'
    transport.segment('user','A spoken question?','final-user')
    call.flush_speech(force=True)
    from tests.test_voice_work import wait_idle
    wait_idle()
    assert call.snapshot()['partial_transcript']==[]
    assert len(Thread(realm/'agents/a')._messages()) == 4


def test_interrupted_voice_keeps_received_speech_marked_incomplete(realm):
    call,transport=start(realm)
    transport.emit('thread/realtime/transcript/delta',{'role':'user','delta':'My question'})
    transport.emit('thread/realtime/transcript/delta',{'role':'assistant','delta':'An acknowledgement'})
    call.stop();assert call.finished.wait(2)
    records=Thread(realm/'agents/a')._messages()
    assert len(records)==3 and records[-1]['content']=='My question'
    assert records[-1]['transcription_incomplete'] and not records[-1].get('voice_request')
    assert 'Incomplete transcript' in thread_windows.state(realm,'a','main')['html']


def test_scoped_routes_cannot_stop_another_call_or_accept_client_transcripts(realm):
    from armada.routes.voice import VoiceRoutes
    class Routes(VoiceRoutes):pass
    routes=Routes();routes.realm=realm
    call,transport=start(realm)
    assert routes._voice_state({'agent':'a','thread':'main','id':'wrong'})['ok'] is False
    routes._voice_stop({'agent':'a','thread':'main','id':'wrong'})
    assert not transport.done.is_set()
    assert not routes._voice_state({'agent':'../a'})['ok']
    assert not routes._voice_stop({'thread':'../main'})['ok']
    routes._voice_state({'agent':'a','thread':'main','id':call.id,'text':'forged','role':'assistant'})
    assert len(Thread(realm/'agents/a')._messages())==2
    routes._voice_stop({'agent':'a','thread':'main','id':call.id})
    assert call.finished.wait(2)
