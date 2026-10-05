# Provider-aware upkeep

System-job cost (`free` / `quota`) describes possible consumption, not authentication.
`usage-keepalive` declares `provider: claude`; the Anthropic model catalogue retains its
own refresh/auth behavior. Inbox and Telegram dispatch have no fixed provider requirement.

`engine.authentication.recipient_access` uses the same `engine_for` precedence as execution:
explicit engine override, recipient model, realm model, then legacy engine configuration.
It checks Claude through `auth.status()` and Codex through `CodexEngine.auth_status()`.
No provider substitution occurs. Missing/malformed/error probe results fail closed with
`auth-unavailable`; a known signed-out state is a `signed-out` skip. These checks are only
made for pending model work and never by page rendering. Mock execution requires no login.
Auth is advisory admission: a session can expire after the check, in which case the ordinary
CLI turn outcome records the failure.

## Limits freshness (v0.99.80)

Header limits caches carry a per-server launch ID. A restart cannot replay a prior browser
session's stale result. Successful provider reads cache for five minutes; stale/unavailable
reads retry after 30 seconds. The lower Claude usage cache supports an explicit fresh read.
An expired Claude usage token requests the enabled `usage-keepalive` job with `urgent=True`:
only this job may bypass cadence, while disabled, authentication, lifecycle, admission and
uncertain-attempt gates remain enforced. A persistent account-wide lock/cooldown limits renewal
attempts to one per five minutes across realms. Claude CLI owns token rotation; ARMADA does not
write OAuth credentials. The supervised renewal has a 35-second execution deadline.

Inbox tasks are screened before authentication and claimed only after authentication.
Unavailable recipients keep their pending mail and do not advance recipient cadence.
Other recipients continue, including in mixed-provider batches. Process now has the same
admission rule. Delivery counters remain separate from task failures; the system-job summary
reports failed tasks as errors and blocked recipients explicitly, even if other tasks succeeded.

Telegram's fallback checks connection and listener ownership before polling. Both the fallback
and independent listener resolve the recipient before probing auth. Help/menu commands need no
provider. A signed-out prompt receives a sign-in/retry reply and consumes no hourly run allowance.
Telegram polling has already consumed that update: it is not queued for automatic replay, and
the owner must resend it. The existing listener heartbeat exclusion remains unchanged.

## System-job result contract

Every `run_one` result and every returned `run_due` item contains:

| Field | Meaning |
|---|---|
| `id` | Requested system-job identity, including unknown IDs |
| `status` | `ok`, `skipped`, `held`, or `error` |
| `ok` | True only for `ok` |
| `reason` | Stable code such as `completed`, `disabled`, `not-due`, `signed-out`, `auth-unavailable`, `listener-active`, `uncertain-attempt`, `invalid-result`, or `record-failed` |
| `detail` | Human-readable explanation |
| `skipped` | True for `skipped` and `held` |
| `error` | Explanation for `error`; empty for successful or skipped work |

Disabled, not-due, locked and uncertain attempts return without creating another claim.
Once admitted, completion records `status` and `reason` on both the entry and attempt, and
appends a timestamp/status history item. Provider skips therefore follow the job's normal
cadence; Run now can retry earlier. Skips neither increment nor clear the execution-failure
streak and never trigger its notification. The week strip does not count a skip as success.
Malformed or contradictory job results are errors. Failure to record a completed result
retains the existing durable claim, holding automatic replay for operator inspection.

`tests/test_provider_upkeep.py` covers the four connection combinations, mixed batches,
recovery without replay, manual inbox admission, fallback/listener routing, fail-closed probes,
keepalive isolation, and job-result/history semantics. All providers and transports are stubbed;
these tests make no paid model calls or live Telegram sends.
