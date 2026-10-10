"""Opt-in real CLI MCP test with synthetic shared documents, never owner service data.

Temporarily registers uniquely named loopback MCP servers in the three installed CLIs.
Only those registrations are removed in finally. Provider sign-in is reused, never copied.
"""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
import threading
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run(output):
    from armada import runner, util
    from armada.engine import claude, codex, gemini
    from armada.engine.contracts import RunRequest
    ident = 'armada_probe_' + uuid.uuid4().hex[:12]
    root = Path(output).resolve().parent / ident
    root.mkdir(parents=True)
    records, calls = {}, []
    models = {'claude': 'claude-opus-5-5', 'codex': 'gpt-6-astra', 'gemini': 'gemini-3.8-flash-low'}
    engines = {'claude': claude.ClaudeEngine(), 'codex': codex.CodexEngine(), 'gemini': gemini.GeminiEngine()}
    names = {p: ident + '_' + p for p in engines}
    schemas = [
        {'name': 'write_document', 'description': 'Create or replace the synthetic acceptance-test document.',
         'inputSchema': {'type': 'object', 'properties': {'text': {'type': 'string'}}, 'required': ['text'], 'additionalProperties': False}},
        {'name': 'read_document', 'description': 'Read the synthetic shared acceptance-test document.',
         'inputSchema': {'type': 'object', 'properties': {}, 'additionalProperties': False}},
    ]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            self.send_response(405); self.end_headers()
        def do_DELETE(self):
            self.send_response(200); self.end_headers()
        def do_POST(self):
            if self.path.strip('/') not in engines:
                self.send_error(404); return
            req = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
            method = req.get('method')
            if 'id' not in req:
                self.send_response(202); self.end_headers(); return
            if method == 'initialize':
                result = {'protocolVersion': req['params']['protocolVersion'], 'capabilities': {'tools': {}},
                          'serverInfo': {'name': 'synthetic-connector-probe', 'version': '1.0'}}
            elif method == 'tools/list':
                result = {'tools': schemas}
            elif method == 'tools/call':
                tool = req['params']['name']; args = req['params'].get('arguments', {})
                if tool == 'write_document': records['text'] = args['text']
                elif tool != 'read_document': raise ValueError('Unexpected probe tool')
                calls.append({'provider': self.path.strip('/'), 'tool': tool, 'text': records.get('text', '')})
                result = {'content': [{'type': 'text', 'text': records.get('text', '')}], 'isError': False}
            else:
                result = {}
            body = json.dumps({'jsonrpc': '2.0', 'id': req['id'], 'result': result}).encode()
            self.send_response(200); self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    result = {'ok': False, 'synthetic_only': True, 'providers': {}, 'calls': calls, 'cleanup': {}}
    registered = []

    def command(provider, args):
        engine = engines[provider]
        return subprocess.run(engine._launcher() + args, cwd=root, capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=60, creationflags=0x08000000,
            env=engine._env() if provider == 'claude' else None)

    try:
        bindings = {}
        for provider in engines:
            url = f'http://127.0.0.1:{server.server_port}/{provider}'
            prefix = ['--scope', 'local', '--transport', 'http'] if provider == 'claude' else ['--type', 'http'] if provider == 'gemini' else []
            args = ['mcp', 'add', *prefix, names[provider], *(['--url'] if provider == 'codex' else []), url]
            registered.append(provider)  # cleanup even if add times out after writing its config
            added = command(provider, args)
            if added.returncode:
                raise RuntimeError(f'{provider} probe registration failed (exit {added.returncode}).')
            # Loopback HTTP is intentionally not a shareable realm endpoint. Link the existing
            # registration by name, exactly like importing a provider-private configuration.
            bindings[provider] = {'server_name': names[provider], 'endpoint': ''}
        util.write_json_atomic(root/'realm.json', {'name': 'Synthetic connector acceptance', 'toolkit': {
            'connectors': [{'id': 'shared-documents', 'connection_type': 'provider-mcp', 'provider_bindings': bindings}]}})
        util.write_json_atomic(root/'agents/probe/agent.json', {'id': 'probe', 'allow_tools': True,
            'toolkit': {'connectors': [{'id': 'shared-documents'}]}})
        prompts = {
            'claude': 'Call write_document with text exactly "Created by Claude: synthetic 12.34". Then read_document. Finish.',
            'codex': 'First call read_document. Then call write_document with text exactly "Edited by Codex: synthetic 56.78". Finish.',
            'gemini': 'Call read_document once and report its text. Finish.',
        }
        for provider in engines:
            print('Testing ' + provider, flush=True)
            engine, _ = runner._prepare_agent_run(root, 'probe', engines[provider], True)
            start = len(calls)
            response = engine.execute(RunRequest(
                system='This is a synthetic connector acceptance test. Use only the MCP server ' + names[provider] +
                    '. Its tools are write_document(text: string) and read_document(). Call them directly. Do not use shell, web, files or other servers.',
                prompt=prompts[provider], model=models[provider], cwd=str(root), allow_tools=True, timeout=180))
            result['providers'][provider] = {'ok': response.ok, 'calls': calls[start:], 'error': response.error,
                                              'output': response.output[:1500]}
            Path(output).write_text(json.dumps(result, indent=2), encoding='utf-8')
        result['ok'] = (all(r['ok'] for r in result['providers'].values())
            and any(c['provider'] == 'claude' and c['tool'] == 'write_document' for c in calls)
            and any(c['provider'] == 'codex' and c['tool'] == 'read_document' and c['text'].startswith('Created by Claude') for c in calls)
            and any(c['provider'] == 'codex' and c['tool'] == 'write_document' for c in calls)
            and any(c['provider'] == 'gemini' and c['tool'] == 'read_document' and c['text'].startswith('Edited by Codex') for c in calls))
    except Exception as exc:
        result['error'] = str(exc)
    finally:
        for provider in registered:
            try:
                args = ['mcp', 'remove', *(['--scope', 'local'] if provider == 'claude' else []), names[provider]]
                result['cleanup'][provider] = command(provider, args).returncode == 0
            except Exception as exc:
                result['cleanup'][provider] = type(exc).__name__
        server.shutdown(); server.server_close()
        result['ok'] = result['ok'] and all(v is True for v in result['cleanup'].values())
        Path(output).write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result['ok']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    raise SystemExit(0 if run(args.output) else 1)
