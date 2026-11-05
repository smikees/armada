# `armada/http_limits.py`

Bound local HTTP input before allocating request workers.

Incomplete headers share one socket gate. Completed requests use separate bounded
lanes so streams and ordinary work cannot consume the control lane. Every lane
still goes through the normal Host, origin, authentication and realm checks.

### class `RequestError`

—

- `RequestError.__init__(self, status, message)` — —

### `read_body(handler)`

Strict framing and JSON; invalid input must never become an empty mutation.

### class `_Input`

—

- `_Input.__init__(self, connection)` — —
- `_Input.readable(self)` — —
- `_Input.readinto(self, target)` — —

### class `_Connection`

—

- `_Connection.__init__(self, sock, prefix, server)` — —
- `_Connection.makefile(self, mode, buffering=-1)` — —
- `_Connection.sendall(self, data)` — —
- `_Connection.close(self)` — —
- `_Connection.__getattr__(self, name)` — —

### `defer_refusal(connection)`

Preserve a handler's error response while the client finishes sending input.

### `_send_refusal(sock, status)`

—

### class `BoundedHTTPServer`

One header gate, at most 44 request workers, no unbounded worker queue.

- `BoundedHTTPServer.handle_error(self, request, client_address)` — —
- `BoundedHTTPServer.__init__(self, *args, **kwargs)` — —
- `BoundedHTTPServer._wake(self)` — —
- `BoundedHTTPServer.process_request(self, request, address)` — —
- `BoundedHTTPServer._refuse(self, sock, status)` — —
- `BoundedHTTPServer._drain_refusal(self, sock)` — —
- `BoundedHTTPServer._headers(self)` — —
- `BoundedHTTPServer._dispatch(self, sock, address, prefix)` — —
- `BoundedHTTPServer.server_close(self)` — —
