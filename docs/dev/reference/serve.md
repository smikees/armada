# `armada/serve.py`

`armada serve` — the interactive local app (SPEC §13).

A real, clickable cockpit served on 127.0.0.1: browse agents and jobs, read each job's actual
prompt, **run** a job (mock or the live engine) and watch the output, ask "what's due now", and
one-click **Update & Restart** (git pull + hot re-exec). stdlib-only, local-only, no deps — the
engine underneath is the same runner/scheduler the CLI uses. Later this same UI gets wrapped in a
native window; today it's the browser reaching http://127.0.0.1:<port>.

### class `Handler`

—

- `Handler._send(self, code, body, ctype='text/html; charset=utf-8', cache: str='')` — —
- `Handler._json(self, code, obj)` — —
- `Handler._query(self)` — —
- `Handler._body(self)` — —
- `Handler._same_origin(self)` — CSRF guard: a local server is reachable by any page in the browser. Block a mutating request whose Origin doesn't match our Host. Requests with no Origin (curl, the app's own tooling, non-browser clients) have no cross-site vector, so they pass.
- `Handler._host_ok(self)` — —
- `Handler._refuse_host(self)` — —
- `Handler.log_message(self, *args)` — —
- `Handler._cross_site(self)` — —
- `Handler.do_GET(self)` — —
- `Handler._route_welcome_get(self, path: str)` — —
- `Handler._route_welcome_post(self, path: str)` — —
- `Handler._untrusted(self, path: str)` — Is this request for content ARMADA didn't write (5.8a)? Section pages always; a thread attachment only when it's a type that runs as a document (HTML, SVG, …).
- `Handler._route_get(self)` — —
- `Handler._err_page(self, e, bare: bool=False)` — —
- `Handler._dark(self)` — Whether to render this page dark.
- `Handler.do_POST(self)` — —
- `Handler._route_post(self)` — —
- `Handler._static(self, path: str)` — —
- `Handler._git_check(self)` — Fetch and report whether the local checkout is behind its upstream.
- `Handler._git_pull(self)` — —
- `Handler._restart(self)` — —
- `Handler.log_message(self, *a)` — —

### `_say(msg: str)`

print() that survives having no console.

### `_launch_mode()`

How this process was started: 'app' (native window) or 'serve' (headless).

### `_init_logging(realm: str)`

Log to stderr and to ~/.armada/logs/armada.log (outside the versioned realm) so swallowed handler errors are visible during daily use and the stress test.

### class `_Server`

The cockpit's HTTP server.


### `port_owner(port: int=8756)`

True if something is already listening on the loopback port.

### class `ContentHandler`

The content-only server (5.8a): the untrusted pages and nothing else — no API, no POST.

- `ContentHandler._route_get(self)` — —
- `ContentHandler.do_POST(self)` — —

### `_content_loop(httpd)`

—

### `start_content_server(port: int)`

Bind the content server on `port` (the app's port + 1), or any free port if that one is still held — Update & Restart hands ports over, and for a moment the old process may keep it. Returns the port bound, or None if nothing could be (the app then sandboxes that content itself).

### `_serve_until_done(httpd)`

serve_forever(), except that a restart in progress is not a failure and not an exit: the socket was closed on purpose, and this thread waits for the re-exec to replace the process.

### `serve(realm: str, port: int=8756)`

—
