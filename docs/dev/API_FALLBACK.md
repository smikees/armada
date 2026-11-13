# Claude API fallback

Owner decision, 13 November 2026: provider-enforced spending limits replace the
mandatory Windows worker and local authoritative budget for newly saved fallback
setups. Same-user code can access owner credentials; the owner accepted this tradeoff.
The worker remains an explicit optional boundary under App Settings → Advanced.
Its existing opt-in is retained even if its manifest is subsequently lost.

## Owner setup

App Settings → Claude → **Set up API usage fallback** opens one modal:

1. Check credit in the Claude Console organization linked to the subscription.
2. Set the organization spending limit. Keep auto-reload off when using existing
   credit only; a monthly limit is not itself a prepaid balance.
3. Create a workspace-scoped API key, paste it, optionally use the free **Test key**
   authentication check, and save.

No second CLI login, administrator prompt or worker setup is required. Do not put
keys in chats, realms, exports or test fixtures. DPAPI protects saved keys on Windows
outside realms; metadata APIs and pages never return their values.

An agent's Configure → Run limits & fallback opens the same modal with engine-key,
separate-key and off choices. An independent agent budget requires a **Console
workspace with a spend limit and a key scoped to that workspace**. Shared keys share
their provider budget. A selected missing agent key never silently uses the engine
key. The engine switch can disable all new fallback attempts, including agent keys.
Only Claude is shipped; namespaces and key selection are provider-specific.

## Execution contract

Subscription CLI authentication remains first. Only an owner-approved, sealed
critical job may enter the new API mode when its subscription has a confirmed
session/hourly/weekly refusal or a fresh exhausted reading. Normal chats, Inbox
tasks and noncritical jobs remain on the plan. Explicit wait/fail overrides remain.
An expired refusal or a newer reading with room restores the subscription lane.

At most one API attempt belongs to the invocation. A mid-run refusal may replay
only after the existing retry-safety test passes. Unsafe or uncertain effects stop
and notify; cross-authentication session resume is not assumed. Subscription-only
connector grants block API fallback and retain their configured wait/fail behavior.
The provider, model, owner timeout, Stop and directly registered MCP grants remain.

The host proxy keeps the real key out of the CLI environment and forwards only
Messages/token-count requests to the fixed Anthropic origin, without redirects.
The CLI gets a temporary invocation token. Provider-managed mode does not use the
legacy local price-bound admission check: new models/features are not blocked by
stale Armada price tables. Optional owner per-run CLI ceilings remain supported.
Recognized credit/spend refusals latch the proxy closed for the invocation, so CLI
retries or model fallback cannot send more upstream requests. API failures are final
for the job's automatic retry series.

Console is the spending authority, including other apps. Armada does not claim to
read the provider's cap, promotional balance, expiry or all account spending from a
workspace key. Its header/preamble/usage file show **reported Armada costs**, with
missing costs and active runs explicit. Damaged advisory tracking does not impose a
fictitious provider limit. Damaged owner policy disables API fallback without
disabling healthy subscription calls. There is no promised zero-dollar overshoot
bound for concurrent requests already in flight at the provider.

New policy is `api-fallback.json`; scoped encrypted keys remain in
`provider-secrets.json`; advisory costs are `claude-fallback-usage.json`, all outside
realms. Existing legacy cap/reserve accounting remains until the owner explicitly
saves the new modal; no live job, key or worker state is rewritten by publication.

## Verification

`tests/test_api_fallback.py` covers eligibility, key scopes, approval changes,
replay/connector guards, final refusals, unknown accounting, corruption, free key
checks, redaction and actual runner receipts. Worker regressions retain explicit
opt-in failure behavior. `tools/owner_workflow_probe.py` covers native modal
operation, cancellation, failed saves, free tests, key clearing, agent overrides,
focus and light/dark layouts at 150% scaling.

`tools/api_fallback_probe.py --output build/api-fallback-cli.json` uses the installed
Claude CLI, an isolated profile, synthetic credentials and a local fake Messages
provider. It checks successful critical-job fallback, cost receipts, no real key in
the CLI environment and the Console-cap stop, including CLI retries. No paid
request, owner credential, business tool or temporary Windows account is used.
This is protocol validation, not live redemption of promotional credit.

Provider references checked 13 November 2026:

- [Workspace budgets and scoped keys](https://platform.claude.com/docs/en/manage-claude/workspaces)
- [API spend limits](https://platform.claude.com/docs/en/api/rate-limits)
- [Monthly API credits](https://support.claude.com/en/articles/17154008-monthly-api-credits-for-max-ultra-and-team-plans)

The monthly-credit FAQ includes self-run noninteractive Claude Code/Agent SDK use
with the linked organization's API key; interactive first-party launches differ.
Individual credit eligibility and expiry remain visible in Console.
