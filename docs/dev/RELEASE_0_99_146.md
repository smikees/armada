# 0.99.146 - Claude API fallback and System jobs columns

Release validation is in progress. Publication evidence will be recorded after the
final committed source passes the release, stabilization and packaged upgrade gates.

System jobs retain their columns after filters clear inline display styles. Long
status text wraps inside its column. The new native geometry regression fails
before the fix and passes 32 checks afterward, covering filters, sorting, tab
changes, row refresh and wide/narrow scaled layouts. See [the diagnosis and tests](SYSTEM_JOBS_LAYOUT.md).

The owner accepted same-user credential access and provider-enforced spending
limits. Claude has a compact App Settings setup modal; agents may inherit its key,
use an independently budgeted Console workspace key, or opt out. No mandatory
worker, elevation or second CLI login is introduced. Existing explicit worker
setups remain enforced. [Execution and setup contract](API_FALLBACK.md).

Newly saved setups permit only approved critical jobs to fall back, once per
invocation, with connector/replay guards and owner timeout/Stop preserved. Console
credit or spending-limit refusals latch the proxy closed: even when the installed
CLI retries or tries another model, it makes no further upstream request. Reported
Armada costs are advisory, not a claimed provider balance. Legacy setup choices
are preserved until the owner explicitly saves the new modal.

The installed-Claude protocol check uses a synthetic key, isolated profile and
local fake provider. Successful fallback reports a cost and API lane; Console cap
refusal stops further upstream requests. No paid request or live promotional
credit redemption is tested. The native setup dialog checks key clearing,
cancel/failure/retry flows, free key tests, agent scopes, keyboard focus and scaled
light/dark layouts. Captures were reviewed. The design detector found only seven
pre-existing global CSS warnings outside the new modal's rules.

No live key, realm, job, provider billing setting or owner app is changed by these
checks. The temporary Windows test account, its profile and tasks remain untouched.
