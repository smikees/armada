"""Bound local HTTP input before allocating request workers.

Incomplete headers share one socket gate. Completed requests use separate bounded
lanes so streams and ordinary work cannot consume the control lane. Every lane
still goes through the normal Host, origin, authentication and realm checks.
"""
from __future__ import annotations

import http.server
import io
import json
import select
import socket
import sys
import threading
import time
from urllib.parse import urlsplit

HEADER_BYTES = 32 * 1024
BODY_BYTES = 16 * 1024 * 1024
HEADER_SECONDS = 5.0
BODY_SECONDS = 15.0
WRITE_SECONDS = 30.0
PENDING_CONNECTIONS = 128
LANES = {"ordinary": 24, "stream": 16, "control": 4}
CONTROL = {("GET", "/health"), ("GET", "/api/instance"),
           ("GET", "/api/chat-stop"), ("POST", "/api/voice-stop"),
           ("POST", "/api/dry-run-stop"), ("POST", "/api/update-cancel"),
           ("POST", "/api/startup-abort")}
STREAMS = {("POST", "/api/chat-stream"), ("POST", "/api/alexander-ask")}


class RequestError(ValueError):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def read_body(handler):
    """Strict framing and JSON; invalid input must never become an empty mutation."""
    lengths = [value.strip(" \t") for value in handler.headers.get_all("Content-Length", [])]
    if handler.headers.get_all("Transfer-Encoding", []):
        raise RequestError(400, "Transfer-Encoding is not supported; send Content-Length.")
    if len(lengths) > 1 or (lengths and (not lengths[0].isascii() or not lengths[0].isdecimal())):
        raise RequestError(400, "Content-Length must be a single non-negative integer.")
    # Compare length first so extremely long decimal strings cannot exhaust int().
    value = (lengths[0].lstrip("0") or "0") if lengths else "0"
    if len(value) > 8 or int(value) > BODY_BYTES:
        raise RequestError(413, "Request exceeds the 16 MiB limit. Send fewer or smaller attachments.")
    size = int(value)
    if not size:
        return {}
    try:
        data = handler.rfile.read(size)
    except (TimeoutError, socket.timeout):
        raise RequestError(408, "Request body timed out. Retry the operation.") from None
    if len(data) != size:
        raise RequestError(400, "Request body ended before Content-Length.")
    try:
        def invalid_constant(value):
            raise ValueError("Non-JSON numeric constant")
        result = json.loads(data.decode("utf-8-sig"), parse_constant=invalid_constant)
    except (UnicodeError, ValueError, RecursionError):
        raise RequestError(400, "Request body must be a valid JSON object.") from None
    if not isinstance(result, dict):
        raise RequestError(400, "Request body must be a JSON object.")
    return result


class _Input(io.RawIOBase):
    def __init__(self, connection):
        super().__init__()
        self.connection = connection

    def readable(self):
        return True

    def readinto(self, target):
        connection = self.connection
        if connection.prefix:
            count = min(len(target), len(connection.prefix))
            target[:count] = connection.prefix[:count]
            del connection.prefix[:count]
            return count
        remaining = connection.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("HTTP input deadline exceeded")
        connection.socket.settimeout(remaining)
        return connection.socket.recv_into(target)


class _Connection:
    def __init__(self, sock, prefix):
        self.socket = sock
        self.prefix = prefix
        self.deadline = time.monotonic() + BODY_SECONDS

    def makefile(self, mode, buffering=-1):
        if mode == "rb":
            return io.BufferedReader(_Input(self))
        return self.socket.makefile(mode, buffering)

    def sendall(self, data):
        self.socket.settimeout(WRITE_SECONDS)
        return self.socket.sendall(data)

    def __getattr__(self, name):
        return getattr(self.socket, name)


def _refuse(sock, status):
    # Never wait on a client while holding the gate. Small best-effort response.
    try:
        sock.setblocking(False)
        reason = http.server.BaseHTTPRequestHandler.responses[status][0]
        message = {503: "ARMADA is busy. Wait a moment and retry.",
                   408: "Request headers timed out. Retry the operation.",
                   431: "Request headers are too large."}.get(status, "Invalid HTTP request.")
        body = json.dumps({"ok": False, "error": message}).encode("utf-8")
        retry = "Retry-After: 1\r\n" if status == 503 else ""
        sock.send((f"HTTP/1.0 {status} {reason}\r\nConnection: close\r\n"
                   f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n"
                   f"{retry}\r\n").encode("ascii") + body)
    except OSError:
        pass
    finally:
        sock.close()


