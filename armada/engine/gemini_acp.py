"""Native Antigravity ACP prompts/steering inside one scoped owner run."""
import json
from .codex_steering import SteeringControl, SteeringProcess
from .process import supervise_rpc


class GeminiSteering(SteeringControl):
    def drain(self, send):
        messages = []
        with self.lock:
            for identity, row in self.requests.items():
                if row['status'] == 'queued':
                    row['status'] = 'sent'
                    messages.append({'jsonrpc': '2.0', 'id': 'armada-steer-'+identity,
                        'method': 'session/prompt', 'params': {'sessionId': self.thread_id,
                            'prompt': [{'type': 'text', 'text': row['text']}]}})
        for message in messages:
            send(message)

    @property
    def waiting(self):
        with self.lock:
            return any(row['status'] in ('queued', 'sent') for row in self.requests.values())

    def accept(self, message):
        identity = message.get('id')
        if not isinstance(identity, str) or not identity.startswith('armada-steer-') or 'method' in message:
            return False
        with self.lock:
            row = self.requests.get(identity.removeprefix('armada-steer-'))
            if row and row['status'] == 'sent':
                error = message.get('error')
                reason = (message.get('result') or {}).get('stopReason')
                if error:
                    self._finish(row, 'rejected', str(error.get('message', error))[:1000])
                elif reason == 'end_turn':
                    self._finish(row, 'accepted')
                else:
                    self._finish(row, 'uncertain', 'Gemini did not confirm this message: '+str(reason))
            return True


