"""Real duplex subprocesses and owner HTTP admission, using synthetic questions only."""
import json
import http.client
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
from armada import questions,thread_windows
from armada.engine.questions import QuestionControl,QuestionProcess,normalize,validate_answers
from armada.execution import RunSession
from armada.request_context import RunContext
from armada.threads import Thread
from golden_support import build_fixture,ServedRealm


QUESTION={'id':'color','header':'Color','question':'Which color?','options':[
    {'label':'Blue','description':'Synthetic choice'},{'label':'Green','description':'Another choice'}],'isOther':True}


def test_answer_requires_valid_choices_and_durability_before_delivery():
    control=QuestionControl(lambda _:None)
    control.add('native','codex',[QUESTION],lambda answers,skipped:{'answers':answers})
    row=control.snapshot()[0]
    def failed(_):raise OSError('Synthetic disk refusal')
    with pytest.raises(OSError):
        control.answer(row['id'],{'color':['Blue']},persist=failed)
    sent=[];control.drain(sent.append)
    assert not sent and control.waiting
    control.answer(row['id'],{'color':['Blue']})
    control.answer(row['id'],{'color':['Blue']})
    with pytest.raises(ValueError,match='already answered'):
        control.answer(row['id'],{'color':['Green']})
    control.drain(sent.append);control.drain(sent.append)
    assert sent==[{'answers':{'color':['Blue']}}]
    control.close(success=True)
    assert control.snapshot()[0]['status']=='answered'


def test_question_validation_multiselect_secrets_and_limits():
    rows=normalize([{**QUESTION,'multiSelect':True}],'claude')
    identity=QUESTION['question']
    assert validate_answers(rows,{identity:['Blue','Custom text']})[identity]==['Blue','Custom text']
    with pytest.raises(ValueError):validate_answers(rows,{})
    with pytest.raises(ValueError):normalize([{**QUESTION,'isSecret':True}],'codex')
    with pytest.raises(ValueError):normalize([QUESTION]*9,'codex')
    fixed=normalize([{**QUESTION,'isOther':False}],'codex')
    with pytest.raises(ValueError):validate_answers(fixed,{'color':['Unknown']})
    with pytest.raises(ValueError):validate_answers(fixed,{'color':['Blue','Green']})
    assert validate_answers(fixed,{},True)=={}


