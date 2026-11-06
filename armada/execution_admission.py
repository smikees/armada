"""Account-wide bounded execution, with kernel-owned tickets and fair realm turns.

Tickets are scheduling metadata, never permission grants or replay instructions. A dead
owner frees capacity; the caller's durable attempt record retains any uncertain outcome.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import logging
import math
import os
from pathlib import Path
import threading
import time
import uuid

from . import util

TOTAL = 4
PER_PROVIDER = 2
PER_REALM = 2
MAX_TICKETS = 128
PER_REALM_QUEUE = 32
POLL_SECONDS = .1
_current = ContextVar('armada_execution_ticket', default=None)
log = logging.getLogger(__name__)


class QueueFull(util.StateError):
    pass


class Cancelled(util.StateError):
    pass


def _directory():
    from .instance import _account_directory
    return _account_directory() / 'execution'


def _state_path():
    return _directory() / 'admission.json'


def _slot_path(slot):
    return _directory() / f'owner-{slot}'


def _read():
    state = util.read_json_state(_state_path(), default=lambda: {
        'schema_version': 1, 'next': 0, 'last_realm': '', 'swept_at': 0, 'tickets': {}}, max_schema=1)
    rows = state.get('tickets')
    valid = (type(state.get('schema_version')) is int and state['schema_version'] == 1 and type(state.get('next')) is int
             and state['next'] >= 0 and isinstance(state.get('last_realm'), str)
             and type(state.get('swept_at')) in (int, float) and math.isfinite(state['swept_at'])
             and isinstance(rows, dict) and len(rows) <= MAX_TICKETS)
    if valid:
        seen = set()
        for slot, row in rows.items():
            if (slot not in {str(n) for n in range(MAX_TICKETS)} or not isinstance(row, dict)
                    or row.get('state') not in ('queued', 'running')
                    or type(row.get('cancelled')) is not bool
                    or type(row.get('seq')) is not int or not 0 <= row['seq'] < state['next']
                    or row['seq'] in seen or type(row.get('pid')) is not int
                    or not all(isinstance(row.get(k), str) and row[k] for k in
                               ('token', 'realm', 'root', 'agent', 'thread', 'run_id', 'provider'))):
                valid = False
                break
            seen.add(row['seq'])
    if not valid:
        raise util.StateError('Invalid execution admission state; new work is held. Preserve admission.json before repairing it.')
    return state


def _prune(state):
    # Probe the stable kernel lock, not PID liveness (PIDs can be reused).
    for slot in list(state['tickets']):
        try:
            with util.file_lock(_slot_path(slot), timeout=0, validate_state=False):
                del state['tickets'][slot]
        except util.FileLockTimeout:
            pass


def _promote(state):
    rows = list(state['tickets'].values())
    active = [r for r in rows if r['state'] == 'running']
    pending = sorted((r for r in rows if r['state'] == 'queued' and not r['cancelled']), key=lambda r: r['seq'])
    while pending:
        eligible = []
        for row in pending:
            # Maintenance wrappers have their own single slot: a wrapper may await a model
            # child, so occupying every model slot here would cause a nested-admission deadlock.
            maintenance = row['provider'] == 'maintenance'
            group = [r for r in active if (r['provider'] == 'maintenance') == maintenance]
            if len(group) >= (1 if maintenance else TOTAL):
                continue
            if sum(r['provider'] == row['provider'] for r in group) >= PER_PROVIDER:
                continue
            if sum(r['realm'] == row['realm'] for r in group) >= PER_REALM:
                continue
            identity = (row['realm'], row['agent'], row['thread'])
            if any((r['realm'], r['agent'], r['thread']) == identity for r in active):
                continue
            # Preserve FIFO for a conversation even when its provider changed while queued.
            if any((r['realm'], r['agent'], r['thread']) == identity for r in pending[:pending.index(row)]):
                continue
            eligible.append(row)
        if not eligible:
            break
        realms = list(dict.fromkeys(r['realm'] for r in eligible))
        last = state['last_realm']
        selected_realm = realms[(realms.index(last) + 1) % len(realms)] if last in realms else realms[0]
        row = next(r for r in eligible if r['realm'] == selected_realm)
        row['state'] = 'running'
        state['last_realm'] = selected_realm
        pending.remove(row)
        active.append(row)


@contextmanager
def _transaction():
    with util.file_lock(_state_path(), validate_state=False):
        state = _read()
        before = repr(state)
        now = time.monotonic()
        if not 0 <= now - state['swept_at'] < .5:
            _prune(state)
            state['swept_at'] = now
        yield state
        if repr(state) != before:
            util.write_json_atomic(_state_path(), state)


class Ticket:
    def __init__(self, context, provider, *, realm_required=True):
        if not isinstance(provider, str) or not provider or len(provider) > 80:
            raise util.StateError('Invalid execution resource.')
        self.context, self.provider = context, provider
        self.slot = self.token = self.owner = None
        self._callbacks = set()
        self._callback_lock = threading.Lock()
        self._stop = threading.Event()
        self._watcher = None
        self.cancelled = False
        try:
            self._publish(context, provider, realm_required)
        except BaseException:
            if self.owner is not None:
                self.owner.__exit__(None, None, None)
                self.owner = None
            raise

    def _publish(self, context, provider, realm_required):
        from . import updater, realmops
        with updater.admission_lock(), realmops.lifecycle_lock(context.realm.root):
            if updater.installed() and updater.admission_paused():
                raise util.StateError('ARMADA is updating. New work can start after it reopens.')
            if realm_required:
                realmops.assert_active(context.realm.root)
            with _transaction() as state:
                rows = state['tickets']
                if any(r['realm'] == context.realm.realm_id and r['run_id'] == context.run_id for r in rows.values()):
                    raise util.StateError('This run ID already has an execution owner.')
                if len(rows) >= MAX_TICKETS or sum(r['realm'] == context.realm.realm_id for r in rows.values()) >= PER_REALM_QUEUE:
                    raise QueueFull('The execution queue is full. Wait for a task to finish, then try again.')
                self.slot = next(str(n) for n in range(MAX_TICKETS) if str(n) not in rows)
                owner = util.file_lock(_slot_path(self.slot), timeout=0, validate_state=False)
                owner.__enter__()
                self.owner = owner
                self.token = uuid.uuid4().hex
                rows[self.slot] = dict(token=self.token, realm=context.realm.realm_id,
                    root=context.realm.root, agent=context.agent, thread=context.thread,
                    run_id=context.run_id, provider=provider, pid=os.getpid(),
                    state='queued', seq=state['next'], cancelled=False)
                state['next'] += 1
            # The ticket is published only while its kernel ownership is held.

    def _row(self, state):
        row = state['tickets'].get(self.slot)
        if not row or row['token'] != self.token:
            raise util.StateError('Execution ownership changed; this work cannot start or continue.')
        return row

    def ready(self):
        with _transaction() as state:
            row = self._row(state)
            if row['cancelled']:
                self.cancelled = True
                raise Cancelled('Run stopped by the owner before execution.')
            _promote(state)
            return row['state'] == 'running'

    def wait(self, cancelled=lambda: False, on_wait=None):
        announced = False
        while True:
            if cancelled():
                raise Cancelled('Run stopped by the owner before execution.')
            if self.ready():
                return
            if not announced and on_wait:
                on_wait()
                announced = True
            self._stop.wait(POLL_SECONDS)

    def _watch(self):
        while not self._stop.wait(POLL_SECONDS):
            try:
                # Atomic snapshots suffice for cancellation; monitoring never rewrites state
                # or performs a kernel probe for every queued ticket on every poll.
                cancelled = self._row(_read())['cancelled']
            except OSError:
                # Losing admission evidence fails closed; never continue provider work on
                # an assumed grant. Callbacks retain the process owner's kill semantics.
                log.exception('Execution ownership could not be verified')
                cancelled = True
            if cancelled:
                self.cancelled = True
                with self._callback_lock:
                    callbacks = list(self._callbacks)
                for callback in callbacks:
                    try:
                        callback()
                    except Exception:
                        log.exception('Could not stop an admitted run; cancellation will be retried')

    @contextmanager
    def activate(self, on_cancel=None):
        token = _current.set(self)
        if on_cancel:
            with self._callback_lock:
                self._callbacks.add(on_cancel)
            if self.cancelled:
                on_cancel()
        if self._watcher is None:
            self._watcher = threading.Thread(target=self._watch, name='execution-cancellation', daemon=True)
            self._watcher.start()
        try:
            yield self
        finally:
            if on_cancel:
                with self._callback_lock:
                    self._callbacks.discard(on_cancel)
            _current.reset(token)

    def close(self):
        if self.owner is None:
            return
        self._stop.set()
        if self._watcher:
            self._watcher.join()
        try:
            with _transaction() as state:
                self._row(state)
                del state['tickets'][self.slot]
                # Keep reuse serialized with publication; another publisher cannot observe
                # a free slot whose previous kernel owner has not closed yet.
                self.owner.__exit__(None, None, None)
                self.owner = None
        finally:
            if self.owner is not None:
                self.owner.__exit__(None, None, None)
                self.owner = None


@contextmanager
def scope(context, provider, *, cancelled=lambda: False, on_cancel=None, on_wait=None, realm_required=True):
    inherited = _current.get()
    same = inherited and (inherited.context.realm, inherited.context.agent, inherited.context.thread) == (context.realm, context.agent, context.thread)
    if same:
        if inherited.provider != provider:
            raise util.StateError('The queued job provider changed. Start a new run with the current settings.')
        if inherited.cancelled or cancelled():
            raise Cancelled('Run stopped by the owner.')
        with inherited.activate(on_cancel):
            yield inherited
        return
    ticket = Ticket(context, provider, realm_required=realm_required)
    try:
        ticket.wait(lambda: cancelled() or bool(inherited and inherited.cancelled), on_wait)
        if inherited:
            with inherited.activate(on_cancel), ticket.activate(on_cancel):
                yield ticket
        else:
            with ticket.activate(on_cancel):
                yield ticket
    finally:
        ticket.close()


def cancel(realm_id, *, agent=None, thread=None, run_id=None):
    matched = 0
    with _transaction() as state:
        for row in state['tickets'].values():
            if (row['realm'] == realm_id and (agent is None or row['agent'] == agent)
                    and (thread is None or row['thread'] == thread)
                    and (run_id is None or row['run_id'] == run_id)):
                row['cancelled'] = True
                matched += 1
    return matched


def snapshot():
    with _transaction() as state:
        return [dict(row) for row in state['tickets'].values()]


def cancelled():
    ticket = _current.get()
    return bool(ticket and ticket.cancelled)


def view(root, agent=None, thread=None):
    """Read-only presentation hint. Kernel ownership, never this hint, admits execution."""
    from .request_context import RealmContext
    identity = RealmContext.capture(root).realm_id
    return [dict(row) for row in _read()['tickets'].values()
            if row['realm'] == identity and (agent is None or row['agent'] == agent)
            and (thread is None or row['thread'] == thread) and util.pid_alive(row['pid'])]


@contextmanager
def provider_call(provider, cwd=None, on_proc=None, on_wait=None):
    """Include auxiliary model calls (titles/search/reviews/compaction) in the same budget."""
    from .request_context import RunContext
    inherited = _current.get()
    required = False
    if inherited and inherited.provider != 'maintenance':
        if inherited.provider != provider:
            raise util.StateError('Nested execution cannot silently change provider capacity.')
        context = inherited.context
    else:
        root = Path(cwd).resolve() if cwd else _directory().parent
        if inherited:
            root = Path(inherited.context.realm.root)
        for candidate in (root, *root.parents):
            if (candidate / 'realm.json').is_file():
                root, required = candidate, True
                break
        context = RunContext.capture(root, 'system', 'aux-' + uuid.uuid4().hex)
    process = None
    stopped = False
    guard = threading.Lock()
    def stop():
        nonlocal stopped
        with guard:
            stopped = True
            if process is not None:
                process.kill()
    def bind(handle):
        nonlocal process
        with guard:
            process = handle
            if stopped:
                handle.kill()
        if on_proc:
            on_proc(handle)
    with scope(context, provider, on_cancel=stop, on_wait=on_wait, realm_required=required):
        yield bind
