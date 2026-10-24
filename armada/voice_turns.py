"""Admit native speech as ordinary agent work, independently of the audio call.

Accepted messages and queued progress are saved before returning. The server owns the
FIFO worker and RunSessions: leaving voice or closing a view never cancels its work.
Like typed turns, an application shutdown does not automatically replay side effects.
"""
from collections import deque
import datetime
import logging
from pathlib import Path
import threading
import time

from . import thread_metadata, util
from .execution import ACTIVE_RUNS, RUNS_LOCK, RunSession, TurnCoordinator, TurnRequest
from .request_context import RunContext
from .threads import Thread

_lock = threading.RLock()
_queues = {}
log = logging.getLogger(__name__)


def _target(root, agent, thread):
    from .thread_windows import target
    target(root, agent, thread)
    path = Path(root)/'agents'/agent/'threads/meta.json'
    with util.file_lock(path, validate_state=False):
        meta = util.read_json_state(path, default=dict)
    if meta.get('archived', {}).get(thread):
        raise ValueError('This thread was archived.')


def submit(root, agent, thread, text, *, voice_session, voice_item, reply=None):
    _target(root, agent, thread)
    context = RunContext.capture(root, agent, thread)
    key = (context.realm.realm_id, agent, thread)
    session = RunSession(context)
    session.active.kind = 'voice_work'
    th = Thread(Path(context.realm.root)/'agents'/agent, thread)
    with _lock:
        session.__enter__()
        try:
            th._write({'role': 'user', 'content': text, 'turn': context.run_id,
                'ts': datetime.datetime.now().astimezone().isoformat(timespec='seconds'),
                'mode': 'voice', 'voice_request': True, 'voice_session': voice_session,
                'voice_item': voice_item})
            th.save_progress(context.run_id, '', 'Queued…')
            thread_metadata.set_unread(Path(context.realm.root)/'agents'/agent, thread)
        except Exception:
            session.close()
            raise
        queue = _queues.setdefault(key, deque())
        queue.append((context, session, text, reply))
        if len(queue) == 1:
            threading.Thread(target=_drain, args=(key,), name='voice-agent-work', daemon=True).start()
    return context.run_id


def _drain(key):
    while True:
        with _lock:
            context, session, text, reply = _queues[key][0]
        th = Thread(Path(context.realm.root)/'agents'/context.agent, context.thread)
        try:
            # A call can open during an existing typed run. Its requests wait for that
            # result too, instead of starting a second agent against stale history.
            while not session.active.cancelled:
                with RUNS_LOCK:
                    busy = any(r.context.realm == context.realm and r.context.agent == context.agent
                        and r.context.thread == context.thread
                        and getattr(r, 'kind', 'chat') not in ('voice_audio', 'voice_work')
                        for r in ACTIVE_RUNS.values())
                if not busy:
                    break
                time.sleep(.05)
            _target(context.realm.root, context.agent, context.thread)
            records = [m for m in th._messages() if m.get('turn') == context.run_id]
            if len(records) != 1 or records[0].get('role') != 'user':
                # An owner may have removed or already answered a queued request.
                continue
            if session.active.cancelled:
                th.complete_turn(context.run_id, 'Run stopped by the owner.', status='stopped')
                result = None
            else:
                th.save_progress(context.run_id, '', 'Thinking…')
                result = TurnCoordinator(TurnRequest(context, text, 'auto', True,
                    admitted_turn=context.run_id), session=session).run()
            if result and reply:
                try:
                    reply(result)
                except Exception:
                    log.exception('Could not speak the saved agent reply')
        except Exception as exc:
            log.exception('Spoken request failed')
            # Do not recreate a deleted/archived thread when reporting a failure.
            try:
                _target(context.realm.root, context.agent, context.thread)
                records = [m for m in th._messages() if m.get('turn') == context.run_id]
                if len(records) == 1 and records[0].get('role') == 'user':
                    th.complete_turn(context.run_id, 'Could not run this request: '+str(exc), status='error')
            except (ValueError, OSError):
                log.exception('Could not save spoken request failure')
        finally:
            session.close()
            with _lock:
                queue = _queues[key]
                queue.popleft()
                if not queue:
                    del _queues[key]
                    return
