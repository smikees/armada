# ARMADA roadmap and release status

The maintainer approves acceptance milestones. Implementation and passing tests
alone do not complete a product acceptance gate.

## Where things stand

The Windows beta supports Claude Code, Codex CLI and Gemini through Antigravity CLI.
Users may connect any one engine or any combination. Threads, jobs, model selection
and connector checks share provider-neutral application contracts; adapter limitations
and differences in telemetry remain explicit.

The current release is recorded in the [README](../README.md),
[changelog](../armada/webui/changelog.py) and [GitHub releases](https://github.com/smikees/armada/releases).
Version **0.99.93** adds draft-only job tests with independent model selection, Stop,
temporary artifacts and seven-day default retention. Inspector agents have owner-approved,
scoped tools to test any realm job and read recorded artifacts without changing production.
Model tests use saved inputs; script tests require explicit draft-only commands.
The published release passed 3,370 isolated tests, exact-source Windows CI, 30 native
Jobs browser checks and 63 packaged upgrade checks. Actual scoped-tool calls from all
three CLIs and the branded embedded runtime verified draft writes and production-write
refusal. Fresh public assets are verified; 0.99.93 is staged in the running 0.99.92 app
for the owner's normal restart.
[Verification](dev/RELEASE_0_99_93.md) records boundaries, validation and publication evidence.
The canonical detached-conversation rendering and cancellation fixes from 0.99.92 remain in place.
The job, capture and recovery work from earlier releases remains in place.
Clean-Sandbox GUI acceptance remains open.

## Implemented foundations

- Independent Windows desktop, tray lifecycle and authenticated local server.
- Portable realms, templates, agents, goals, conversations and visible context.
- Three-engine setup and connected-provider model defaults.
- Memories, artifacts, capabilities and an agent task inbox.
- Scheduling across realms, bounded retries and structured results.
- Recoverable writes, durable scheduler claims and signed package updates.
- Documentation, Alexander assistance and issue reporting.

## Current reliability work

- Account-wide single-instance ownership and existing-window activation.
- Update progress based on actual work rather than scheduler existence.
- Path-safe Windows restarts and isolated native lifecycle tests.

## Acceptance still required

- Clean-machine installation and setup, including WebView2 prerequisites.
- Trusted Windows publisher signing if a suitable distribution route is adopted.
- End-to-end accessibility and setup review across display configurations.
- Wider invited-beta feedback and resolution of reproducible defects.

The unsigned beta can be blocked by Windows Application Control. Local checks are
not clean-machine acceptance, and update signatures are not publisher signatures.
See [release boundaries](dev/RELEASING.md#release-boundaries).

## Future work

Council planning, further engines, platform support and template distribution are
separate product decisions, not prerequisites for any currently supported provider.

## Contributor references

[Specification](../SPEC.md) · [Architecture](dev/ARCHITECTURE.md) · [Schema](dev/SCHEMA.md) ·
[Provider onboarding](dev/PROVIDER_ONBOARDING.md) · [Releasing](dev/RELEASING.md) · [ADRs](adr/README.md).
