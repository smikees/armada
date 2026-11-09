"""Bounded mid-turn input for Codex app-server; the RPC owner alone writes stdin."""
from collections import OrderedDict
import logging
import threading

log = logging.getLogger(__name__)


class SteeringControl:
    def __init__(self):
        self.lock = threading.RLock()
        self.thread_id = self.turn_id = ''
        self.closed = False
        self.requests = OrderedDict()

    @property
    def ready(self):
        with self.lock:
            return bool(self.thread_id and self.turn_id and not self.closed)

    def activate(self, thread_id, turn_id):
        with self.lock:
            if not self.closed and isinstance(turn_id, str) and turn_id:
                self.thread_id, self.turn_id = thread_id, turn_id

    def submit(self, identity, text, callback):
        with self.lock:
            if identity in self.requests:
                return
            if not self.ready:
                raise ValueError('This run cannot accept steering now. Your message was not sent.')
            if len(self.requests) >= 64:
                raise ValueError('This run has reached its steering-message limit. Wait for it to finish.')
            if any(r['status'] in ('queued', 'sent') for r in self.requests.values()):
                raise ValueError('Another steering message is awaiting confirmation. Try again shortly.')
            self.requests[identity] = {'text': text, 'callback': callback, 'status': 'queued', 'turn': self.turn_id}

    def _finish(self, row, status, error=''):
        row['status'] = status
        # Persistence failure must remain visible; never acknowledge delivery without its record.
        try:
            row['callback'](status, error)
        except Exception:
            log.exception('Could not persist steering delivery outcome')
            raise

    def drain(self, send):
        messages = []
        with self.lock:
            for identity, row in self.requests.items():
                if row['status'] != 'queued':
                    continue
                if not self.ready or row['turn'] != self.turn_id:
                    self._finish(row, 'rejected', 'The active turn ended before this message was sent.')
                    continue
                row['status'] = 'sent'
                messages.append({'id': 'armada-steer-' + identity, 'method': 'turn/steer', 'params': {
                    'threadId': self.thread_id, 'expectedTurnId': row['turn'],
                    'input': [{'type': 'text', 'text': row['text']}]}})
        # Never hold the control lock across a pipe write: a stalled provider
        # must not block HTTP admission and thereby prevent Stop taking RUNS_LOCK.
        for message in messages:
            send(message)

    def accept(self, message):
        identity = message.get('id')
        if not isinstance(identity, str) or not identity.startswith('armada-steer-') or 'method' in message:
            return False
        with self.lock:
            row = self.requests.get(identity.removeprefix('armada-steer-'))
            if row is None or row['status'] != 'sent':
                return True
            error = message.get('error')
            if error:
                reason = str(error.get('message', 'The engine rejected steering.')) if isinstance(error, dict) else str(error)
                self._finish(row, 'rejected', reason[:1000])
                if isinstance(error, dict) and error.get('code') == -32601:
                    self.closed = True
            elif isinstance(message.get('result'), dict) and message['result'].get('turnId') == row['turn']:
                self._finish(row, 'accepted')
            else:
                self._finish(row, 'uncertain', 'The engine did not confirm delivery to the expected turn.')
            return True

    def close(self):
        with self.lock:
            self.closed = True
            for row in self.requests.values():
                if row['status'] == 'queued':
                    self._finish(row, 'rejected', 'The run ended before this message was sent.')
                elif row['status'] == 'sent':
                    self._finish(row, 'uncertain', 'The run ended without confirming steering delivery. Check its response before sending again.')


class SteeringProcess:
    """Expose steering only for this particular app-server process and active turn."""
    def __init__(self, process, control):
        self.process, self.control = process, control

    @property
    def pid(self):
        return self.process.pid

    @property
    def can_steer(self):
        return self.control.ready and self.process.poll() is None

    def poll(self):
        return self.process.poll()

    def kill(self):
        self.process.kill()
        self.control.close()

    def steer(self, identity, text, callback):
        # Admission is synchronous and may raise only before enqueue. Delivery and
        # its callback run later on the RPC owner, never on the HTTP request thread.
        self.control.submit(identity, text, callback)
