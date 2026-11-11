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

In **Settings → App → Claude → API credit & fallback**, set up the Windows worker,
sign in to Claude for that account, and enter your Anthropic Console API key. The key
stays outside realms and agent processes. Worker setup needs administrator consent
from the signed-in owner; using a different administrator account is not supported.

Choose use the key, wait for reset, or fail. Realm, agent and job controls can override
the default. The monthly cap defaults to $100, with a $5 per-run ceiling and a 30%
reserve for critical jobs. The API lane closes at the cap. Missing cost data charges
the full reserved ceiling. The header shows spent credit and warnings arrive through
your enabled notification channels. Anthropic decides whether the key draws on a
promotional credit or another Console balance.

A claude.ai connector cannot follow a run onto the key. ARMADA waits or fails with its
name and reason; register a direct MCP connection when the service supports it. Inline
images and documents are refused by the API lane because their cost cannot be bounded
safely here. Use the subscription for those inputs. Text and compatible directly
registered tools can use the key.

Jobs and Inbox tasks have no default wall-clock deadline. Optional job and realm
ceilings still apply, and inactive jobs stop with a notification. Usage readings in
`usage-last.json` and each run's context show the last known limits and their age.
