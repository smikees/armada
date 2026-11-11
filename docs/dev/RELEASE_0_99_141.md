# 0.99.141 - Resilient jobs and isolated Claude API fallback

Released on 11 November 2026 from `2aacc4ac27dbd94d4538c594e744de43f03fb507`.
The [GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.141)
and [website](https://armada.stamih.com/) both offer v0.99.141. Application code
last changed in `b841171813ab4b5b79ea772a21276712939b36ec`; subsequent commits
updated validation records and the release publisher only.

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

Feature-candidate elapsed-time checks completed a scheduled job and Inbox task at 2,700 seconds
of active execution each, with no deadline. A separate explicit 600-second ceiling
stopped at 600.031 seconds of active execution. Queue time was recorded separately.

The final enforced publisher passed **4,469 tests with six skips** in 805.09 seconds.
Both exact-commit Windows CI jobs passed **4,471 tests with four skips**, and the
PHP relay passed 23 assertions. GitHub push runs created no checks and could not
be cancelled or rerun. The publisher's explicit `--ci-run` path validated the same
Windows workflow, exact main commit and all three successful jobs from
[manual dispatch 43105873277](https://github.com/smikees/armada/actions/runs/43105873277).
All local, installer and upgrade gates remained mandatory, and the actual trigger
is recorded in `build/release-evidence-0.99.141.json`. An earlier candidate's
transient section-capture path check passed on retry and twelve isolated repeats;
the final CI run passed without a retry.

The unchanged application passed stabilization in **238.52 seconds** at
`e5e711de7fec8f6e9110b2c83f2f7a5f36eb74ee` and the detached thread probe passed
**102 checks**. Native draft/inspector UI checks passed **28 checks**. The final
installer passed recovery at all five interruption points, external DLL isolation,
16 WebView2 session checks, 68 tray checks, three 69-check restart runs and 86
presentation checks. Main/companion light and dark recovery captures were reviewed.
The signed upgrade from v0.99.140 passed **72 checks** against the final assets.

The public manifest signature, tag/manifest source commit, ZIP hash and all **487
package files** verified. The downloaded **23,402,583-byte** installer matched the
local build. The website's release and installer links verified after backed-up,
certificate-validated FTPS deployment. Evidence is retained in
`build/public-release-0.99.141.json`, `build/upgrade-0.99.141.json` and
`build/stabilization-20261111-215319-472723`.

Installer SHA-256: `99527c5d8d900508789ef49858f90f25817e6a9f8b5a85bb740b41cf1d85d7d2`.
Update ZIP SHA-256: `b71c83f70903d4beac51f21396d5618cd3302f4e452de2a8ef7875c88d7c7cc2`.

The beta continues unsigned Windows installer distribution; app updates remain
Ed25519-signed. Trusted publisher signing and clean-machine Sandbox acceptance are
not certified. No live Console credit charge, subscription-to-key resume or broker
operation was exercised. Owners must configure their worker sign-ins/API key and
configure compatible direct connectors where supported. Subscription-only grants
otherwise keep those jobs on the configured wait/fail path.
The conservative API gateway refuses inline media and unsupported or unbounded
billable features. See [runtime controls](RUN_CONTROLS.md) and
[worker setup](WORKER_ISOLATION.md) for the supported boundary and activation steps.
The app was not restarted and live business jobs/files were not modified. The
synthetic test account was retained at the owner's request.
