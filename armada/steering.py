"""Owner steering admission and durable receipts, scoped to one exact running chat."""
import datetime
import logging
from pathlib import Path
import re

from . import util
from .threads import Thread

MAX_TEXT = 32000


def receipts(messages):
    return [dict(item) for message in messages for item in message.get('steering', [])
            if isinstance(item, dict)]


def resolve(thread, turn, identity, status, error=''):
    def change(record):
        item = next((r for r in record.get('steering', []) if r['id'] == identity), None)
        if item is None or item['status'] != 'pending':
            return False
        item.update(status=status, error=error)
        return True
    thread._store.update_turn_request(turn, change)


def finish(thread, turn):
    """A crash/missing acknowledgement cannot leave a receipt claiming delivery forever."""
    def change(record):
        changed = False
        for item in record.get('steering', []):
            if item['status'] == 'pending':
                item.update(status='uncertain', error='The run ended without confirming delivery. Check its response before sending again.')
                changed = True
        return changed
    thread._store.update_turn_request(turn, change)


def available(active):
    return bool(active and not active.cancelled and getattr(active, 'steering_enabled', False)
                and getattr(active.process, 'can_steer', False))


def submit(root, agent, name, run_id, identity, text, *, registry=None, lock=None):
    from .execution import ACTIVE_RUNS, RUNS_LOCK
    from .thread_windows import target
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT or '\0' in text:
        raise ValueError('Steering must contain 1–32,000 characters of text.')
    if not isinstance(identity, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{8,80}', identity):
        raise ValueError('Invalid steering request ID.')
    if not isinstance(run_id, str) or not run_id:
        raise ValueError('Steering requires the exact active run ID.')
    context, _, _, _ = target(root, agent, name)
    registry = ACTIVE_RUNS if registry is None else registry
    thread = Thread(Path(context.root)/'agents'/agent, name)
    with RUNS_LOCK if lock is None else lock:
        existing = next((r for r in receipts(thread._messages()) if r['id'] == identity), None)
        active = registry.get((context.realm_id, run_id))
        if active and (active.context.agent != agent or active.context.thread != name):
            active = None
        if existing:
            if existing.get('run_id') != run_id or existing.get('text') != text:
                raise ValueError('This steering request ID was already used for another message.')
            if existing['status'] == 'pending' and not active:
                resolve(thread, existing['turn'], identity, 'uncertain', 'The run ended without confirming delivery.')
                existing.update(status='uncertain', error='The run ended without confirming delivery.')
            return existing
        if not available(active):
            raise ValueError('This run is no longer accepting steering. Your message was not sent.')
        turn = active.steering_turn
        item = {'id': identity, 'run_id': run_id, 'turn': turn, 'text': text, 'status': 'pending',
                'error': '', 'ts': datetime.datetime.now().astimezone().isoformat(timespec='seconds')}
        def add(record):
            rows = record.setdefault('steering', [])
            if len(rows) >= 64:
                raise ValueError('This run has reached its steering-message limit.')
            rows.append(item)
            return True
        thread._store.update_turn_request(turn, add, require_open=True)
        active.steering_received = True
        try:
            active.process.steer(identity, text, lambda status, error='': resolve(thread, turn, identity, status, error))
        except Exception as exc:
            logging.getLogger(__name__).debug('Steering admission rejected', exc_info=True)
            resolve(thread, turn, identity, 'rejected', str(exc)[:1000])
            item.update(status='rejected', error=str(exc)[:1000])
        return item
