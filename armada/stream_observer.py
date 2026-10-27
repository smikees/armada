"""A slow UI observer cannot hold the engine's event/cancellation loop."""
import json
import logging
import queue
import socket
import threading

log = logging.getLogger(__name__)
_slots = threading.BoundedSemaphore(16)


class StreamObserver:
    MAX_BYTES = 1024 * 1024

    def __init__(self, handler):
        self.handler = handler
        self.events = queue.Queue(maxsize=128)
        self.lock = threading.Lock()
        self.bytes = 0
        self.closed = threading.Event()
        self.worker = None
        if not _slots.acquire(blocking=False):
            self.disconnect()
            return
        connection = getattr(handler, 'connection', None)
        try:
            if connection is not None:
                connection.settimeout(2)
            self.worker = threading.Thread(target=self._deliver, name='armada-stream-observer', daemon=True)
            self.worker.start()
        except Exception:
            _slots.release()
            self.worker = None
            self.disconnect()
            log.debug('Could not start stream observer', exc_info=True)

    def disconnect(self):
        self.closed.set()
        connection = getattr(self.handler, 'connection', None)
        if connection is not None:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def __call__(self, event):
        if self.closed.is_set():
            return
        data = ('data: ' + json.dumps(event, ensure_ascii=False) + '\n\n').encode('utf-8')
        with self.lock:
            if self.bytes + len(data) > self.MAX_BYTES:
                self.disconnect()
                return
            self.bytes += len(data)
        try:
            self.events.put_nowait(data)
        except queue.Full:
            self.disconnect()

    def _deliver(self):
        try:
            while not self.closed.is_set() or not self.events.empty():
                try:
                    data = self.events.get(timeout=.1)
                except queue.Empty:
                    continue
                self.handler.wfile.write(data)
                self.handler.wfile.flush()
                with self.lock:
                    self.bytes -= len(data)
        except Exception:
            log.debug('Stream observer detached; persisted thread remains authoritative', exc_info=True)
            self.disconnect()
        finally:
            _slots.release()

    def close(self):
        self.closed.set()
        if self.worker:
            self.worker.join(2.2)
            if self.worker.is_alive():
                self.disconnect()