@pytest.mark.parametrize('provider',['claude','codex'])
@pytest.mark.parametrize('stop',[False,True])
def test_duplex_native_questions_and_approval_denials(tmp_path,monkeypatch,provider,stop):
    script=tmp_path/'provider.py'
    script.write_text('''import json,sys,time
def send(value):print(json.dumps(value),flush=True)
provider='''+repr(provider)+'''
for line in sys.stdin:
 m=json.loads(line)
 if provider=='codex':
  if m.get('method')=='initialize':
   assert m['params']['capabilities']['experimentalApi']
   send({'id':1,'result':{}})
  elif m.get('method')=='thread/start':
   assert m['params']['approvalPolicy']=='never'
   send({'id':2,'result':{'thread':{'id':'native-thread'}}})
  elif m.get('method')=='turn/start':
   send({'id':3,'result':{'turn':{'id':'native-turn'}}})
   send({'id':'approval','method':'item/commandExecution/requestApproval','params':{}})
  elif m.get('id')=='approval':
   assert 'error' in m
   send({'method':'item/started','params':{'threadId':'native-thread','item':{'id':'mcp-item','type':'mcpToolCall','server':'ungranted','tool':'never_execute','arguments':{}}}})
   send({'id':'mcp-approval','method':'item/tool/requestUserInput','params':{
    'threadId':'native-thread','turnId':'native-turn','itemId':'mcp-item','isBlocking':True,'questions':[
     {'id':'approve','header':'Approve','question':'Allow this tool?','options':[{'label':'Allow','description':'Never grant'}]}]}})
  elif m.get('id')=='mcp-approval':
   assert 'error' in m
   send({'id':'ask','method':'item/tool/requestUserInput','params':{
    'threadId':'native-thread','turnId':'native-turn','itemId':'item','isBlocking':True,'questions':[
     {'id':'color','header':'Color','question':'Which color?','options':[{'label':'Blue','description':'Synthetic'}]}]}})
  elif m.get('id')=='ask':
   assert m['result']['answers']=={'color':{'answers':['Blue']}}
   send({'method':'serverRequest/resolved','params':{'threadId':'native-thread','requestId':'ask'}})
   send({'method':'item/agentMessage/delta','params':{'threadId':'native-thread','turnId':'native-turn','itemId':'answer','delta':'Answer received'}})
   send({'method':'turn/completed','params':{'threadId':'native-thread','turn':{'status':'completed'}}})
 else:
  if m.get('type')=='control_request':
   send({'type':'control_response','response':{'subtype':'success','request_id':m['request_id'],'response':{}}})
  elif m.get('type')=='user':
   send({'type':'system','subtype':'session_state_changed','state':'running','sdk_host_only':True})
   send({'type':'control_request','request_id':'approval','request':{'subtype':'can_use_tool','tool_name':'Bash','input':{'command':'never-run'}}})
  elif m.get('type')=='control_response':
   response=m['response']
   if response['request_id']=='approval':
    assert response['response']['behavior']=='deny'
    send({'type':'control_request','request_id':'ask','request':{'subtype':'can_use_tool','tool_name':'AskUserQuestion','input':{'questions':[
     {'header':'Color','question':'Which color?','options':[{'label':'Blue','description':'Synthetic'}],'multiSelect':False}]}}})
   else:
    assert response['response']['behavior']=='allow'
    assert response['response']['updatedInput']['answers']=={'Which color?':'Blue'}
    send({'type':'system','subtype':'task_started','task_id':'background','task_type':'local_agent'})
    send({'type':'result','subtype':'success','is_error':False,'result':'Early turn result','usage':{},'modelUsage':{}})
    send({'type':'system','subtype':'task_notification','task_id':'background','status':'completed'})
    send({'type':'assistant','message':{'content':[{'type':'text','text':'Answer received'}]}})
    send({'type':'result','subtype':'success','is_error':False,'result':'Answer received','usage':{},'modelUsage':{}})
    send({'type':'system','subtype':'session_state_changed','state':'idle','sdk_host_only':True})
''',encoding='utf-8')
    if provider=='codex':
        from armada.engine.codex import CodexEngine
        engine=CodexEngine()
    else:
        from armada.engine.claude import ClaudeEngine
        engine=ClaudeEngine()
        monkeypatch.setattr(engine,'_direct',lambda:True)
        monkeypatch.setattr(engine,'_env',lambda:{})
    monkeypatch.setattr(engine,'_launcher',lambda:[sys.executable,'-u',str(script)])
    monkeypatch.setattr(engine,'_mcp_args',lambda *a,**k:[])
    handle=[];events=[]
    def receive(event):
        events.append(event)
        if event.get('kind')=='question' and event['request']['status']=='pending':
            if stop:handle[0].kill()
            else:
                row=event['request']
                handle[0].questions.answer(row['id'],{row['questions'][0]['id']:['Blue']})
    receive.interactive_questions=True
    result=engine.run_stream('Synthetic protocol test','Ask a synthetic question',cwd=str(tmp_path),timeout=10,
        on_event=receive,on_proc=handle.append)
    if stop:
        assert result.cancelled and not result.ok
        assert handle[0].questions.snapshot()[0]['status']=='cancelled'
    else:
        assert result.ok,result.error
        assert result.output=='Answer received'
        assert handle[0].questions.snapshot()[0]['status']=='answered'
    assert any(e.get('kind')=='question' for e in events)


