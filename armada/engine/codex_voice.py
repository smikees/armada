"""Experimental Codex WebRTC signaling. Audio stays between the browser and Codex.

Schemas verified against installed codex-cli 0.157.1, with experimentalApi enabled.
This preview admits no tools, files, plugins, apps, web search or shell commands.
"""
from __future__ import annotations

import tempfile

from .codex import CodexEngine, _feature_args, model_id
from .process import supervise_rpc


class CodexVoice:
    def __init__(self):
        self.engine = CodexEngine()
        self.send = None
        self.thread_id = None

    def run(self, offer, instructions, history, model, emit, on_proc):
        launcher = self.engine._launcher()
        if not launcher:
            raise ValueError('Install and sign in to Codex in Settings → App before using voice.')
        with tempfile.TemporaryDirectory(prefix='armada-voice-') as folder:
            args = _feature_args() + self.engine._mcp_args(False, (), cwd=folder)
            for feature in ('shell_tool', 'unified_exec', 'image_generation', 'view_image', 'code_mode'):
                args += ['-c', f'features.{feature}=false']
            args += ['-c', 'web_search="disabled"', '-c', 'project_doc_max_bytes=0']

            def start(send):
                self.send = send
                send({'id': 1, 'method': 'initialize', 'params': {'clientInfo': {
                    'name': 'armada', 'title': 'ARMADA voice preview', 'version': '1'},
                    'capabilities': {'experimentalApi': True}}})

            def accept(message, send):
                # No server-initiated tool, approval or credential request is accepted.
                if 'id' in message and 'method' in message:
                    send({'id': message['id'], 'error': {'code': -32601,
                        'message': 'Tools and approvals are unavailable in ARMADA voice preview.'}})
                    return False
                if message.get('error'):
                    if message['error'].get('code') == -32601:
                        raise ValueError('This Codex CLI does not support voice preview. Update Codex and try again.')
                    raise ValueError(str(message['error'].get('message') or 'Codex rejected voice setup.'))
                if message.get('id') == 1:
                    send({'method': 'initialized', 'params': {}})
                    params = {'cwd': folder, 'approvalPolicy': 'never', 'sandbox': 'read-only',
                              'ephemeral': True, 'serviceName': 'armada',
                              'baseInstructions': instructions, 'developerInstructions': instructions}
                    if model_id(model):
                        params['model'] = model_id(model)
                    send({'id': 2, 'method': 'thread/start', 'params': params})
                elif message.get('id') == 2:
                    self.thread_id = message['result']['thread']['id']
                    send({'id': 3, 'method': 'thread/realtime/start', 'params': {
                        'threadId': self.thread_id, 'version': 'v3', 'outputModality': 'audio',
                        'clientManagedHandoffs': True, 'flushTranscriptTailOnSessionEnd': False,
                        'transport': {'type': 'webrtc', 'sdp': offer},
                        'includeStartupContext': False, 'initialItems': history,
                        'prompt': instructions, 'realtimeStartInstructions': instructions,
                        'realtimeEndInstructions': 'The owner ended voice. Do not start work or modify files.'}})
                elif message.get('method') == 'turn/started':
                    raise ValueError('Voice preview cannot start an action. End voice and use normal chat.')
                elif message.get('method', '').startswith('thread/realtime/'):
                    params = message.get('params') or {}
                    if params.get('threadId') != self.thread_id:
                        raise ValueError('Codex emitted voice data for another conversation.')
                    emit(message['method'], params)
                    return message['method'] == 'thread/realtime/closed'
                return False

            return supervise_rpc(launcher + ['app-server'] + args, start=start, on_message=accept,
                                 on_proc=on_proc, timeout=600, cwd=folder)

    def stop(self):
        if self.send and self.thread_id:
            self.send({'id': 4, 'method': 'thread/realtime/stop', 'params': {'threadId': self.thread_id}})
