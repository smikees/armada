"""Native Claude streaming input, with receipts tied to answered message UUIDs."""
import threading
import uuid


class ClaudeSteering:
    def __init__(self):
        self.lock = threading.RLock()
        self.requests = {}
        self.enabled = False
        self.closed = False

    @property
    def ready(self):
        with self.lock:
            return self.enabled and not self.closed

    @property
    def waiting(self):
        with self.lock:
            return any(not row['answered'] for row in self.requests.values())

    def submit(self, identity, text, callback):
        with self.lock:
            if identity in self.requests:
                return
            if not self.ready:
                raise ValueError('This run cannot accept messages now. Your message was not sent.')
            if len(self.requests) >= 64:
                raise ValueError('This run has reached its message limit. Wait for it to finish.')
            if any(row['status'] in ('queued', 'sent') for row in self.requests.values()):
                raise ValueError('Another message is awaiting confirmation. Try again shortly.')
            self.requests[identity] = {'uuid': str(uuid.uuid4()), 'text': text, 'callback': callback,
                                       'status': 'queued', 'answered': False}

    def drain(self, send):
        messages = []
        with self.lock:
            for row in self.requests.values():
                if row['status'] == 'queued':
                    row['status'] = 'sent'
                    messages.append({'type': 'user', 'uuid': row['uuid'], 'session_id': '',
                        'message': {'role': 'user', 'content': row['text']}, 'parent_tool_use_id': None,
                        'priority': 'now', 'origin': {'kind': 'human'}})
        # As with Codex, the bounded RPC writer owns the pipe. No HTTP thread
        # writes to stdin or holds the control lock during a blocked write.
        for message in messages:
            send(message)

    def observe(self, message):
        kind = message.get('type')
        # Replays acknowledge transport only; they can precede a blocking hook.
        # Confirm incorporation only on a model reply/result that names this UUID.
        if kind not in ('assistant', 'stream_event', 'result'):
            return
        if kind == 'assistant' and (message.get('message') or {}).get('role') == 'user':
            return
        ids = message.get('user_message_uuids') or [message.get('user_message_uuid')]
        if not isinstance(ids, list):
            return
        with self.lock:
            for row in self.requests.values():
                if row['status'] == 'queued' or row['answered'] or row['uuid'] not in ids:
                    continue
                if row['status'] == 'sent':
                    rejected = kind == 'result' and message.get('num_turns') == 0
                    row['status'] = 'rejected' if rejected else 'accepted'
                    row['callback'](row['status'], 'Claude did not run this message.' if rejected else '')
                if kind == 'result':
                    row['answered'] = True

    def close(self):
        with self.lock:
            self.closed = True
            for row in self.requests.values():
                row['answered'] = True
                if row['status'] in ('queued', 'sent'):
                    status = 'rejected' if row['status'] == 'queued' else 'uncertain'
                    row['status'] = status
                    row['callback'](status, 'The run ended before confirming this message. Check its response before sending again.')
