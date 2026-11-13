# 0.99.146 - Claude API fallback and System jobs columns

Published on 13 November 2026 from `6bba3fc42935eac6ef7640e2978b66edd23b69d0`.
The [GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.146)
and [website](https://armada.stamih.com/) both offer this version.

System jobs keep their seven columns after the shared filter hides or restores
rows. Layout now belongs to the stylesheet; long status text wraps in its own
column. The new native regression fails before the fix and passes **32 standalone
checks** afterward. It measures row/header geometry after search clearing, all
filters, sorting, tab changes and row updates across wide, standard and narrow
scaled layouts in both themes. These checks are also part of the complete owner
workflow. [Diagnosis and regression evidence](SYSTEM_JOBS_LAYOUT.md).

Claude has a compact App Settings setup modal: check Console credit, set its
spending limit, and save a workspace API key. The normal subscription CLI sign-in
remains first. Only approved critical jobs enter the new fallback mode, once per
invocation, with the existing connector/replay guards, owner timeout and Stop.
Agents can inherit the engine key, use a separate workspace key for an independent
Console budget, or opt out. [Setup and execution contract](API_FALLBACK.md).

The owner accepted same-user credential access and provider-enforced spending
limits. No mandatory worker, elevation or second CLI login is introduced. Keys
remain encrypted outside realms on Windows, and the CLI receives a temporary proxy
token. An existing explicit worker opt-in remains enforced under Advanced. Legacy
local API controls remain until the owner explicitly saves the new modal.

Console manages the authoritative budget, including calls outside Armada. Local
costs are advisory and never claim to represent remaining promotional credit.
Unknown costs, malformed timestamps and overflowing totals remain unavailable
without discarding a completed job. Known credit/spend refusals latch the proxy
closed so CLI retries or model fallback cannot send another upstream request.

The final publisher passed **4,555 tests with 6 skips** in 1101.65
seconds. [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/43453818313)
passed both Python test jobs (**4,557 tests with 4 skips** each, in 832.99 and
841.92 seconds) and relay. Final-source stabilization passed in
**407.48 seconds**, including fault injection, load,
performance, three **163-check** native thread/window cycles, page work and
**78 owner workflows**. Evidence: `build/stabilization-20261113-163309-751710`.

The freshly staged runtime separately passed **78 native owner
workflows**, including modal key clearing, cancellation, failed-save recovery,
free key checks, agent key overrides/removal, keyboard focus and 150% scaled dark
mode. The light/dark modal captures and packaged presentation-recovery captures
were reviewed. The UI detector found only seven pre-existing global CSS warnings
outside the new modal's rules.

The installed Claude CLI also passed a synthetic subscription-refusal-to-API run
and a Console cap refusal against a local fake Messages provider. No paid request,
real API key or live promotional credit redemption was used. The real key never
entered the CLI environment. Evidence: `build/api-fallback-cli.json` and
`build/owner-workflows-bundled-0.99.146.json`.

The installer passed native launcher recovery, DLL isolation, WebView2 sessions,
tray lifecycle, all restart cases and presentation recovery. The signed upgrade
from v0.99.145 passed **72 checks**. Public verification checked the
Ed25519 signature, tag/manifest commit, ZIP hash, all **499
packaged files**, installer hash and website links.
The **23,445,659-byte** installer has SHA-256
`032d71a90f6b7256a93cb4ba3c0af5814d7d7d255140e47ae9a7467cec9c5efb`; the update ZIP has SHA-256
`785fb69af19190ad0698af0e3ca5e24b3ca3e4b4f6b62935671aa003eddef2a1`.
Evidence: `build/release-evidence-0.99.146.json`, `build/upgrade-0.99.146.json`
and `build/public-release-0.99.146.json`.

This continues the owner-authorized unsigned maintenance beta distribution.
Trusted Windows publisher signing and clean-machine Sandbox acceptance remain
unverified. Hardware KVM/mixed-DPI removal and the previously documented snapshot
path-resolution race remain limitations from earlier releases. The owner app was
not installed or restarted; live realms, jobs, keys and provider billing settings
were not changed. The temporary Windows test account, profile and tasks remain
untouched.
