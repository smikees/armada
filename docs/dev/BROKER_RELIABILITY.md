# Connector outages and dependent jobs

Implementation and account research, 13 November 2026. User approved coordinator-triggered
runs with the proposed opt-in/cap guards and accepted the same-user Windows
credential boundary for command jobs, as for API fallback.

## Boundaries

Heartbeats and prerequisite waits make no model requests. Waiting is durable and
holds no provider ticket or invocation lock. Approval seals cover dependencies,
windows, required connectors, retry delays, command text/environment, fallback
targets, secret names and coordinator controls. Existing explicit run timeouts
remain unchanged. Owner Run now bypasses prerequisite waiting with a warning.

The runtime check must distinguish server reachability, provider inventory and
callable tool inventory. HTTP 401 means the server answered, not that a broker
read can succeed. An Anthropic incident is correlated evidence, not proof that it
caused a particular connector failure. A missing claude.ai inventory is never an
empty successful prerequisite check. No credentials belong in health history.

## Delivery work

- [x] Complete and test persistent heartbeat scheduling, bounded probes, state
  notifications, agent-readable latest state and 30-day availability.
- [x] Complete prerequisite scheduler integration, restart/update behavior,
  dependency chains/manual results, deadline failures and run-anyway context.
- [x] Add owner Jobs controls and approval summaries, watch controls on
  Capabilities, live waiting status in Jobs/calendar/Activity.
- [x] Resolve bounded connector status queries for UI and setup tools, including
  per-provider terminal errors and absent granted connectors in run evidence.
- [x] Complete command secret Settings modal, injection/redaction and tests.
- [x] Implement approved fallback-job dispatch and dependency satisfaction.
- [x] Implement coordinator start tool, sealed opt-in, per-job/per-realm daily
  caps, overlap protection, immutable approved inputs, audit and notifications.
- [x] Research and document broker routes, source-enforced read-only limits,
  session coexistence, token refresh, coverage and owner actions. No account
  changes until a route meets the user's stated conditions.
- [x] Update in-app proposal contract, reference and release notes; run focused,
  full, native UI and lifecycle validation. Do not mutate the live trading realm
  or retire its existing probe until a replacement is configured and accepted.

## Release note draft (not published)

Jobs can wait for required connectors and fresh successful results from other
jobs, inside an owner-approved start window. Connector monitoring makes no model
calls, records outages and recovery, and supplies agent-readable readings.
Waiting work appears in Jobs and Activity. Custom retry delays and approved
fallback jobs preserve replay safeguards. A fallback also waits for its own
prerequisites before acquiring execution capacity; a prerequisite regression
while queued stops it before execution and reports the reason.

Coordinators can start only jobs explicitly opted in by the owner, with daily
caps and a reason recorded in history. Permissions and sealed inputs are checked
again after queueing. Interrupted requests are shown as interrupted and are not
automatically replayed. Command credentials use Windows encryption outside realm
folders and are supplied only to approved command processes, within the accepted
same-user account boundary. Direct broker authentication, read-only enforcement,
token refresh and a gateway supervisor are not claimed implemented or tested.

## Research findings requiring care

IBKR's official FAQ currently describes the public MCP endpoint at
`https://api.ibkr.com/v1/api/mcp-public`, compatibility with generic MCP clients,
Review & Approve instructions, and autonomous trading modes. It also says linking
a different AI platform disconnects the previous one. Therefore a second live
registration cannot be assumed to coexist with the daily claude.ai connector.
No source-enforced read-only consent has yet been verified on the owner's account.

Sources checked 13 November 2026:

