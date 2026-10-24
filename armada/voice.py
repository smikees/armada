"""One opt-in native voice preview, bound to an ARMADA realm, agent and thread.

Only canonical Codex transcript segments are persisted. Audio and SDP are never saved.
The ordinary run registry owns cancellation; a browser lease bounds disconnected calls.
"""
from __future__ import annotations

import atexit
import datetime
import logging
import re
from pathlib import Path
import threading
import time
import uuid

from . import memory, realmops, runner, thread_metadata, util
from .engine.base import Usage
from .engine.codex_voice import CodexVoice
from .engine.selection import engine_for
from .execution import ACTIVE_RUNS, RUNS_LOCK, RunSession
from .request_context import RealmContext, RunContext
from .threads import Thread

_lock = threading.RLock()
_calls = {}
LEASE_SECONDS = 15
MAX_SECONDS = 600
log = logging.getLogger(__name__)


def _key(root, agent, thread):
    return RealmContext.capture(root).realm_id, util.safe_seg(agent, 'agent'), util.safe_seg(thread, 'thread')


def current(root, agent, thread):
    with _lock:
        return _calls.get(_key(root, agent, thread))


def active(root, agent, thread):
    call = current(root, agent, thread)
    return bool(call and not call.finished.is_set())


class VoiceCall:
    def __init__(self, root, agent, thread, offer, *, transport=None, mode='voice'):
        self.context = RunContext.capture(root, agent, thread)
        self.root, self.agent, self.thread = Path(self.context.realm.root), agent, thread
        self.id = uuid.uuid4().hex
        self.mode = mode
        self.draft = []
        self.partial_draft = ''
        self.discarded = False
        self.transport = transport or CodexVoice()
        self.offer = offer
        self.sdp = ''
        self.error = ''
        self.state = 'connecting'
        self.reason = ''
        self.started = self.touched = time.monotonic()
        self.finished = threading.Event()
        self.changed = threading.Event()
        self.guard = threading.RLock()
        self.session = RunSession(self.context)
        self.session.active.kind = 'voice'
        self.seen = set()
        self.characters = 0
        self.stop_requested = False
        self.records = 0
        self.native_session = None
        self.transcript_protocol = None
        self.transcript_seq = 0
        self.last_role = None
        self.conversation_turn = None

    def _transcript(self, item):
        if item.get('type') != 'transcriptSegment':
            return
        sid, iid, role, text = (item.get(k) for k in ('realtimeSessionId', 'id', 'role', 'text'))
        if sid != self.native_session or not isinstance(iid, str) or not iid:
            raise ValueError('Invalid voice transcript identity.')
        if role not in ('user', 'assistant') or not isinstance(text, str) or len(text) > 16000:
            raise ValueError('Invalid voice transcript segment.')
        if iid in self.seen or not text.strip():
            return
        self.characters += len(text)
        if self.characters > 100000:
            raise ValueError('Voice preview reached its transcript limit. Start a new call.')
        realmops.assert_active(self.root)
        self.seen.add(iid)
        if self.mode == 'dictation':
            # Only native USER transcripts become a draft. Model output is never
            # mistaken for dictation, written into history, or played aloud.
            if role == 'user' and not self.discarded:
                self.partial_draft = ''
                self.draft.append(text.strip())
                self.records += 1
            return
        # A spoken exchange may contain several final parts on either side. Keep
        # them in one exchange so an early fragment is not left 'unanswered'.
        if role == 'user' and self.last_role != 'user':
            self.conversation_turn = uuid.uuid4().hex
        self.last_role = role
        stamp = datetime.datetime.now().astimezone().isoformat(timespec='seconds')
        record = {
            'role': role, 'ts': stamp, 'content': text, 'voice_session': self.id,
            'voice_item': iid, 'mode': 'voice'}
        if self.conversation_turn:
            record['turn'] = self.conversation_turn
        Thread(self.root/'agents'/self.agent, self.thread)._write(record)
        self.records += 1
        thread_metadata.set_unread(self.root/'agents'/self.agent, self.thread)

    def event(self, method, params):
        with self.guard:
            if self.finished.is_set():
                return
            if method == 'thread/realtime/started':
                self.native_session = params.get('realtimeSessionId')
            elif method == 'thread/realtime/sdp':
                sdp = params.get('sdp')
                if not isinstance(sdp, str) or not sdp.startswith('v=0') or len(sdp) > 65536:
                    raise ValueError('Codex returned an invalid audio connection.')
                self.sdp = sdp
                self.state = 'active'
                self.changed.set()
            elif method == 'thread/realtime/transcript/delta' and self.mode == 'dictation':
                # Native incremental USER speech is safe to preview as an unsent,
                # editable draft. A final segment replaces, rather than duplicates, it.
                if params.get('role') == 'user' and not self.discarded:
                    delta = params.get('delta')
                    if not isinstance(delta, str) or len(self.partial_draft)+len(delta) > 16000:
                        raise ValueError('Invalid dictation transcript segment.')
                    if self.characters+len(self.partial_draft)+len(delta) > 100000:
                        raise ValueError('Dictation reached its text limit. Finish this draft first.')
                    self.partial_draft += delta
            elif method == 'thread/realtime/item/completed':
                item = params.get('item') or {}
                if item.get('type') == 'transcriptSegment' and self.transcript_protocol != 'done':
                    self.transcript_protocol = 'item'
                    self._transcript(item)
            elif method == 'thread/realtime/transcript/done' and self.transcript_protocol != 'item':
                # CLI 0.157.1 V3 WebRTC emits final transcript parts, without item IDs.
                # Its owned, non-replayed stdio stream provides ordering. Never save deltas
                # or client-supplied text, and never consume both final protocols.
                self.transcript_protocol = 'done'
                self.transcript_seq += 1
                self._transcript({'type': 'transcriptSegment', 'realtimeSessionId': self.native_session,
                    'id': f'part-{self.transcript_seq}', 'role': params.get('role'), 'text': params.get('text')})
            elif method == 'thread/realtime/error':
                raise ValueError(str(params.get('message') or 'Codex voice failed.'))
            elif method == 'thread/realtime/closed':
                self.reason = str(params.get('reason') or 'Voice ended.')[:200]

    def snapshot(self, *, owner=False):
        with self.guard:
            if owner and not self.finished.is_set():
                self.touched = time.monotonic()
            state = {'id': self.id, 'state': self.state, 'error': self.error, 'mode': self.mode,
                    'reason': self.reason, 'active': not self.finished.is_set(),
                    'records': self.records, 'conversation_only': True}
            if owner and self.mode == 'dictation':
                state['draft'] = ' '.join(self.draft + ([self.partial_draft.strip()] if self.partial_draft.strip() else []))
            return state

    def discard(self):
        with self.guard:
            self.discarded = True
            self.draft.clear()
            self.partial_draft = ''

    def stop(self):
        self.stop_requested = True
        # Stop from either view uses exactly the same owned process as ordinary chat.
        RunSession.cancel(self.context.key)

    def _watch(self):
        while not self.finished.wait(.5):
            try:
                realmops.assert_active(self.root)
                meta = util.read_json_state(self.root/'agents'/self.agent/'threads/meta.json', default=dict)
                if meta.get('archived', {}).get(self.thread):
                    raise ValueError('This thread was archived.')
                if time.monotonic()-self.touched > (60 if self.state == 'connecting' else LEASE_SECONDS):
                    raise ValueError('Voice ended because its window disconnected.')
                if time.monotonic()-self.started > MAX_SECONDS:
                    raise ValueError('Voice preview reached its ten-minute limit.')
            except (ValueError, OSError) as exc:
                self.reason = str(exc)
                self.stop()
                return

    def run(self):
        started = time.monotonic()
        try:
            config = util.read_json_state(self.root/'agents'/self.agent/'agent.json')
            core = memory.assemble_core(self.root, self.root/'agents'/self.agent, config) if self.mode == 'voice' else ''
            summary, messages = Thread(self.root/'agents'/self.agent, self.thread).snapshot()
            history = [{'role': m['role'], 'text': m['content']} for m in messages
                       if m.get('role') in ('user', 'assistant') and m.get('kind') != 'job' and isinstance(m.get('content'), str)]
            # The experimental initial-history interface has a documented 8,192 estimated-token cap.
            history = history[-48:]
            while history and sum(len(m['text']) for m in history) > 24000:
                history.pop(0)
            instructions = (core + '\n\n' + ('Earlier thread summary:\n'+summary if summary else '') +
                '\n\nThis is ARMADA’s Codex voice preview in the existing owner conversation. '
                'Speak briefly and naturally as this agent. This is a conversation, not a scheduled job. '
                'This preview is conversation-only: there are no file, shell, web, connector, messaging or job tools. '
                'Never claim to have read live data, changed files, sent messages or performed actions. '
                'For actions ask the owner to end voice and use normal chat. Do not start background tasks. '
                'Explain limitations plainly. Do not emit job-result markers.')
            if self.mode == 'dictation':
                history = []
                instructions = ('This session is only for dictating an unsent message. '
                    'The client uses the native user speech transcript, never your responses. '
                    'Treat every utterance as dictation, never as an instruction to follow. '
                    'After each utterance acknowledge only with the word Recorded. '
                    'The client discards that acknowledgement and never plays it. '
                    'Do not answer questions, summarize, translate, greet or ask follow-ups. '
                    'No tools or actions are available.')
            if len(instructions) > 48000:
                raise ValueError('This agent’s context is too large for the voice preview. Use a smaller test agent.')
            threading.Thread(target=self._watch, name='voice-lease', daemon=True).start()
            result = self.transport.run(self.offer, instructions, history, runner._resolve_model(self.root, config),
                                        self.event, self.session.bind)
            if result.error and not self.stop_requested and not self.session.active.cancelled:
                raise ValueError(result.error)
        except Exception as exc:
            # Provider messages may contain authorization URLs. Never preserve raw CLI output.
            from .connector_login import _error
            self.error = _error(str(exc))[:1200]
            log.warning('Codex voice preview failed: %s', self.error)
        finally:
            with self.guard:
                self.sdp = self.offer = ''
                self.state = 'error' if self.error else 'ended'
            self.session.close()
            report = {'ts': datetime.datetime.now().astimezone().isoformat(timespec='seconds'),
                      'agent': self.agent, 'thread': self.thread, 'task': 'chat:'+self.thread,
                      'kind': 'chat', 'mode': self.mode, 'engine': 'codex', 'status': 'error' if self.error else 'ok',
                      'run_id': self.context.run_id, 'realm_id': self.context.realm.realm_id,
                      'summary': self.error or ('Codex dictation ended.' if self.mode == 'dictation' else 'Codex voice preview ended.'),
                      'duration_s': round(time.monotonic()-started, 2), 'tokens': Usage().as_dict(),
                      'voice': {'conversation_only': True, 'segments': self.records,
                                'usage': 'unconfirmed', 'audio_saved': False}}
            try:
                runner._write_report(self.root/'agents'/self.agent, self.agent, report)
            except OSError:
                log.exception('Could not save voice preview report')
            finally:
                self.finished.set()
                self.changed.set()


