# Agent runtime controls — 0.99.141

Lane selection and critical-job admission use owner-protected usage readings.
`usage-last.json` is the credential-free realm mirror for agents; editing that file
cannot force API spending or change the authoritative reading.

Jobs and Inbox tasks run until their engine finishes or the owner presses Stop unless
`timeout` or the realm's `default_job_timeout` supplies a ceiling. Existing job files
and their limits are preserved. Command-job defaults and dry-run deadlines are unchanged.

The owner can set or clear a job limit in Jobs. Approval shows the limit, fallback
choice, connector policy, API ceiling/model and critical flag. Machine-local seals bind
these choices to the job's approved instructions. Edits by an agent invalidate the seal.
Existing time limits are sealed once when the realm opens after upgrade. New fallback
or critical fields found in an old job still need owner approval. The existing realm
default ceiling is captured in owner-controlled settings; later agent edits to realm.json
cannot remove it.

Unattended agent turns have a 30-minute inactivity watchdog and scheduled runs issue
one advisory at 60 minutes. Both are owner settings under Realm run controls. Raw engine
activity, including otherwise invisible thinking deltas, renews the watchdog; Armada
queue messages do not. Waiting for a subscription reset suspends inactivity monitoring
and releases execution capacity. Stalls record the last engine-event time and notify
through the owner's enabled channels. Terminal cleanup releases capacity, invocation
locks and retry journals. A new scheduled start overlapping an earlier invocation is
recorded as skipped, with its reason and a notification.

Claude fallback is configured in its App Settings card. Set up the isolated Windows
worker before entering a key. Setup requires elevation as the signed-in owner and
creates a non-admin account, private profile and a uniquely named, noninteractive
Windows station. A fixed keeper task holds that station open; it has no command
interface or credentials. Existing desktop/station permissions are never changed.
Worker activation rejects app, interpreter or control locations whose ancestors the
worker could replace. Use the normal per-user installation, rather than a writable
development checkout. Shared-directory ancestor ACLs are not modified.

Normal CLI, connector discovery, sign-in and local MCP/tool processes use the worker
identity. The worker needs its own provider sign-ins and MCP registrations; old owner
connections are not silently reused. Claude uses its supported native PowerShell tool.
POSIX tools can need a separate worker-compatible installation. Browser authorization
URLs use the existing validated owner flow; a worker-side pseudoconsole supports
interactive CLI sign-in without access to the owner's desktop.

Approved draft scripts retain their existing LPAC AppContainer restrictions, including
no network/children and writes confined to staged output. They run on a draft desktop
in the private station. Their separate probe verifies that they cannot decrypt owner
DPAPI data, read an existing owner credential fixture, open the owner's clipboard
station, read owner process memory or inherit an API key. No unrestricted agent code
runs with the owner identity. Agents sharing the worker account are not isolated from
one another; this boundary protects owner credentials and control files.

The key is stored outside realms with owner-bound Windows DPAPI and has no read/echo
HTTP endpoint. An invocation-local gateway keeps the real key in the trusted host;
the CLI receives only an expiring gateway token. The installed CLI must pass a
synthetic test proving its shell children do not inherit provider credentials.
`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1` provides this extra check. A missing or failed
worker setup closes execution, including when a key exists but its worker manifest
is missing. See [worker isolation](WORKER_ISOLATION.md).

The monthly cap is account-wide across this machine's realms. Its default is $100,
the cycle starts on UTC day 1, the per-run ceiling is $5, and 30% is reserved for critical
jobs. A full run ceiling is reserved atomically before launch, and passed as
`--max-budget-usd`. Real terminal API cost replaces the reservation. Unreadable cost
charges the whole ceiling; crashes retain the reservation. An unreadable or missing used ledger closes
the API lane. Outstanding reservations survive cycle boundaries. The credit display
distinguishes spent from reserved. Anthropic, rather than Armada, determines whether
the supplied Console key draws from a promotional credit or charges another balance.

A local, invocation-authenticated gateway also checks every paid request before forwarding
it. Free token counting and a conservative UTF-8 byte bound cover text input. Inline media
requires the plan because its API billing cannot be bounded here. Generous headroom, worst-case cache
and context multipliers and the requested output ceiling bound the cost against the run's
reservation. Unsupported models/features, premium tiers and provider-hosted tool fees
fail closed. Completed request usage releases unused request capacity inside the run;
incomplete responses retain the full request bound. The terminal cost releases the unused
monthly reservation at the end, checked against independently metered provider counters.
A worker cannot lower the charge by understating the CLI total; unreadable cache tiers
retain the full reservation. Anthropic pricing
changes require a release updating the verified model bounds. The gateway exposes no
arbitrary URLs, credential endpoint or redirect path. An unfinished request at CLI exit
charges the full run reservation. The Console organisation's own limit remains useful
defence against spending from other clients sharing that key.

The price bounds were checked on 11 November 2026 against Anthropic's
[pricing reference](https://platform.claude.com/docs/en/about-claude/pricing).
The [token-counting reference](https://platform.claude.com/docs/en/build-with-claude/token-counting)
documents the free counting endpoint and notes that counts are estimates.

Fallback is provider-scoped and currently enabled only for Claude. Codex and Gemini
authentication remains unchanged. Fresh exhausted usage or a recorded refusal skips
the plan attempt. Only a structured 429 plus subscription-limit wording qualifies;
generic rate limits do not. A refused attempt with tools must pass the existing job
replay test. Missing or ambiguous side-effect evidence prevents replay. `--resume`
across authentication lanes is deliberately not used. Only one API fallback is allowed
per invocation, and an API-lane failure cannot enter the job retry loop.

The owner's plan-limit policy can use the key, wait or fail, with realm, agent and job
overrides. A granted claude.ai connector blocks API fallback and uses the separate
wait-or-fail policy, with a plain explanation. Direct MCP registrations remain usable.
The CLI's own startup warning confirmed that API-key authentication disables claude.ai
connectors on the installed 2.1.319 CLI. No actual subscription or Console credit was
spent by the credential probe.

Critical jobs precede other queued work. When approved critical jobs exist for a provider,
one provider slot and one realm slot are held available by admitting fewer ordinary
runs, rather than interrupting work with possible side effects. A configured session-use
threshold defers ordinary work. Critical jobs can spend the reserved API credit.

Successful header readings and the scheduler refresh write `usage-last.json` using one
entry per engine, timestamps, plan, session/weekly resets and model buckets. The
scheduler refreshes every 25 minutes, allowing time for its tick and provider probe
within the requested 30-minute interval when providers respond. Every turn gets the
last readings and API credit in its preamble. Unavailable or old readings are stated
honestly; an outage cannot be turned into fresh data. No credentials or account IDs
belong in this file.

Run `python tools/provider_lane_probe.py --output build/provider-lane-probe.json`
to repeat the local installed-CLI check. Unit tests simulate 45 minutes of healthy
events; they do not substitute for a 45-minute production soak. Native thread-window
and release gates remain required before installation/publication.

## Interactive Brokers on both lanes

Armada already has a direct IBKR registration flow. IBKR's
[custom connector release notes](https://www.ibkrguides.com/releasenotes/connector-v1.1.5.htm)
confirm the public endpoint
`https://api.ibkr.com/v1/api/mcp-public`. In Capabilities, choose Interactive Brokers,
connect it for Claude using a direct MCP registration, complete IBKR's sign-in, and
grant that registration to the desk agent. Validate it with a read-only tool call on
each lane before switching the desk. The disabled `claude_as_...` realm entry does
not establish that a working direct registration exists. These changes do not alter
the owner's live realm or broker setup.
