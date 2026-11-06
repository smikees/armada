"""A bounded scheduler queue. Only admitted work receives a worker thread.

The daemon owns discovery and pumping; workers own execution and terminal evidence.
No executor's hidden/unbounded queue, and no worker is occupied waiting for a slot.
"""
import logging
import threading

from . import execution_admission as admission

log = logging.getLogger(__name__)


class Dispatcher:
    def __init__(self):
        self.pending = {}
        self.running = {}
        self.lock = threading.Lock()
        self.closed = False

    def contains(self, key):
        with self.lock:
            return key in self.pending or key in self.running

    def submit(self, context, provider, prepare):
        """Reserve bounded queue space before durable claiming. prepare returns work/cancel.

        A failed claim releases the reservation; a successful claim must always have its
        terminal callback called, or remain uncertain if persistence itself failed.
        """
        if self.closed:
            raise admission.Cancelled('The scheduler is stopping.')
        if self.contains(context.key):
            return False
        ticket = admission.Ticket(context, provider)
        try:
            callbacks = prepare()
            if callbacks is None:
                ticket.close()
                return False
            with self.lock:
                self.pending[context.key] = (ticket, *callbacks)
            return True
        except BaseException:
            ticket.close()
            raise

    def pump(self):
        for key, (ticket, work, cancelled) in list(self.pending.items()):
            try:
                ready = ticket.ready()
            except (OSError, ValueError) as exc:
                try:
                    cancelled(str(exc))
                except Exception:
                    log.exception('Could not record queued cancellation; attempt remains uncertain')
                finally:
                    with self.lock:
                        self.pending.pop(key, None)
                    ticket.close()
                continue
            if not ready:
                continue
            worker = threading.Thread(target=self._run, args=(key, ticket, work),
                                      name='scheduled-execution', daemon=True)
            with self.lock:
                self.running[key] = (ticket, worker)
                del self.pending[key]
            try:
                worker.start()
            except BaseException:
                with self.lock:
                    del self.running[key]
                try:
                    cancelled('The execution worker could not start.')
                finally:
                    ticket.close()
                raise

    def _run(self, key, ticket, work):
        try:
            with ticket.activate():
                work()
        except BaseException:
            # The caller owns its durable result. Never fabricate success or retry a
            # callback that may already have performed external side effects.
            log.exception('Scheduled execution ended without a recorded outcome')
        finally:
            try:
                ticket.close()
            finally:
                with self.lock:
                    self.running.pop(key, None)

    def cancel_pending(self, root, reason='The scheduler stopped before this job began.'):
        for key, (ticket, work, cancelled) in list(self.pending.items()):
            if ticket.context.realm.root != str(root.resolve()):
                continue
            try:
                cancelled(reason)
            except Exception:
                log.exception('Could not record queued cancellation; attempt remains uncertain')
            finally:
                with self.lock:
                    self.pending.pop(key, None)
                ticket.close()

    def busy(self, root):
        with self.lock:
            return any(t.context.realm.root == str(root.resolve()) for t, _ in self.running.values())

    def close(self):
        self.closed = True
        for ticket, _, _ in list(self.pending.values()):
            from pathlib import Path
            self.cancel_pending(Path(ticket.context.realm.root))
        with self.lock:
            running = list(self.running.values())
        for ticket, _ in running:
            admission.cancel(ticket.context.realm.realm_id, run_id=ticket.context.run_id)
        for _, worker in running:
            worker.join()
