"""Inactivity supervision for unattended agent turns; time spent queued is excluded."""
import datetime as dt
import threading
import time


class Watchdog:
    def __init__(self, root, agent, thread, settings, stop, *, scheduled=False, clock=time.monotonic):
        self.root, self.agent, self.thread, self.stop = root, agent, thread, stop
        self.clock = clock
        self.quiet = float(settings.get('agent_inactivity_minutes', 30)) * 60
        self.soft = float(settings.get('agent_soft_mark_minutes', 60)) * 60 if scheduled else 0
        if self.quiet <= 0 or self.soft < 0:
            raise ValueError('Inactivity must be positive and the soft mark cannot be negative.')
        self.started = self.last = clock()
        self.last_at = dt.datetime.now(dt.timezone.utc).isoformat()
        self.stalled = self.notified = False
        self.suspended = False
        self.done = threading.Event()
        self.worker = None

    def event(self, event):
        if event.get('waiting_for_plan'):
            self.suspended = True
        # Queue/status messages are Armada activity, not evidence of a live engine.
        if event.get('kind') != 'status':
            self.suspended = False
            self.last = self.clock()
            self.last_at = dt.datetime.now(dt.timezone.utc).isoformat()

    def check(self):
        if self.suspended:
            return
        now = self.clock()
        if not self.stalled and now - self.last >= self.quiet:
            self.stalled = True
        if self.stalled:
            self.stop()  # Retry a failed kill until the owned process exits.
        if self.soft and not self.notified and now - self.started >= self.soft:
            self.notified = True
            from . import notify
            notify.emit(self.root, 'job_long_running', 'A scheduled job is still running',
                        f'{self.agent}: running for {int((now-self.started)/60)} minutes. Open the thread to Stop.', self.href)

    @property
    def href(self):
        from urllib.parse import quote
        from .job_history import JOB_PREFIX
        if self.thread.startswith(JOB_PREFIX):
            return f'/agent/{quote(self.agent, safe="")}/jobs?job={quote(self.thread[len(JOB_PREFIX):], safe="")}'
        return f'/agent/{quote(self.agent, safe="")}/threads?thread={quote(self.thread, safe="")}'

    def _watch(self):
        import logging
        while not self.done.wait(min(1, self.quiet / 4)):
            try:
                self.check()
            except Exception:
                logging.getLogger(__name__).exception('Could not supervise an unattended run')

    def __enter__(self):
        self.worker = threading.Thread(target=self._watch, name='agent-inactivity', daemon=True)
        self.worker.start()
        return self

    def __exit__(self, *args):
        self.done.set()
        if self.worker:
            self.worker.join()