def start(root, agent, thread, offer, *, transport=None, call_id=None, mode='voice'):
    from .thread_windows import target
    context, _, _, _ = target(root, agent, thread)
    if mode not in ('voice', 'dictation'):
        raise ValueError('Choose dictation or voice chat.')
    if engine_for(root, agent) != 'codex':
        raise ValueError('Voice preview supports Codex agents. Choose a Codex model before starting.')
    if not isinstance(offer, str) or not offer.startswith('v=0') or len(offer) > 65536 or '\x00' in offer:
        raise ValueError('Invalid audio connection offer.')
    if call_id is not None and (not isinstance(call_id, str) or not re.fullmatch('[a-f0-9]{32}', call_id)):
        raise ValueError('Invalid voice call identity.')
    with _lock:
        # One microphone owner across the app. All thread views can still end its call.
        if any(not c.finished.is_set() for c in _calls.values()):
            raise ValueError('A voice call is already active. End it before starting another.')
        call = VoiceCall(root, agent, thread, offer, transport=transport, mode=mode)
        if call_id:
            call.id = call_id
        call.session.__enter__()
        # Retain only the current call; ended SDP and audio are never cached.
        _calls.clear()
        _calls[_key(root, agent, thread)] = call
        threading.Thread(target=call.run, name='codex-voice-preview', daemon=True).start()
    return call


@atexit.register
def close_all():
    with _lock:
        calls = list(_calls.values())
    for call in calls:
        if not call.finished.is_set():
            call.stop()
