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
Version **0.99.102** fixes the Settings font sample, makes both font menus equally readable, and
introduces a saved Default size that Ctrl+0 restores independently of shortcut adjustments.
The version row has improved alignment and spacing. [Verification](dev/RELEASE_0_99_102.md)
records the scope and publication checks; owner acceptance milestones remain open.
Published with 3,602 tests passing (5 skipped), both exact-source Windows CI configurations,
5 recovery checks, 16 multi-window checks and 63 packaged upgrade checks. Public downloads,
the update signature and all 341 packaged source files are verified. The website is live with
matching 0.99.102 links and a verified installer download. The owner's app was not restarted.

Version **0.99.101** puts every way to add a capability on the Add a capability tab: engine connectors
(Gmail, Google Drive…) are search results with Add for Claude and Add for Codex, and an MCP address, Claude
import, Bring a link and the engines’ own directories sit below the results. Connectors set up in Claude are
Claude only unless portable; the User tab filters are on two lines; font choices preview in their own face.
[Verification](dev/RELEASE_0_99_101.md).

Version **0.99.100** arranges capabilities by engine reach: Any engine, Claude only, Codex only and
Gemini only, with a section switcher, Works-with strips and per-engine sign-in chips only where a
capability can work. One-engine-at-a-time services (Interactive Brokers, or any the owner marks) carry a
current engine, a previewed Move and enforcement in the execution policy. Model pickers show what an agent
keeps on the chosen engine; runs name withheld capabilities to the agent. Provider-hosted connectors are
added per engine, and realm format v4 splits rows that 0.99.99 linked to two services.
[Implementation plan](dev/CAPABILITIES_UPGRADE.md) · [verification](dev/RELEASE_0_99_100.md).

Version **0.99.99** adds service-first connector discovery, independent engine bindings and
native Codex app admission. Account labels stay explicitly unverified, unlinking is scoped to
one realm/engine, and model switches prompt connector review. The release also updates the
public website's version and installer links. [Verification](dev/RELEASE_0_99_99.md) records
the acceptance boundary and publication checks; owner milestones remain open.
Publication passed 3,555 isolated tests (5 skipped), both exact-source Windows CI configurations,
5 native recovery checks, 16 multi-window checks and 63 packaged upgrade checks. All public
assets, the signed manifest and 338 packaged source files are verified. The website is live
with matching 0.99.99 links and a verified installer download; the owner's app was not restarted.

Version **0.99.98** fixes connector sign-in feedback and configuration copying.
Google Drive in Codex explains its required client setup, CLI outcomes remain visible and
clipboard controls provide real templates and a fallback. [Verification](dev/RELEASE_0_99_98.md)
records focused tests and actual CLI/browser checks. The published release passed 3,505 isolated
tests, both exact-source Windows CI configurations, 5 native recovery checks, 16 multi-window
session checks and 63 packaged upgrade checks. Fresh public assets, exact source and the update
signature are verified. The running owner app was not restarted.

Version **0.99.97** adds independent provider connection status and actions for connectors,
CLI-safe grant identities, operational job warnings and useful Claude quota/refusal errors.
The published release passed 3,485 isolated tests, both exact-source Windows CI jobs,
5 native recovery checks, 16 multi-window checks and 63 packaged upgrade checks. Fresh public
assets and the update signature are verified. The original skill review succeeded after its
provider quota reset. [Publication evidence](dev/RELEASE_0_99_97.md). Existing grants, runtime
compatibility and provider defaults remain intact. The running owner app was not restarted.

Version **0.99.96** adds inspector writes to the running job's approved output
folders, bounded host-managed owner messages with job-history receipts, optional
unpacked anonymous comparisons and dismissible new-version ribbons. Inspector
shell/web/live connector and production-change restrictions remain in force.
The [technical design](dev/DRAFT_REVIEW_ARCHITECTURE.md) documents the extensions
and a verified Windows skill-script exit fix found by the release gate.
The published release passed 3,437 isolated tests,
both exact-source Windows CI jobs, 56 native Jobs/update checks and 63 packaged
upgrade checks. Actual Claude, Codex and Gemini turns exercised approved writes,
audited owner-message attempts and refused foreign-agent writes. Public assets
are verified; 0.99.96 is staged in the running 0.99.95 app without restart.
[Publication evidence](dev/RELEASE_0_99_96.md).

Version **0.99.95** scopes inspector tools to flagged jobs, adds fingerprinted
Python/Node skill execution inside Windows draft isolation, and adds frozen-input
blind A/B comparisons with immutable score reveal and anonymous export. Inspector
metadata and dry-run effort overrides are included. Existing inspectors must mark
their review jobs. The published release passed 3,397 isolated tests, both exact-source
Windows CI jobs, 42 native Jobs/editor checks and 63 packaged upgrade checks. Actual
Claude, Codex and Gemini turns each exercised approved Python/Node scripts and a
refused production write. Fresh public assets are verified; 0.99.95 is staged in
the running 0.99.94 app for the owner's normal restart.
[Technical design](dev/DRAFT_REVIEW_ARCHITECTURE.md) and
[publication evidence](dev/RELEASE_0_99_95.md).

Version **0.99.94** aligns Dry run history with the existing Jobs disclosures,
removes its duplicate top-row button and reuses the shared select/body typography.
All 32 native Jobs checks, 78 targeted tests and 179 snapshot/reference checks passed.
The published release passed 3,372 isolated tests, exact-source Windows CI and 63
packaged upgrade checks. Fresh public assets are verified; 0.99.94 is staged in
the running 0.99.93 app for the owner's normal restart.
[Verification](dev/RELEASE_0_99_94.md) records validation and publication evidence.
The draft-only tests and inspector access from 0.99.93 remain in place: separate
models/history, temporary artifacts, seven-day retention and owner-approved,
read-only cross-agent artifact review. Model tests use saved inputs; script tests
require explicit draft-only commands. [0.99.93 verification](dev/RELEASE_0_99_93.md)
records the isolation boundaries and actual scoped-tool checks across all three CLIs.
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
