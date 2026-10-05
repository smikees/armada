# `armada/local_auth.py`

Per-server loopback credentials, bootstrapped through an owner-only local file.

The browser exchanges a URL fragment for an HttpOnly cookie, then removes the fragment.
Neither public health checks nor content pages disclose the credential. Browser origin
guards remain necessary: cookies are scoped to hosts, not TCP ports.

### `_private_directory()`

—

### `_path(port: int)`

—

### `headers(port: int)`

Internal clients must possess the owning user's per-server credential.

### `browser_url(url: str, destination: str='')`

—

### class `Session`

—

- `Session.__init__(self, port: int)` — —
- `Session.allows(self, headers)` — —
- `Session.close(self)` — —
