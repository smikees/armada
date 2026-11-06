"""Bounded asynchronous native script calls; no worker thread per browser call."""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import threading
import time

log = logging.getLogger(__name__)


@dataclass(eq=False)
class _Call:
    script: str
    done: threading.Event = field(default_factory=threading.Event)
    task: object = None
    started: bool = False
    value: object = None
    error: str = ""


class ScriptCalls:
    """Native UI timer polls at most four tasks; timeouts retain their capacity.

    Reset only after the owning WebView is withdrawn/disposed. Queued and late
    completions cannot cross that generation boundary or create extra workers.
    """
    def __init__(self, post, start, *, capacity=4):
        self.post, self.start, self.capacity = post, start, capacity
        self.lock = threading.Lock()
        self.calls = set()
        self.closed = False

    def evaluate(self, script, timeout=10):
        deadline = time.monotonic() + timeout
        call = _Call(script)
        with self.lock:
            if self.closed or len(self.calls) >= self.capacity:
                raise OSError("The browser is unavailable or busy with an unresponsive operation")
            self.calls.add(call)
        def begin():
            with self.lock:
                if call not in self.calls:
                    return
                call.started = True
            # Native dispatch can itself stall. Never hold the caller's deadline
            # lock across it, and never attach a late task to a replaced view.
            try:
                task = self.start(call.script)
                with self.lock:
                    if call in self.calls:
                        call.task = task
            except Exception as exc:
                log.debug('Native script start failed (%s)', type(exc).__name__)
                self._finish(call, error="The browser could not start its operation")
        try:
            self.post(begin)
        except Exception as exc:
            log.debug('Native script dispatch failed (%s)', type(exc).__name__)
            self._finish(call, error="The native window could not accept its operation")
        if not call.done.wait(max(0, deadline - time.monotonic())):
            with self.lock:
                # A delayed BeginInvoke must not execute an already expired request.
                if not call.started:
                    self.calls.discard(call)
            raise OSError("The browser did not complete its operation before the deadline")
        if call.error:
            raise OSError(call.error)
        return call.value

    def _finish(self, call, *, value=None, error=""):
        with self.lock:
            if call not in self.calls:
                return
            self.calls.remove(call)
            call.value, call.error = value, error
            call.done.set()

    def poll(self):
        with self.lock:
            calls = list(self.calls)
        for call in calls:
            task = call.task
            if task is None or not task.IsCompleted:
                continue
            try:
                result = json.loads(str(task.Result))
                if result.get("exceptionDetails"):
                    raise ValueError("script failed")
                self._finish(call, value=result.get("result", {}).get("value"))
            except Exception as exc:
                log.debug('Native script completion failed (%s)', type(exc).__name__)
                self._finish(call, error="The browser could not complete its operation")

    def reset(self, *, close=False):
        with self.lock:
            self.closed = close
            for call in self.calls:
                call.error = "The browser view changed before the operation completed"
                call.done.set()
            self.calls.clear()
