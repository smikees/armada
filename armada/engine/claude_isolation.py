"""Exercise installed Claude child-environment isolation without a real key or paid call."""
from .. import worker as worker_account
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import urllib.request
import shlex

def probe(engine, output=None):
    requests = []
    sentinel = 'sk-ant-armada-synthetic-environment-probe'
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append(body)
            if self.path.startswith('/v1/messages/count_tokens'):
                raw = json.dumps({'input_tokens':100}).encode()
                self.send_response(200)
                self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            tool_results = [b for m in body.get('messages', []) for b in m.get('content', [])
                            if isinstance(b, dict) and b.get('type') == 'tool_result']
            python = Path(sys.executable).with_name('python.exe') if sys.platform == 'win32' else Path(sys.executable)
            script = "import os; print('KEY_PRESENT='+str(bool(os.environ.get('ANTHROPIC_API_KEY')))); print('AUTH_PRESENT='+str(bool(os.environ.get('ANTHROPIC_AUTH_TOKEN'))))"
            native_worker = worker_account.enabled()
            command = ("& '"+str(python).replace("'","''")+"' -c '"+script.replace("'","''")+"'" if native_worker else
                       shlex.quote(str(python).replace('\\','/'))+' -c '+shlex.quote(script))
            content = ([{'type': 'text', 'text': 'Environment probe completed.'}] if tool_results else
                       [{'type': 'tool_use', 'id': 'toolu_armada_probe', 'name': 'PowerShell' if native_worker else 'Bash', 'input': {'command': command}}])
            response = {'id': 'msg_armada_probe', 'type': 'message', 'role': 'assistant',
                        'model': 'claude-haiku-4-5-20251001', 'content': content,
                        'stop_reason': 'end_turn' if tool_results else 'tool_use', 'stop_sequence': None,
                        'usage': {'input_tokens': 100, 'output_tokens': 30}}
            # SDK requests streams: return valid message SSE, including tool argument deltas.
            if body.get('stream'):
                events = [('message_start', {'type':'message_start','message':{**response,'content':[], 'stop_reason':None}})]
                for i, block in enumerate(content):
                    initial = {**block, 'input':{}} if block['type']=='tool_use' else {**block,'text':''}
                    events.append(('content_block_start', {'type':'content_block_start','index':i,'content_block':initial}))
                    delta = ({'type':'input_json_delta','partial_json':json.dumps(block['input'])} if block['type']=='tool_use' else
                             {'type':'text_delta','text':block['text']})
                    events.append(('content_block_delta', {'type':'content_block_delta','index':i,'delta':delta}))
                    events.append(('content_block_stop', {'type':'content_block_stop','index':i}))
                events += [('message_delta', {'type':'message_delta','delta':{'stop_reason':response['stop_reason'],'stop_sequence':None},'usage':{'output_tokens':30}}),
                           ('message_stop', {'type':'message_stop'})]
                raw = ''.join('event: '+name+'\ndata: '+json.dumps(value)+'\n\n' for name,value in events).encode()
                kind = 'text/event-stream'
            else:
                raw, kind = json.dumps(response).encode(), 'application/json'
            self.send_response(200)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with worker_account.temporary_directory(prefix='armada-lane-probe-') as directory:
            config=Path(directory)/'mcp.json'
            config.write_text('{"mcpServers":{}}',encoding='utf-8')
            system=Path(directory)/'system.md'
            system.write_text('Synthetic system instructions for credential isolation.\n'*500,encoding='utf-8')
            env = {**engine._env(), 'ANTHROPIC_API_KEY':sentinel,
                   'CLAUDE_CONFIG_DIR':directory,
                   'ANTHROPIC_BASE_URL':f'http://127.0.0.1:{server.server_port}',
                   'NO_PROXY':'127.0.0.1,localhost', 'no_proxy':'127.0.0.1,localhost',
                   'CLAUDE_CODE_SUBPROCESS_ENV_SCRUB':'1', 'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC':'1'}
            for variable in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy'):
                env.pop(variable, None)
            shell = 'PowerShell' if worker_account.enabled() else 'Bash'
            command = engine._launcher()+['-p','Run the environment probe.','--output-format','stream-json','--verbose',
                '--model','claude-haiku-4-5-20251001','--tools',shell,'--allowedTools',shell,
                '--permission-prompts','none','--setting-sources','','--strict-mcp-config',
                '--mcp-config',str(config),'--system-prompt-file',str(system),'--no-session-persistence','--max-budget-usd','1',
                '--debug-file',str(Path(directory)/'probe-debug.log')]
            from ..api_gateway import Gateway
            with Gateway(sentinel,5) as gateway:
                def fake_upstream(path, body, headers):
                    return urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{server.server_port}'+path,
                        data=json.dumps(body).encode(),headers={'Content-Type':'application/json'}),timeout=10)
                gateway._open = fake_upstream
                env.update(gateway.env)
                assert sentinel not in env.values()
                try:
                    process = worker_account.run(command, input='', env=env, cwd=directory, capture_output=True, text=True,
                                             encoding='utf-8', errors='replace', timeout=45)
                except subprocess.TimeoutExpired as exc:
                    output = exc.stdout or b''
                    error = exc.stderr or b''
                    if isinstance(output, bytes):
                        output = output.decode('utf-8', 'replace')
                    if isinstance(error, bytes):
                        error = error.decode('utf-8', 'replace')
                    process = subprocess.CompletedProcess(command, -1, output, error+'\nProbe timed out.')
                authorised_requests = gateway.budget.charges
            events = []
            for line in process.stdout.splitlines():
                try:
                    events.append(json.loads(line))
                except ValueError:
                    pass
            results = [b for r in requests for m in r.get('messages', []) for b in m.get('content', [])
                       if isinstance(b, dict) and b.get('type') == 'tool_result']
            evidence = json.dumps(results)
            passed = bool(results) and 'KEY_PRESENT=False' in evidence and 'AUTH_PRESENT=False' in evidence and sentinel not in evidence
            report = {'passed': passed, 'returncode':process.returncode, 'requests':len(requests),
                      'budgeted_requests':authorised_requests, 'real_key_in_cli_environment':False,
                      'child_environment_scrubbed':passed,
                      'tools':[e.get('tools') for e in events if e.get('type') == 'system'],
                      'result': [e.get('result') for e in events if e.get('type') == 'result'],
                      'diagnostics':[{k:v for k,v in e.items() if k not in ('tools','mcp_servers')} for e in events if e.get('type') == 'system' and e.get('subtype') != 'init'],
                      'stderr':process.stderr[-1500:]}
            debug = Path(directory)/'probe-debug.log'
            if debug.exists():
                report['network_diagnostics'] = [line[-1200:] for line in worker_account.read_text(debug,encoding='utf-8',errors='replace').splitlines()
                                                 if any(k in line.lower() for k in ('connect','error','fetch','request failed'))][-18:]
            report['version'] = worker_account.run(engine._launcher()+['--version'],env=engine._env(),capture_output=True,
                                               text=True,timeout=10).stdout.strip()
            report['system_prompt_read']='Synthetic system instructions for credential isolation.' in json.dumps(requests)
            report['runtime_inputs_readable']=not any('path could not be vetted' in line or 'EPERM' in line
                                                     for line in report.get('network_diagnostics',[]))
            report['passed']=report['passed'] and report['runtime_inputs_readable'] and report['system_prompt_read']
            if output:
                Path(output).write_text(json.dumps(report, indent=2), encoding='utf-8')
            return report
    finally:
        server.shutdown()
        server.server_close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    from .claude import ClaudeEngine
    report = probe(ClaudeEngine(), args.output)
    print(json.dumps({k:v for k,v in report.items() if k != 'network_diagnostics'},indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
