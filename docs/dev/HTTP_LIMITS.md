# Local HTTP resource limits

Released in 0.99.126. M4 introduces admission before allocating a handler thread. The cockpit and
content-origin server each own one header gate and bounded worker lanes.

| Resource | Limit and behavior |
|---|---|
| Incomplete connections | 128; an arriving connection evicts the oldest incomplete one at capacity |
| Refusal delivery | At most 128 read halves retained for up to 0.5 seconds to drain unread input after sending the error; no worker allocated |
| Headers | 32 KiB, including request line; five seconds total to finish |
| Ordinary requests | 24 concurrent handlers; additional completed requests receive 503 |
| Chat/support streams | 16 concurrent handlers, separate from ordinary requests |
| Health/instance/stop/cancel | Four reserved handlers; all normal authorization checks still apply |
| JSON request body | 16 MiB; 15 seconds total from handler admission, including slow trickles |
| Response socket writes | 30 seconds per write; no total lifetime deadline on an active stream |
| Provider probes | Three shared workers, at most one in-flight observation per provider |

The gate consumes partial headers without creating a thread for each socket.
Only complete headers reach a handler. A connection carries one request; streaming
responses remain open until their operation finishes, but another request must
pass admission on another connection. Server close releases pending and active
sockets, including refusal drains. Gate refusals and handler error responses share this drain. Keeping the read half
briefly avoids Windows
discarding a refusal response with a reset when input is still unread. Refusal
delivery remains best-effort under continuous flooding or client disconnects.
Application work does not automatically replay when a connection closes.

Body framing requires a single decimal Content-Length and rejects Transfer-Encoding.
Invalid UTF-8, JSON, non-object JSON, non-JSON numeric constants and incomplete
bodies return 400; over-limit bodies return 413; deadline expiry returns 408.
These errors occur before mutation dispatch, including realm binding. An absent
or zero-length body remains an empty object for existing bodyless actions.

Provider status and the legacy authentication-status endpoint share observations,
including overlapping forced refreshes. Each engine retains its existing freshness
policy; completed observations are not given a new cache lifetime. Login/install
progress and enabled state are read when presenting the result, so disconnecting
during a refresh cannot reconnect a provider. Identical persisted observations
do not rewrite the configuration file.

These limits bound application resource consumption; they do not promise service
availability against a continuously flooding local process. A saturated control
lane can still return 503. The reserve controls server admission, not browser
connection pools or renderer responsiveness. Slow response readers can occupy their lane until a
write times out; execution admission and job cancellation remain separate controls.

Regression evidence lives in `test_http_limits.py`, `test_provider_refresh.py` and
the existing real-HTTP authentication, realm-context and content-origin suites.
Use synthetic realms only. Packaged browser and upgrade gates are still required
before release because every page now passes through this transport.
