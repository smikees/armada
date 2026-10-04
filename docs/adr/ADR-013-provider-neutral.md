# ADR-013 — Provider-neutral teams

**Status: Accepted; records the current three-engine product. Supersedes ADR-001.**

## Decision

Claude Code, Codex CLI and Gemini through Antigravity CLI are independent, equal
choices. Setup requires any one authenticated engine and allows any combination.
Agent and job configuration selects the engine through its model. Neither another
provider's subscription nor a provider desktop app is a prerequisite.

## Consequences

- Provider authentication, tools, quotas and capabilities stay in adapters.
- Common UI and docs use neutral language; specific limitations remain explicit.
- Defaults consider connected providers and model metadata, falling back to provider
  defaults for unknown catalogues. Explicit choices are preserved.
- Tests cover single-provider and mixed-provider setups using synthetic realms.
