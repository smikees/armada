"""Opt-in real Codex metadata check: scoped ephemeral thread, no model/service calls."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from armada import codex_apps
from armada.engine.codex import CodexEngine, _feature_args
from armada.engine.process import supervise_rpc


def probe():
    installed = codex_apps.inventory()
    allowed = {next(r['id'] for r in installed if r['callable'])}
    result = {}
    with tempfile.TemporaryDirectory(prefix='native-app-scope-', dir=Path(__file__).resolve().parents[1]/'build') as cwd:
        args = _feature_args() + codex_apps.scoped_args(allowed, cwd=cwd)
        def start(send):
            send({'id':1, 'method':'initialize', 'params':{'clientInfo':{'name':'armada-probe','version':'1.0'},
                'capabilities':{'experimentalApi':True}}})
        def accept(message, send):
            if message.get('error'):
                raise ValueError('Native app scope metadata request failed.')
            if message.get('id') == 1:
                send({'method':'initialized','params':{}})
                send({'id':2,'method':'thread/start','params':{'cwd':cwd,'ephemeral':True,
                    'approvalPolicy':'never','sandbox':'read-only'}})
            elif message.get('id') == 2:
                send({'id':3,'method':'app/installed','params':{'threadId':message['result']['thread']['id'],
                    'forceRefresh':True}})
            elif message.get('id') == 3:
                codex_apps.verify_snapshot(message['result'],allowed)
                result.update(ok=True, granted=sorted(allowed), callable=[r['id'] for r in message['result']['apps'] if r['callable']],
                    model_turn_started=False, service_content_read=False, persisted_configuration_changed=False)
                return True
            return False
        outcome = supervise_rpc(CodexEngine()._launcher()+['app-server']+args, start=start,
            on_message=accept, timeout=60, cwd=cwd)
        if not result:
            raise ValueError(outcome.error or 'Native scope check did not complete.')
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    options=parser.parse_args()
    result=probe()
    options.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