class BoundedHTTPServer(http.server.ThreadingHTTPServer):
    """One header gate, at most 44 request workers, no unbounded worker queue."""
    request_queue_size = 128

    def handle_error(self, request, client_address):
        if self._closing or isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError)):
            return  # ordinary peer disconnect or deliberate shutdown
        super().handle_error(request, client_address)

    def __init__(self, *args, **kwargs):
        self._gate_lock = threading.Lock()
        self._pending = {}
        self._active = set()
        self._closing = False
        self._slots = {name: threading.BoundedSemaphore(count) for name, count in LANES.items()}
        self._wake_read, self._wake_write = socket.socketpair()
        self._wake_read.setblocking(False)
        self._wake_write.setblocking(False)
        try:
            super().__init__(*args, **kwargs)
        except BaseException:
            self._wake_read.close()
            self._wake_write.close()
            raise
        self._gate = threading.Thread(target=self._headers, name="http-headers", daemon=True)
        self._gate.start()

    def _wake(self):
        try:
            self._wake_write.send(b"x")
        except OSError:
            pass

    def process_request(self, request, address):
        request.setblocking(False)
        with self._gate_lock:
            if self._closing:
                request.close()
                return
            if len(self._pending) >= PENDING_CONNECTIONS:
                # Discard the oldest incomplete request, allowing a new Stop or
                # health request to reach the parser during an idle-client burst.
                oldest = next(iter(self._pending))
                self._pending.pop(oldest)
                _refuse(oldest, 503)
            self._pending[request] = (address, bytearray(), time.monotonic() + HEADER_SECONDS)
        self._wake()

    def _headers(self):
        while True:
            with self._gate_lock:
                if self._closing:
                    return
                pending = dict(self._pending)
            try:
                ready, _, _ = select.select([self._wake_read, *pending], [], [], 0.1)
            except (OSError, ValueError):
                continue  # an evicted/closed socket was in the snapshot
            if self._wake_read in ready:
                try:
                    self._wake_read.recv(4096)
                except OSError:
                    pass
            for sock, (address, prefix, deadline) in pending.items():
                status = None
                complete = False
                if time.monotonic() >= deadline:
                    status = 408
                elif sock in ready:
                    try:
                        chunk = sock.recv(min(8192, HEADER_BYTES + 1 - len(prefix)))
                        if not chunk:
                            status = 400
                        prefix.extend(chunk)
                        end = prefix.find(b"\r\n\r\n")
                        complete = end >= 0 and end + 4 <= HEADER_BYTES
                        if not complete and len(prefix) >= HEADER_BYTES:
                            status = 431
                    except BlockingIOError:
                        continue
                    except OSError:
                        status = 400
                if not complete and status is None:
                    continue
                with self._gate_lock:
                    if self._pending.pop(sock, None) is None:
                        continue
                if status:
                    _refuse(sock, status)
                else:
                    self._dispatch(sock, address, prefix)

    def _dispatch(self, sock, address, prefix):
        try:
            method, target, _ = bytes(prefix).split(b"\r\n", 1)[0].decode("iso-8859-1").split()
            route = (method, urlsplit(target).path)
        except ValueError:
            _refuse(sock, 400)
            return
        lane = "control" if route in CONTROL else "stream" if route in STREAMS else "ordinary"
        slot = self._slots[lane]
        if not slot.acquire(blocking=False):
            _refuse(sock, 503)
            return
        connection = _Connection(sock, prefix)
        with self._gate_lock:
            if self._closing:
                slot.release()
                sock.close()
                return
            self._active.add(connection)
        def run():
            try:
                self.process_request_thread(connection, address)
            finally:
                with self._gate_lock:
                    self._active.discard(connection)
                slot.release()
        try:
            threading.Thread(target=run, name=f"http-{lane}", daemon=True).start()
        except BaseException:
            with self._gate_lock:
                self._active.discard(connection)
            slot.release()
            sock.close()
            raise

    def server_close(self):
        with self._gate_lock:
            self._closing = True
            connections = [*self._pending, *self._active]
            self._pending.clear()
        self._wake()
        for connection in connections:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            connection.close()
        gate = getattr(self, "_gate", None)
        if gate is not None and gate is not threading.current_thread():
            gate.join(timeout=2)
        self._wake_read.close()
        self._wake_write.close()
        super().server_close()
