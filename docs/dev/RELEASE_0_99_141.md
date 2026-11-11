# 0.99.141 - Resilient jobs and isolated Claude API fallback

Application code: `b841171813ab4b5b79ea772a21276712939b36ec`.
Publication is pending exact-commit CI and packaged gates.

Shared main/detached bullet editing supports Shift+Enter, Tab and Shift+Tab,
including nested rendering after sending. Agent jobs and Inbox tasks have no
implicit wall-clock deadline; explicit job/realm ceilings remain. Owner controls
seal ceilings, fallback choices and critical status outside agent-writable realms.

Inactivity monitoring starts with engine attachment/events, ends before transcript
flushing, and frees the owned process tree on
a stall. Scheduled jobs have one soft-duration advisory and a recorded/notified
skip when the previous invocation still owns the job. Critical reservations cover
account-wide/provider capacity and realm capacity independently. Authoritative
usage readings stay in owner controls; credential-free realm copies remain readable
by agents and are refreshed by scheduler upkeep every 25 minutes.

Claude fallback uses a bounded invocation gateway, conservative request reservations,
independent provider-usage metering, monthly/per-run ceilings and a critical reserve.
Subscription-only connector grants prevent silent API migration. Replay after tools
requires the existing retry evidence. Generic 429 responses do not trigger fallback.

API fallback requires a separate non-admin Windows worker. Native probes verified
owner DPAPI/data denial, protected helper/interpreter code, rejected redirected ACL
grants, private staging until launch, blocked root/parent replacement, child identity
and process-tree Stop. File brokers could not read, write or create lock files in
protected owner data even when path authorization was bypassed. The installed CLI
created a draft through the real scoped MCP broker and was refused an outside write.
Both used local fake provider responses with no paid calls. Setup additionally refused a real owner-identity child and
an admitted running turn before UAC or credential creation, preventing older owner
runs from overlapping key activation. Draft scripts remain in LPAC on a private desktop; owner
clipboard-station and process-memory access were denied. Installed Claude 2.1.319
read file-based prompt/MCP inputs and scrubbed its shell environment using a fake
local provider, with no paid requests or real API key.

Real elapsed-time checks completed a scheduled job and Inbox task at 2,700 seconds
of active execution each, with no deadline. A separate explicit 600-second ceiling
stopped at 600.031 seconds of active execution. Queue time was recorded separately.

The complete native Windows local gate passed **4,455 tests with six skips**.
The final source stabilization gate passed in **246.83 seconds** and the detached
thread probe passed **102 checks**. Native draft/inspector UI checks also passed.
The queued GitHub push run created no checks and could not be cancelled or rerun;
this validation record triggers a fresh push without application-code changes.
Publication details and public hashes will be recorded after the enforced gate.

The beta continues unsigned Windows installer distribution; app updates remain
Ed25519-signed. Trusted publisher signing and clean-machine Sandbox acceptance are
not certified. No live Console credit charge, subscription-to-key resume or broker
operation was exercised. Owners must configure their worker sign-ins/API key and
configure compatible direct connectors where supported. Subscription-only grants
otherwise keep those jobs on the configured wait/fail path.
The app was not restarted and live business jobs/files were not modified. The
synthetic test account was retained at the owner's request.
