"""Experimental Codex WebRTC signaling. Audio stays between the browser and Codex.

Schemas verified against installed codex-cli 0.157.1, with experimentalApi enabled.
This preview admits no tools, files, plugins, apps, web search or shell commands.
"""
from __future__ import annotations

import tempfile
import threading

from .codex import CodexEngine, _feature_args, model_id
from .process import supervise_rpc


class CodexVoice:
    def __init__(self, *, mode='voice'):
        self.engine = CodexEngine()
        self.mode = mode
        self.send = None
        self.thread_id = None
        self._send_lock = threading.Lock()
        self._request_id = 10

    def run(self, offer, instructions, history, model, emit, on_proc):
        launcher = self.engine._launcher()
        if not launcher:
            raise ValueError('Install and sign in to Codex in Settings → App before using voice.')
        with tempfile.TemporaryDirectory(prefix='armada-voice-') as folder:
            args = _feature_args() + self.engine._mcp_args(False, (), cwd=folder)
            for feature in ('shell_tool', 'unified_exec', 'image_generation', 'view_image', 'code_mode'):
                args += ['-c', f'features.{feature}=false']
            args += ['-c', 'web_search="disabled"', '-c', 'project_doc_max_bytes=0', '-c', 'notify=[]']
            backend = instructions

            def start(send):
                def locked_send(message):
                    with self._send_lock:
                        send(message)
                self.send = locked_send
                send({'id': 1, 'method': 'initialize', 'params': {'clientInfo': {
                    'name': 'armada', 'title': 'ARMADA voice preview', 'version': '1'},
                    'capabilities': {'experimentalApi': True}}})

            def accept(message, send):
                send = self.send
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
                              'baseInstructions': backend, 'developerInstructions': backend}
                    if model_id(model):
                        params['model'] = model_id(model)
                    send({'id': 2, 'method': 'thread/start', 'params': params})
                elif message.get('id') == 2:
                    self.thread_id = message['result']['thread']['id']
                    send({'id': 3, 'method': 'thread/realtime/start', 'params': {
                        'threadId': self.thread_id, 'version': 'v3', 'outputModality': 'audio',
                        # ARMADA's ordinary runner supplies real replies via appendSpeech.
                        'clientManagedHandoffs': True, 'delegationAckFiller': False,
                        'flushTranscriptTailOnSessionEnd': False,
                        'transport': {'type': 'webrtc', 'sdp': offer},
                        'includeStartupContext': False, 'initialItems': history,
                        'prompt': instructions, 'realtimeStartInstructions': backend,
                        'realtimeEndInstructions': 'The owner ended voice. Do not start work or modify files.'}})
                elif message.get('method') in ('turn/started', 'turn/completed', 'item/started'):
                    params = message.get('params') or {}
                    if params.get('threadId') != self.thread_id:
                        raise ValueError('Codex emitted voice data for another conversation.')
                    if message['method'] == 'item/started':
                        kind = (params.get('item') or {}).get('type')
                        if kind not in ('userMessage', 'agentMessage', 'reasoning', 'plan', 'contextCompaction'):
                            raise ValueError('A tool was requested in conversation-only voice. Use normal chat for actions.')
                    else:
                        emit(message['method'], params)
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

    def speak(self, text):
        if not self.send or not self.thread_id or not text.strip():
            return
        self._request_id += 1
        self.send({'id': self._request_id, 'method': 'thread/realtime/appendSpeech',
                   'params': {'threadId': self.thread_id, 'text': text}})
