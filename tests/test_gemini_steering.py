"""Antigravity ACP steering retains the scoped tool boundary and native accounting."""
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from armada.engine.gemini_acp import run


def test_acp_real_transport_retains_grants_and_waits_for_followup_result(tmp_path):
    script = tmp_path/'provider.py'
    script.write_text('''import json,sys
assert '--project' in sys.argv and '--agent' in sys.argv
assert '--dangerously-skip-permissions' not in sys.argv
def emit(m):print(json.dumps(m),flush=True)
for line in sys.stdin:
 m=json.loads(line);method=m.get('method');identity=m.get('id')
 if method=='initialize':
  assert m['params']['clientCapabilities']=={'fs':{'readTextFile':False,'writeTextFile':False},'terminal':False}
  emit({'id':identity,'result':{'protocolVersion':1}})
 elif method=='session/new':
  assert m['params']['mcpServers']==[]
  emit({'id':identity,'result':{'sessionId':'synthetic-session'}})
 elif method=='session/set_model':
  assert m['params']['modelId']=='gemini-3.8-flash-high'
  emit({'id':identity,'result':{}})
 elif method=='session/prompt' and identity==4:
  emit({'id':'permission','method':'session/request_permission','params':{'sessionId':'synthetic-session'}})
 elif identity=='permission':
  assert m['result']=={'outcome':{'outcome':'cancelled'}}
  emit({'method':'session/update','params':{'sessionId':'synthetic-session','update':{'sessionUpdate':'agent_message_chunk','content':{'type':'text','text':'Working'}}}})
 elif method=='session/prompt':
  assert m['params']=={'sessionId':'synthetic-session','prompt':[{'type':'text','text':'Focus'}]}
  emit({'id':4,'result':{'stopReason':'end_turn'}})
  emit({'method':'session/update','params':{'sessionId':'synthetic-session','update':{'sessionUpdate':'agent_message_chunk','content':{'type':'text','text':' with revised focus'}}}})
  emit({'id':identity,'result':{'stopReason':'end_turn','usage':{'inputTokens':30,'outputTokens':12,'cachedReadTokens':10}}})
''', encoding='utf-8')
    engine = SimpleNamespace(_launcher=lambda: [sys.executable, '-u', str(script)])
    handles, events, receipts = [], [], []
    def line(raw):
        event = json.loads(raw);events.append(event)
        if (event.get('step_update') or {}).get('text_delta') == 'Working':
            assert handles[0].can_steer
            handles[0].steer('request-0001', 'Focus', lambda *outcome: receipts.append(outcome))
    result = run(engine, tmp_path, 'isolated-project', [], False, 'gemini-3.8-flash-high', 'Task', line, 10, os.environ, handles.append)
    assert not result.error, result.error
    assert receipts == [('accepted', '')]
    assert not handles[0].can_steer
    terminal = events[-1]['result']
    assert terminal['status'] == 'SUCCESS' and terminal['response'] == 'Working with revised focus'
    assert terminal['usage'] == {'input_tokens': 30, 'output_tokens': 12, 'cache_read_tokens': 10}


def test_acp_permissions_authorize_only_one_call_to_selected_connector(tmp_path):
    script = tmp_path/'permissions.py'
    script.write_text('''import json,sys
assert '--process-per-session' in sys.argv
def emit(m):print(json.dumps(m),flush=True)
cases=[('call_mcp_tool','selected','echo',True),('call_mcp_tool','ambient','echo',False),
       ('write_file','selected','echo',False),('call_mcp_tool','selected','',False)]
def ask(index):
 name,server,tool,allowed=cases[index]
 emit({'id':'permission-'+str(index),'method':'session/request_permission','params':{
  'sessionId':'session','toolCall':{'name':name,'rawInput':{'ServerName':server,'ToolName':tool}},
  'options':[{'kind':'allow_always','optionId':'always'},{'kind':'allow_once','optionId':'once'}]}})
for line in sys.stdin:
 m=json.loads(line);method=m.get('method');identity=m.get('id')
 if method=='initialize':emit({'id':identity,'result':{'protocolVersion':1}})
 elif method=='session/new':
  assert m['params']['mcpServers']==[{'name':'selected','type':'http','url':'https://synthetic.invalid/mcp','headers':[{'name':'X-Test','value':'synthetic'}]}]
  emit({'id':identity,'result':{'sessionId':'session'}})
 elif method=='session/prompt':ask(0)
 elif str(identity).startswith('permission-'):
  index=int(identity.split('-')[1]);allowed=cases[index][3]
  assert m['result']['outcome']==({'outcome':'selected','optionId':'once'} if allowed else {'outcome':'cancelled'})
  if index+1<len(cases):ask(index+1)
  else:emit({'id':4,'result':{'stopReason':'end_turn'}})
''', encoding='utf-8')
    engine = SimpleNamespace(_launcher=lambda: [sys.executable, '-u', str(script)])
    events = []
    result = run(engine, tmp_path, 'project', [], False, '', 'Task',
        lambda raw: events.append(json.loads(raw)), 10, os.environ, None,
        servers=[{'name': 'selected', 'serverUrl': 'https://synthetic.invalid/mcp', 'headers': {'X-Test': 'synthetic'}}])
    assert not result.error, result.error
    assert events[-1]['result']['status'] == 'SUCCESS'