def run(engine, folder, project, roots, file_access, actual, prompt, line, timeout, env, on_proc, servers=()):
    control = GeminiSteering()
    session, completed, stop_reason = '', False, ''
    usage, chunks, tools = {}, [], {}
    def rpc(send, identity, method, params):
        send({'jsonrpc': '2.0', 'id': identity, 'method': method, 'params': params})
    def emit(event):
        line(json.dumps(event, ensure_ascii=False))
    def start(send):
        rpc(send, 1, 'initialize', {'protocolVersion': 1, 'clientInfo': {'name': 'armada'},
            'clientCapabilities': {'fs': {'readTextFile': False, 'writeTextFile': False}, 'terminal': False}})
    def begin(send):
        control.activate(session, 'owner-turn')
        emit({'event': 'init'})
        rpc(send, 4, 'session/prompt', {'sessionId': session, 'prompt': [{'type': 'text', 'text': prompt}]})
    def receive(message, send):
        nonlocal session, completed, stop_reason, usage
        method, identity = message.get('method'), message.get('id')
        params = message.get('params') or {}
        if params.get('sessionId') and params['sessionId'] != session:
            raise ValueError('Gemini returned an update for a different session.')
        if method and identity is not None:
            # ACP ignores project grants for MCP. Authorize one call only to an
            # explicitly selected server; per-tool filters retain print mode.
            # Native writes and host filesystem/terminal RPCs are never approved.
            if method == 'session/request_permission':
                tool = params.get('toolCall') or {}
                data = tool.get('rawInput') or {}
                approved = (control.ready and tool.get('name') == 'call_mcp_tool' and
                    isinstance(data, dict) and bool(data.get('ToolName')) and
                    data.get('ServerName') in {s['name'] for s in servers})
                option = next((o.get('optionId') for o in params.get('options', [])
                               if o.get('kind') == 'allow_once'), None) if approved else None
                outcome = {'outcome': 'selected', 'optionId': option} if option else {'outcome': 'cancelled'}
                send({'jsonrpc': '2.0', 'id': identity, 'result': {'outcome': outcome}})
            else:
                send({'jsonrpc': '2.0', 'id': identity, 'error': {'code': -32601, 'message': 'Host capability unavailable.'}})
            return False
        if message.get('error') and identity in (1, 2, 3, 4):
            raise ValueError(str(message['error'].get('message', 'Gemini ACP request failed.')))
        result = message.get('result') or {}
        if identity == 1:
            if result.get('protocolVersion') != 1:
                raise ValueError('Unsupported Gemini ACP protocol version.')
            configured = []
            for spec in servers:
                url = spec.get('url') or spec.get('serverUrl')
                if url:
                    configured.append({'name': spec['name'], 'type': spec.get('type', 'http'), 'url': url,
                        'headers': [{'name': k, 'value': v} for k, v in spec.get('headers', {}).items()]})
                else:
                    configured.append({'name': spec['name'], 'command': spec['command'], 'args': spec.get('args', []),
                        'env': [{'name': k, 'value': v} for k, v in spec.get('env', {}).items()]})
            rpc(send, 2, 'session/new', {'cwd': str(folder), 'mcpServers': configured})
        elif identity == 2:
            session = result.get('sessionId')
            if not isinstance(session, str) or not session:
                raise ValueError('Gemini did not create a valid session.')
            if actual:
                rpc(send, 3, 'session/set_model', {'sessionId': session, 'modelId': actual})
            else:
                begin(send)
        elif identity == 3:
            begin(send)
        elif identity == 4:
            completed, stop_reason = True, result.get('stopReason', '')
        if result.get('usage'):
            usage = result['usage']
        if method == 'session/update':
            update = params.get('update') or {}
            kind, content = update.get('sessionUpdate'), update.get('content') or {}
            if kind == 'agent_message_chunk' and content.get('type') == 'text':
                text = content.get('text', '')
                chunks.append(text)
                emit({'event': 'step_update', 'step_update': {'step_type': 'agent_response', 'text_delta': text}})
            elif kind in ('tool_call', 'tool_call_update'):
                key = str(update.get('toolCallId', ''))
                tool = tools.setdefault(key, {})
                tool.update(update)
                data = tool.get('rawInput') or {}
                if not isinstance(data, dict):
                    data = {'input': data}
                name = tool.get('name') or (tool.get('_meta') or {}).get('toolName') or tool.get('title') or 'tool'
                name = {'read_file': 'view_file', 'write_file': 'write_to_file'}.get(name, name)
                info = {'name': name, 'parameters': data}
                if 'rawOutput' in tool or 'content' in tool:
                    info['output'] = tool.get('rawOutput', tool.get('content'))
                else:
                    info['acp_result_unavailable'] = True
                failed = tool.get('status') in ('failed', 'cancelled')
                if failed:
                    info['error'] = info.get('output') or tool['status']
                emit({'event': 'step_update', 'step_update': {'step_type': 'tool', 'step_index': key,
                    'state': 'ERROR' if failed else 'DONE' if tool.get('status') == 'completed' else 'ACTIVE', 'tool_info': info}})
        control.accept(message)
        return completed and not control.waiting
    args = engine._launcher()+['--project', project, 'acp', '--agent', 'armada-turn', '--include-default-customizations=false']
    if any(spec.get('url') or spec.get('serverUrl') for spec in servers):
        args += ['--process-per-session']
    if file_access:
        for root in roots:
            args += ['--add-dir', str(root)]
    try:
        result = supervise_rpc(args, start=start, on_message=receive, timeout=timeout, cwd=str(folder), env=env,
            on_proc=lambda p: on_proc(SteeringProcess(p, control)) if on_proc else None, on_tick=control.drain)
        stats = {'input_tokens': usage.get('inputTokens'), 'output_tokens': usage.get('outputTokens'),
                 'cache_read_tokens': usage.get('cachedReadTokens', 0)}
        emit({'event': 'result', 'result': {'status': 'SUCCESS' if stop_reason == 'end_turn' and not result.error else 'ERROR',
            'error': result.error or ('Gemini ended with status '+stop_reason if stop_reason != 'end_turn' else ''),
            'response': ''.join(chunks), 'usage': stats, 'acp_usage': usage}})
        return result
    finally:
        control.close()
