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
Version **0.99.90** polishes detached thread windows with a wider Windows-style shadow,
a seamless frame edge, a lower avatar profile, subtle header elevation and balanced close-button
spacing. [Verification](dev/RELEASE_0_99_90.md) records the visual reference comparison and
native checks. The detached conversation controls from [0.99.89](dev/RELEASE_0_99_89.md),
capture and recovery work from [0.99.88](dev/RELEASE_0_99_88.md), and scheduler supervision
from [0.99.87](dev/RELEASE_0_99_87.md) remain in place.
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