- [IBKR connection FAQ](https://www.interactivebrokers.com/support/faq/content/connecting-ibkr-account-ai-platform-1437187133)
- [IBKR public MCP announcement](https://us1.interactivebrokers.com/en/general/about/mediaRelations/7-28-26.php)
- [IBKR AI integration](https://www.interactivebrokers.com/en/trading/ai-integrations.php)
- [Trading sessions](https://www.interactivebrokers.com/docs/web-api/authentication/trading)

IBKR documents one brokerage session per username across platforms. Market-data
permissions belong to usernames; non-brokerage read-only Web API access excludes
the `/iserver` market-data endpoints. These limits need an owner-visible decision
before installing or signing into a gateway. A supervised service is conditional
on choosing a route that needs one; no gateway is installed by this change.

## Broker route assessment — account validation still required

| Route | Coverage and output | Read-only boundary | Owner/session work |
|---|---|---|---|
| Direct IBKR MCP | Closest candidate to today's raw MCP answers. Public generic-client support is documented, but the exact positions/orders/trades/balances/quotes/Greeks tool set and schemas must be compared on a safe test identity. | No verified source-enforced read-only OAuth scope covering every prohibited action. Review & Approve is not read-only. Do not build the reader on it yet. | New OAuth sign-in; coexistence and refresh must be tested. IBKR warns that a second AI connection replaces the previous one. The current claude.ai registration was not changed. |
| IB Gateway / TWS socket API | A different data interface, requiring a translation layer owned by Marcus. API market-data documentation includes option Greeks. Full capture equivalence, especially open orders while read-only, remains untested. | Keep Read-Only API enabled. Official guidance says it blocks API orders; the full place/change/cancel/alert contract still needs validation on a paper identity. Current API settings cannot be changed through the API while read-only is enabled. | Local gateway installation and interactive login. Daily auto-restart is supported; weekly manual reauthentication remains. A separate username may avoid displacing the owner's trading session, but its market-data entitlement/cost must be checked. |
| Client Portal Web API gateway | Different HTTP schemas; brokerage-session market data cannot be obtained through the outer read-only session alone. Not a drop-in replacement for raw MCP responses. | The outer read-only subset lacks required market data. No verified source restriction covering all prohibited trading/alert calls in a full session. | Local Java gateway and browser authentication, with 2FA and periodic reauthentication. Another session on the same username can displace manual access. |
| Flex Web Service | Reporting backup for books/ledger, not a live quotes/option-chain replacement. The token retrieves configured statement queries. | Reporting-only service; does not supply the intraday broker tool suite. | Owner creates a query and token. Token validity is configurable from six hours to one year; optional IP restrictions. No gateway or ongoing trading login required. |

Additional primary sources:

- [TWS API installation/read-only behavior](https://www.interactivebrokers.com/campus/trading-lessons/installing-configuring-tws-for-the-api/?retakeFinal=1)
- [TWS configuration API requires manually disabling read-only](https://www.interactivebrokers.com/docs/tws-api/doc/setting-management)
- [TWS streaming data and option computations](https://www.interactivebrokers.com/docs/tws-api/doc/md/streaming-data)
- [Gateway daily restart and weekly reauthentication](https://www.interactivebrokers.com/docs/excel/rtd/downloads/best-practices-tws-ib-gateway-configuration/daily-weekly-reauthentication)
- [Web API session and username market-data requirements](https://www.interactivebrokers.com/campus/ibkr-api-page/webapi-doc/)
- [Client Portal gateway authentication](https://www.interactivebrokers.com/campus/trading-lessons/launching-and-authenticating-the-gateway/)
- [Flex token configuration and validity](https://www.interactivebrokers.com/docs/web-api/flex-web-service/client-portal-configuration/enable-and-create-access-token)

A direct MCP client can perform protocol initialization, tools/list and tools/call
without a language model. That establishes protocol feasibility only; IBKR OAuth,
token refresh, read-only consent and this account's tools have not been tested.
Successful direct registration should make the endpoint independent of Claude's
subscription connector list, but API-lane visibility must still be tested. Use a
server name containing `Interactive_Brokers` to preserve capture matching. Never
remove the existing claude.ai registration to test this claim.

The account decision comes before a gateway supervisor or broker-specific OAuth
refresh implementation. Neither is claimed delivered here. A new process watchdog
alone cannot bypass weekly login/2FA or prove read-only permissions. No reader or
parser under the live realm's `skills/` has been edited.

## Validation and activation

Local validation completed on 13 November 2026. The pinned isolated full gate
passed **4,626 tests with 6 skips** in **920.93 seconds** on Python 3.12.10
(`build/outage-full-complete.log`). The focused feature set passed 46 tests.
Stabilization passed in **367.55 seconds**, including 280 fault tests, concurrent
soak and history performance checks, three 163-check native window cycles,
6 page-work checks and 98 owner workflows (`build/outage-stabilization.json`).
The final dedicated WebView2 journey passed 11 checks, including panel geometry;
its captured form was visually reviewed (`build/job-readiness-native-reviewed.json`
and `.png`). Generated references and the four intentional golden-page changes
were reviewed. Stabilization recorded an uncommitted development tree; these are
local implementation results, not exact-commit CI or packaged-release evidence.
No release has been published for this work and no live broker sign-in, model
call, hosts-file change or job reconfiguration was performed.

Synthetic tests cover repeated connector failure/recovery, no claim or provider
ticket during waits, fresh-check requirements, deadlines, scheduler restart,
queue withdrawal after a prerequisite regresses, manual/fallback outcomes,
dependency chains/cycles, approval tampering, coordinator caps and role spoofing,
credential environment scope and persisted-output redaction. The hidden WebView2
journey in `tools/job_readiness_probe.py` covers saving/reloading controls and both
settings modals with a synthetic secret. No real provider call or order is needed.

For the live acceptance exercise, first configure watches and approve required
connectors/windows for the selected jobs. Keep the existing probe until the native
heartbeat has produced validated readings. Use a temporary test endpoint or a
per-test proxy to simulate an outage; do not edit the machine hosts file and
interrupt live broker work. Then verify recovery, dependent starts and one notice
per transition. Retire the old probe only after that check. Broker sign-in and
read-only rejection tests need an isolated paper/test identity and markets closed.
