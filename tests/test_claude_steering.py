"""Claude follow-ups use native UUID delivery evidence, never a transport-only echo."""
import json
import sys
from armada.engine.claude_steering import ClaudeSteering


def test_receipt_waits_for_model_incorporation_and_terminal_result():
    control = ClaudeSteering();control.enabled = True
    receipts = []
    control.submit('request-0001', 'Change focus', lambda *outcome: receipts.append(outcome))
    sent = [];control.drain(sent.append)
    message = sent[0];identity = message['uuid']
    assert message['priority'] == 'now' and message['origin'] == {'kind': 'human'}
    assert message['message'] == {'role': 'user', 'content': 'Change focus'}
    assert not any(key in message for key in ('tools', 'model', 'permissionMode', 'cwd'))
    control.observe({'type': 'user', 'isReplay': True, 'uuid': identity})
    assert receipts == [] and control.waiting
    control.observe({'type': 'assistant', 'user_message_uuids': [identity]})
    assert receipts == [('accepted', '')] and control.waiting
    control.observe({'type': 'result', 'user_message_uuids': [identity], 'num_turns': 1})
    assert not control.waiting
    control.close();assert receipts == [('accepted', '')]


def test_dropped_or_unsent_input_never_claims_acceptance():
    for sent in (False, True):
        control = ClaudeSteering();control.enabled = True;receipts = []
        control.submit('request-0001', 'Message', lambda *outcome: receipts.append(outcome))
        if sent:control.drain(lambda _: None)
        control.close()
        assert receipts[0][0] == ('uncertain' if sent else 'rejected')
        assert not control.waiting and not control.ready


def test_real_rpc_owner_keeps_session_alive_for_native_followup(tmp_path, monkeypatch):
    from armada.engine.claude import ClaudeEngine
    script = tmp_path/'provider.py'
    script.write_text('''import json,sys
def emit(m):print(json.dumps(m),flush=True)
for line in sys.stdin:
 m=json.loads(line)
 if m['type']=='control_request':
  emit({'type':'control_response','response':{'subtype':'success','request_id':m['request_id'],'response':{'claude_code_version':'2.1.319'}}})
 elif m['type']=='user' and not m.get('uuid'):
  emit({'type':'system','subtype':'session_state_changed','state':'running'})
  emit({'type':'system','subtype':'init','tools':[]})
  emit({'type':'assistant','message':{'content':[{'type':'text','text':'Working'}]}})
 elif m['type']=='user':
  assert m['priority']=='now' and m['origin']=={'kind':'human'}
  emit({'type':'result','subtype':'success','is_error':False,'num_turns':1,'result':'Earlier answer','usage':{},'modelUsage':{}})
  emit({'type':'user','uuid':m['uuid'],'isReplay':True,'message':{'role':'user','content':m['message']['content']}})
  emit({'type':'assistant','user_message_uuids':[m['uuid']],'message':{'content':[{'type':'text','text':'Revised focus'}]}})
  emit({'type':'result','subtype':'success','is_error':False,'num_turns':2,'result':'Revised focus','user_message_uuids':[m['uuid']],'usage':{},'modelUsage':{}})
  emit({'type':'system','subtype':'session_state_changed','state':'idle'})
''', encoding='utf-8')
    engine = ClaudeEngine()
    monkeypatch.setattr(engine, '_launcher', lambda: [sys.executable, '-u', str(script)])
    monkeypatch.setattr(engine, '_mcp_args', lambda *a, **kw: [])
    handles, receipts = [], []
    def receive(event):
        if event.get('kind') == 'text' and event.get('text') == 'Working':
            assert handles[0].can_steer
            handles[0].steer('request-0001', 'Change focus', lambda *value: receipts.append(value))
    receive.interactive_questions = True
    result = engine.run_stream('System', 'Task', cwd=str(tmp_path), timeout=10,
                               on_event=receive, on_proc=handles.append)
    assert result.ok, result.error
    assert result.output == 'Earlier answer\n\nRevised focus'
    assert receipts == [('accepted', '')]
    assert not handles[0].can_steer
