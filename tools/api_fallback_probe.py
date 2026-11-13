"""Installed Claude CLI through critical-job fallback and a synthetic local provider.

No real credential, provider request, business tool or Windows account is used.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import urllib.request
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run(output):
    output = output.resolve()
    from armada.engine.claude import ClaudeEngine
    # Resolve the installed binary before isolating its profile. No owner sign-in
    # files are used by the CLI started below.
    launcher = ClaudeEngine()._launcher()
    if not launcher:
        raise RuntimeError('Install Claude Code before running this protocol probe.')
    with tempfile.TemporaryDirectory(prefix='armada-api-fallback-probe-') as directory:
        home = Path(directory)
        for name in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'CODEX_HOME', 'XDG_CONFIG_HOME'):
            os.environ[name] = str(home/name)
            Path(os.environ[name]).mkdir()
        for name in ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'CLAUDE_CODE_OAUTH_TOKEN',
                     'CLAUDE_CONFIG_DIR', 'ANTHROPIC_BASE_URL', 'OPENAI_API_KEY', 'GEMINI_API_KEY',
                     'CLAUDE_CODE_USE_BEDROCK', 'CLAUDE_CODE_USE_VERTEX', 'CLAUDE_CODE_USE_FOUNDRY'):
            os.environ.pop(name, None)
        os.environ.update(ARMADA_DATA_DIR=str(home/'account'), ARMADA_NO_EXTERNAL_NOTIFY='1',
                          ARMADA_NO_MODEL_SYNC='1', CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1',
                          DISABLE_TELEMETRY='1', DISABLE_ERROR_REPORTING='1')
        from armada import api_fallback, api_gateway, billing, instance, run_policy, util, worker
        from armada.engine.claude import ClaudeEngine
        from armada.engine.base import RunResult
        from armada.engine.contracts import RunRequest, execute_request
        root = home/'realm'
        util.write_json_atomic(root/'realm.json', {'name': 'Synthetic API fallback', 'provider': 'claude'})
        util.write_json_atomic(root/'agents/a/agent.json', {'id': 'a', 'model': 'claude-haiku-4-5'})
        job = {'id': 'critical', 'kind': 'agent', 'prompt': 'Return the synthetic marker.', 'critical': True, 'allow_tools': False}
        util.write_json_atomic(root/'agents/a/jobs/critical.json', job)
        run_policy.seal_job(root, 'a', job)
        sentinel = 'sk-ant-synthetic-critical-job-probe'
        api_fallback.save('claude', enabled=True, api_key=sentinel)
        marker = 'ARMADA_API_FALLBACK_PROBE_OK'
        requests = []
        provider_closed = threading.Event()
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):pass
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append({'path': self.path, 'model': body.get('model')})
                if provider_closed.is_set():
                    raw = json.dumps({'type': 'error', 'error': {'type': 'invalid_request_error',
                        'message': 'You have reached your specified workspace API usage limits'}}).encode()
                    self.send_response(400);self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(raw)));self.end_headers();self.wfile.write(raw)
                    return
                content = [{'type': 'text', 'text': marker}]
                message = {'id': 'msg_armada_fallback', 'type': 'message', 'role': 'assistant',
                    'model': body.get('model') or 'claude-haiku-4-5', 'content': content,
                    'stop_reason': 'end_turn', 'stop_sequence': None,
                    'usage': {'input_tokens': 100, 'output_tokens': 20}}
                if self.path.startswith('/v1/messages/count_tokens'):
                    raw = json.dumps({'input_tokens': 100}).encode();kind = 'application/json'
                elif body.get('stream'):
                    events = [
                        ('message_start', {'type': 'message_start', 'message': {**message, 'content': [], 'stop_reason': None}}),
                        ('content_block_start', {'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'text', 'text': ''}}),
                        ('content_block_delta', {'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': marker}}),
                        ('content_block_stop', {'type': 'content_block_stop', 'index': 0}),
                        ('message_delta', {'type': 'message_delta', 'delta': {'stop_reason': 'end_turn', 'stop_sequence': None}, 'usage': {'output_tokens': 20}}),
                        ('message_stop', {'type': 'message_stop'})]
                    raw = ''.join('event: '+name+'\ndata: '+json.dumps(value)+'\n\n' for name, value in events).encode()
                    kind = 'text/event-stream'
                else:
                    raw = json.dumps(message).encode();kind = 'application/json'
                self.send_response(200);self.send_header('Content-Type', kind)
                self.send_header('Content-Length', str(len(raw)));self.end_headers();self.wfile.write(raw)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        original_gateway = api_gateway.Gateway
        class SyntheticGateway(original_gateway):
            def _open(self, path, body, headers):
                assert self._key == sentinel and self.budget is None
                return urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{server.server_port}'+path,
                    data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'}), timeout=15)
        calls = []
        keys_hidden = []
        engine = ClaudeEngine()
        engine._cached = launcher
        request = RunRequest('This is an isolated protocol probe. Return the marker supplied by the synthetic provider.',
            'Return the synthetic marker.', model='claude-haiku-4-5', cwd=str(root/'agents/a'), timeout=60,
            allow_tools=False, only_tools=[])
        def invoke(selected, incoming, **callbacks):
            calls.append(bool(incoming.env))
            if len(calls) == 1:
                return RunResult(ok=False, error="You've hit your weekly limit · resets 11:59pm (Europe/Madrid)",
                                 raw={'api_error_status': 429})
            keys_hidden.append(sentinel not in incoming.env.values())
            return execute_request(selected, incoming, **callbacks)
        try:
            with patch.object(instance, '_account_directory', lambda: home/'account'), patch.object(api_gateway, 'Gateway', SyntheticGateway):
                result = billing.execute(engine, request, root=root, agent='a', job=job,
                    run_id='synthetic-fallback', on_event=lambda event: None, on_proc=lambda proc: None, invoke=invoke)
                successful_requests = len(requests)
                provider_closed.set()
                stopped = billing.execute(engine, request, root=root, agent='a', job=job,
                    run_id='synthetic-cap-refusal', on_event=lambda event: None, on_proc=lambda proc: None,
                    invoke=lambda selected, incoming, **callbacks: execute_request(selected, incoming, **callbacks))
            cap_stopped = (not stopped.ok and stopped.raw.get('billing', {}).get('final_failure')
                           and len(requests)-successful_requests == 1 and 'spending limit reached' in stopped.error)
            report = {'ok': result.ok and marker in result.output and calls == [False, True] and all(keys_hidden) and bool(cap_stopped),
                      'provider': 'claude', 'lane': result.raw.get('billing', {}).get('lane'),
                      'budget_managed': result.raw.get('billing', {}).get('budget_managed'),
                      'reported_cost_usd': result.raw.get('billing', {}).get('real_cost_usd'),
                      'engine_invocations': len(calls), 'local_provider_requests': requests,
                      'console_cap_refusal_stopped_without_retry': bool(cap_stopped),
                      'real_key_in_cli_environment': not all(keys_hidden), 'worker_required': worker.enabled(),
                      'paid_requests': 0, 'error': result.error, 'cap_error': stopped.error}
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps(report, indent=2))
            return 0 if report['ok'] and report['lane'] == 'api' and not report['worker_required'] else 1
        finally:
            server.shutdown();server.server_close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    raise SystemExit(run(parser.parse_args().output))
