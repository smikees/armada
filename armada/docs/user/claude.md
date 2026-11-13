# Claude models

Use Claude on its own or alongside Codex and Gemini. Your agents keep their roles,
memories, goals and conversations when you change their model.

1. In setup or **Settings → App → Engines → Claude**, install or update Claude Code.
2. Choose **Sign in** and complete the provider's login. ARMADA reuses that saved login.
3. Select a Claude model for the realm, an agent or a job. Inherited settings follow
   the realm default; explicit job settings take precedence.

Models and subscription details come from the connected account. ARMADA does not
require either of the other engines. Provider account eligibility and quotas apply.

Configure and authorize Claude connectors, then grant the capabilities to the agent.
Claude plugins and connector sessions are specific to Claude; connecting them does
not authorize Codex or Gemini. See [Capabilities](capabilities.md) and
[Staying safe](safety.md) for access controls and their limits.

The Overview header displays reported account limits. Readings are cached for five
minutes; unavailable values are marked as unknown. Usage and API-equivalent figures
use reported accounting and do not represent a subscription charge.


## API credit at the subscription limit

In **Settings → App → Claude → Set up API usage fallback**, follow the dialog's
three steps: check Console credit, set its spending limit, and save a workspace API
key. **Test key** checks sign-in without a paid model call or saving the key. Your
normal Claude CLI sign-in remains the subscription lane; no second account is needed.

Only approved **critical jobs** use the new fallback at a confirmed session or weekly
limit. Explicit wait/fail choices still apply. A mid-run refusal can restart only
when replay is safe; otherwise ARMADA stops and explains why. After a subscription
reset, the next job uses the plan again. A Console credit or spend-limit refusal
stops further API calls for that invocation.

**Claude Console enforces the budget**, including other apps. Keep auto-reload off
to use existing credit only. Promotional credit eligibility and expiry are shown
there. Armada reports its own API costs, not your remaining credit. For a separate
agent budget, create a Console workspace with its own spend limit and use its
workspace-scoped key in that agent's **Configure → Run limits & fallback** dialog.
Shared keys share their budget. Keys are encrypted outside realms on Windows; code
running as your Windows account can still access them. The optional isolated worker
under App Settings → Advanced offers a stronger boundary with separate sign-ins.

A claude.ai connector cannot follow a run onto the key. ARMADA waits or fails with its
name and reason; register a direct MCP connection when the service supports it.
Fallback never silently removes a required connector. Previously configured local
API caps and reserve controls remain until you explicitly save the new setup dialog.

Jobs and Inbox tasks have no default wall-clock deadline. Optional job and realm
ceilings still apply, and inactive jobs stop with a notification. Usage readings in
`usage-last.json` and each run's context show the last known limits and their age.