def test_owner_answers_are_run_bound_idempotent_and_survive_in_history(tmp_path):
    root=build_fixture(tmp_path/'realm')
    thread=Thread(Path(root)/'agents/captain','main')
    turn=thread.begin_turn('Owner question test')
    context=RunContext.capture(root,'captain','main','question-run')
    control=QuestionControl(lambda event:questions.record(thread,turn,context.run_id,event['request']))
    with ServedRealm(root) as server,RunSession(context) as session:
        session.active.steering_turn=turn
        session.bind(QuestionProcess(SimpleNamespace(kill=lambda:None,poll=lambda:None,pid=0),control))
        control.add('native','codex',[QUESTION],lambda answers,skipped:{'answers':answers})
        from armada.webui.agentbits import _agent_activity
        from armada.webui.activity_monitor import content
        from armada import reader
        assert questions.waiting(root,'captain')==['main']
        assert _agent_activity(root,'captain')=='input'
        monitor=content(reader.read(root),root)
        assert 'data-activity-key="needs-input:captain"' in monitor
        assert 'Question awaiting your answer' in monitor
        assert 'data-activity-key="working:captain"' not in monitor
        row=thread_windows.state(root,'captain','main')['questions'][0]
        body={'agent':'captain','thread':'main','run_id':context.run_id,'question_id':row['id'],'answers':{'color':['<Custom>']}}
        assert not server.post('/api/thread-answer',{**body,'run_id':'stale-run'})['ok']
        assert server.post('/api/thread-answer',body)['ok']
        assert server.post('/api/thread-answer',body)['ok']
        assert not server.post('/api/thread-answer',{**body,'answers':{'color':['Green']}})['ok']
        sent=[];control.drain(sent.append);control.drain(sent.append)
        assert sent==[{'answers':{'color':['<Custom>']}}]
        assert not thread_windows.state(root,'captain','main')['questions'], 'Sent questions must close before the ongoing run finishes.'
        control.close(success=True)
        thread.complete_turn(turn,'Question answered')
    html=thread_windows.state(root,'captain','main')['html']
    assert 'Which color?' in html and '&lt;Custom&gt;' in html and '<Custom>' not in html
    assert 'Owner answer: <Custom>' in thread.render()


def test_companion_answer_keeps_original_realm_after_cockpit_switch(tmp_path):
    from urllib.parse import urlencode
    root=build_fixture(tmp_path/'realm')
    other=build_fixture(tmp_path/'other')
    thread=Thread(Path(root)/'agents/captain','main')
    turn=thread.begin_turn('Synthetic realm-bound question')
    context=RunContext.capture(root,'captain','main','same-question-run')
    control=QuestionControl(lambda event:questions.record(thread,turn,context.run_id,event['request']))
    with ServedRealm(root) as server,RunSession(context) as session:
        session.active.steering_turn=turn
        session.bind(QuestionProcess(SimpleNamespace(kill=lambda:None,poll=lambda:None,pid=0),control))
        control.add('native','codex',[QUESTION],lambda answers,skipped:{'answers':answers})
        identity=control.snapshot()[0]['id']
        headers={**server.auth_headers(),'Content-Type':'application/json','X-Armada-Realm':context.realm.realm_id}
        def request(path,body=None,companion=False):
            connection=http.client.HTTPConnection('127.0.0.1',server.port,timeout=10)
            try:
                connection.request('POST' if body else 'GET',path,json.dumps(body) if body else None,
                    {**headers,**({'X-Armada-Companion':'thread'} if companion else {})})
                response=connection.getresponse()
                return response.status,response.read()
            finally:
                connection.close()
        assert request('/switch?'+urlencode({'path':other}))[0]==302
        body={'agent':'captain','thread':'main','run_id':context.run_id,'question_id':identity,'answers':{'color':['Blue']}}
        assert request('/api/thread-answer',body)[0]==409
        status,raw=request('/api/thread-answer',body,True)
        assert status==200 and json.loads(raw)['ok']
        assert not questions.waiting(other,'captain')
        sent=[];control.drain(sent.append)
        assert sent==[{'answers':{'color':['Blue']}}]
        control.close(success=True)
