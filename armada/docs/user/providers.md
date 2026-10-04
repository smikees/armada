# Engines and accounts

ARMADA works with **any one** of these engines, or any combination. You do not need
all three subscriptions or any provider's desktop app.

| Engine | CLI used by ARMADA | Setup guide |
|---|---|---|
| Claude · Anthropic | Claude Code | [Claude](claude.md) |
| Codex · OpenAI | Codex CLI | [Codex](codex.md) |
| Gemini · Google | Antigravity CLI | [Gemini](gemini.md) |

In setup or **Settings → App → Engines**, install the CLI you want, sign in through
its provider, and enable it for ARMADA. Existing CLI logins can be reused. The card
shows installation, authentication and the subscription name when the CLI reports it.
Available models, account eligibility and quotas depend on the provider.

Choose the realm's default model in **Realm settings → Model defaults**. Individual
agents and jobs can override it. Changing providers preserves roles, memories and
conversation history. New teams choose from the engines connected after setup;
an unfamiliar catalogue uses the provider's default model.

Connectors need authorization for the engine that will use them. An authorization
in one provider is not shared with another. Capability badges show availability
for each engine; unsupported tool combinations explain the missing support.

Usage bars show only what each provider reports. Missing quota or token data is
unknown, not zero. ARMADA's API-equivalent estimate is a comparison, not your bill.
