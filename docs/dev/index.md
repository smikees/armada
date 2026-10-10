# ARMADA developer docs

What to read for the job in front of you. Start with the architecture if you've never touched the
code; after that, go straight to the row that matches the task.

| You're about to… | Read |
|---|---|
| Understand how the app fits together | [ARCHITECTURE.md](ARCHITECTURE.md) — processes, module map, seams, the nine invariants |
| Change anything a realm stores on disk | [SCHEMA.md](SCHEMA.md) — the layout and how format migrations work |
| Change a shared file or investigate a lock/state error | [PERSISTENCE.md](PERSISTENCE.md) — exclusive mutations, schema guards and recovery |
| Change request routing, realm switching or cancellation | [REQUEST_CONTEXT.md](REQUEST_CONTEXT.md) — immutable destinations, stale-page rejection and bound content |
| Change CLI execution, deadlines or terminal results | [PROCESS_LIFECYCLE.md](PROCESS_LIFECYCLE.md) — process ownership, provider parsing and failure persistence |
| Change turn coordination or provider requirements | [EXECUTION_CONTRACTS.md](EXECUTION_CONTRACTS.md) — typed requests/events, ownership, validation and unknown accounting |
| Change how agents write memory | [MEMORY_BOUNDARIES.md](MEMORY_BOUNDARIES.md) — provider file-tool restrictions, observations and coverage limits |
| Touch the engine, or anything that talks to Claude | [ENGINE_SEAM_AUDIT.md](ENGINE_SEAM_AUDIT.md) — what assumes Claude, and the three rules for new code |
| Work on model providers or Codex | [CODEX_INTEGRATION.md](CODEX_INTEGRATION.md) — routing, capabilities, CLI protocol and verification |
| Work on the Google engine | [GEMINI_INTEGRATION.md](GEMINI_INTEGRATION.md) — CLI execution, scoped tools, authentication and accounting |
| Change provider setup or Alexander preferences | [PROVIDER_ONBOARDING.md](PROVIDER_ONBOARDING.md) — browser login, App connections, model choices and acceptance |
| Change background provider admission or system-job results | [PROVIDER_UPKEEP.md](PROVIDER_UPKEEP.md) — recipient auth, pending work, Telegram and skip/error semantics |
| Change capabilities, connectors or which engines can use them | [CAPABILITIES_UPGRADE.md](CAPABILITIES_UPGRADE.md) — engine reach, one engine at a time, the v4 migration |
| Add something users can extend without code | [EXTENSION_POINTS.md](EXTENSION_POINTS.md) — the add-on contract |
| Draw anything | [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md), then [DESIGN_TOKENS.md](DESIGN_TOKENS.md) |
| Work the UI polish backlog | [UI_AUDIT.md](UI_AUDIT.md); if you're the Haiku agent, [HAIKU_AGENT.md](HAIKU_AGENT.md) first |
| Touch anything security-relevant (routes, files, what agents can reach, Telegram) | [THREAT_MODEL.md](THREAT_MODEL.md) |
| Run or write tests; regold a page | [TESTING.md](TESTING.md) |
| Ship a version | [RELEASING.md](RELEASING.md) |
| Write code, a changelog entry or a commit message | [CONVENTIONS.md](CONVENTIONS.md) |
| Look up a module or function | [reference/](reference/index.md) — generated from the docstrings |

Decisions that are settled live in [`../adr/`](../adr/README.md); what's being worked on, and in
which order, in [`../LAUNCH_PLAN.md`](../LAUNCH_PLAN.md).

Historical, kept for the reasoning: [CODE_REVIEW_2026-09-07.md](CODE_REVIEW_2026-09-07.md) (the
review Phase 2 finished) and [VOICE_SHELVED.md](VOICE_SHELVED.md) (read-aloud, built and shelved).

The user-facing docs — what the app shows at `/docs` — are in [`armada/docs/user/`](../../armada/docs/user/index.md) — inside the package, so installed copies have them.
