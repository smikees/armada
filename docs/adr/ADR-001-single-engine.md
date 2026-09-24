# ADR-001 — Claude is the only engine for v1

**Status:** Accepted · 2026-09-21

## Context

ARMADA runs agents through an engine seam: `matcap/engine/base.py` defines `EngineAdapter`
(`doctor()`, `run()`, optional `run_stream()`), and two adapters exist — `ClaudeEngine`, which
shells out to the Claude Code CLI (`claude -p --output-format json …`), and `MockEngine` for
tests. The seam is real, and it is thin.

Everything above it assumes Claude's stack, not "an engine": tool use and the `--tools` flags,
MCP servers as the capability transport, skills as `SKILL.md` folders Claude loads, the
subscription-limits header, the model catalogue and its refresh job, prompt caching
assumptions in how context is assembled, and the usage accounting that drives the Tokens and
API-eq KPIs. The capability model — connectors, extensions, skills, plugins — is Claude's
vocabulary. Supporting a second engine is not "add an adapter"; it is deciding what each of
those means when the engine has a different tool model, a different skill format, and no MCP.

Mihai uses Claude. The people most like him use Claude. Multi-engine is mandatory mid-term, not
now.

## Decision

Claude is the only engine for v1 and for the beta. No work is done to support another engine
before launch.

What *is* done before launch, in Phase 2 (step 2.6): an audit that lists every place the code
assumes Claude specifically, so the cost of a second engine is a priced list rather than a
guess. The audit does not fix anything.

## Consequences

- The wizard checks for the Claude CLI and a subscription (Phase 6, via `doctor()`), and says
  plainly that ARMADA needs Claude. No abstract "choose your provider" step.
- New code may keep assuming Claude, but should route through `EngineAdapter` where it already
  can — the audit will list where it doesn't.
- OpenAI is DEFERRED item D.2 in the launch plan, gated on beta users asking for it. When it
  comes, the audit is the spec. **The audit:** [`docs/dev/ENGINE_SEAM_AUDIT.md`](../dev/ENGINE_SEAM_AUDIT.md)
  (2026-09-24, v0.99.39) — eleven areas, roughly 5–7 weeks for an MCP-capable second engine,
  with the capability model as the long pole.
- We give up: users who don't have Claude. That is the population we are choosing not to serve
  at launch, on purpose.
