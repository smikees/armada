# ARMADA roadmap and release status

The maintainer approves acceptance milestones. Implementation and passing tests
alone do not complete a product acceptance gate.

## Where things stand

Version **0.99.142** is in release validation. Detached thread and portrait outlines
retain their antialiased boundary pixels using a native transparent perimeter.
The live conversation, shadow and editor retain their behavior. See
[edge compositing](dev/THREAD_EDGES.md).

Version **0.99.141** is published: shared nested bullets, unlimited agent-job
and Inbox defaults, stalled-run handling, owner-sealed run controls, Claude API fallback
with a Windows worker boundary, saved provider usage and critical-job reservations.
The publisher passed **4,469 tests**, both exact-source Windows CI jobs passed
**4,471 tests**, and **72 packaged upgrade checks** passed. Native worker/DPAPI,
desktop and 45-minute synthetic execution checks passed. Public signatures,
all 487 package files, installer hash and website links verified. Worker/provider
sign-ins and a key are required to activate fallback; live API billing and broker
operations were not exercised. [Release evidence](dev/RELEASE_0_99_141.md).

Version **0.99.140** is published. The Windows 11 title bar follows the app's
light or dark background and shows only the native window controls. The line
under it spans the window, and the divider below the main menu aligns with the
content margins. The publisher passed **4,402 tests**, both Windows CI jobs
passed **4,404 tests**, and **72 packaged upgrade checks** passed. The public
website, installer hash, and signed update were verified.
[Release evidence](dev/RELEASE_0_99_140.md).

Version **0.99.139** is published. Conversations can run past 20 minutes, the
thread rail sections collapse, and App Settings has engine switches and read-only
system memories. Memory defaults to Realm and provides the same reader under App.
The publisher suite passed **4,400 tests** and both Windows CI jobs passed
**4,402 tests**. Native stability, memory and Inbox, and **72 packaged upgrade
checks** passed. The public site, installer hash, and signed update were verified.
[Release evidence](dev/RELEASE_0_99_139.md).

Version **0.99.138** is the published active-conversation steering release. Supported Codex
conversations accept extra owner instructions during the same run, from either
thread view, with exact-run checks and durable delivery status. CI also exposed
and drove a Windows dry-run marker-race repair and an HTTP test synchronization
correction. Final publisher: **4,397 passed / six skipped**; both exact-source
Windows jobs: **4,399 / four skipped**. Final-source stabilization, three
100-check native thread cycles, packaged lifecycle and **72 signed-upgrade
checks** passed. Public signatures, package/source bytes, installer hash and
website links verified. The owner app and live data were untouched.
[Steering contract](dev/STEERING.md) · [Release evidence](dev/RELEASE_0_99_138.md).

Version **0.99.137** is the published compact thread-activity release. Working
threads show one latest-action row above the status indicator; expansion reveals
ten entries at a time, with More for older entries. Pages, details and keyboard
focus survive streaming independently in each view. Publisher: **4,363 passed /
six skipped**; both exact-source Windows CI jobs: **4,365 / four skipped** after
one transient preflight startup timeout was investigated and retried. All 89
native thread checks, packaged lifecycle checks and **72 signed-upgrade checks**
passed. Public signatures, source bytes, installer hash and website links verified.
Owner app/live data untouched. [Release evidence](dev/RELEASE_0_99_137.md).

Version **0.99.136** is the published timed-inbox and shared system-memory release.
Automatic dispatch enforces processing windows; an acknowledged owner Process
now warning grants a recorded one-time exception. Settings → App manages shared
instructions across realms and providers. Publisher: **4,358 passed / six skipped**;
both exact-source Windows CI jobs: **4,360 / four skipped**. Ten native timing/UI
checks, full stabilization, packaged lifecycle and **72 signed-upgrade checks**
passed. Public signatures, source bytes, installer hash and website links verified.
Owner app/live data untouched. [Timing contract](dev/INBOX_TIMING.md) ·
[Release evidence](dev/RELEASE_0_99_136.md).

Version **0.99.135** is the published navigation follow-up: menu selections
immediately show the destination and a loading view, with safe slow-load
cancellation. Native delayed-response feedback measured 2.6ms (DOM state).
Release validation also exposed and fixed a concurrent-startup owner-publication
race. Publisher: **4,316 passed / six skipped**; both exact-source Windows CI jobs:
**4,318 / four skipped**. Native startup, full stabilization, packaged lifecycle
and **72 signed-upgrade checks** passed. Public signatures, source bytes,
installer hash and website links verified. Owner app/live data untouched.
[Navigation design](dev/NAVIGATION_FEEDBACK.md) ·
[Release evidence](dev/RELEASE_0_99_135.md).

Version **0.99.134** is the published M12 release. **All M1–M12 implementation
milestones are verified and released; maintainer product acceptance is still pending.**
Current security/ownership contracts and repeatable synthetic stress/performance
gates are in place. The final clean-source gate passed three concurrent realms,
protected writes, paused restores, long-history budgets and three native-window
cycles plus page/owner workflows. Publisher: **4,309 passed / six skipped**; both
exact-source Windows CI jobs: **4,311 / four skipped**. All packaged lifecycle and
**72 signed-upgrade checks** passed. Fresh recovery captures were reviewed. Public
signatures, package/source bytes, installer hash and matching website links verified.
Owner app and live realms/providers were untouched. Next: maintainer acceptance,
then Windows publisher signing and clean-machine WebView2 acceptance.
[Contracts and acceptance checklist](dev/STABILIZATION_CONTRACTS.md) ·
[Release evidence](dev/RELEASE_0_99_134.md).

Version **0.99.133** is the published M11 release: permission previews, responsive
owner workflows, keyboard-safe dialogs and visible save outcomes. Publisher:
**4,267 passed** (six skipped); both exact-source CI jobs: **4,269** (four skipped).
Native owner/page/shared-window checks, packaged lifecycle and 72 signed-upgrade
checks passed. Public signatures, source bytes, installer hash and website verified.
Owner app untouched; maintainer acceptance remains pending. M12 followed in 0.99.134.
[Owner workflows](dev/OWNER_WORKFLOWS.md) ·
[Release evidence](dev/RELEASE_0_99_133.md).

Version **0.99.132** is the published M10 release: lazy page resources, preserved
navigation state and bounded background snapshot refresh. Publisher: **4,245 passed**
(six skipped); both exact-source Windows CI jobs: **4,247** (four skipped). Native
page-work and shared-window checks, all packaged lifecycle checks and **72 signed-upgrade
checks** passed. Public signatures, package/source bytes, installer hash and website
links verified. Owner app untouched; maintainer acceptance remains pending.
M11 and M12 followed in 0.99.133 and 0.99.134.
[Page-work contract](dev/PAGE_WORK.md) · [Release evidence](dev/RELEASE_0_99_132.md).

Version **0.99.131** is the published M9 release: rebuildable history summaries,
recent-date queries, independent previews and shared transcript/metrics snapshots.
The mandatory publisher passed **4,232 tests** (six skipped); both exact-source
Windows CI jobs passed **4,234** (four skipped). Native shared windows passed **79**
checks; all packaged lifecycle/recovery gates and **72 signed-upgrade checks** passed.
Public signatures, package/source bytes, installer hash and matching website verified.
Owner app untouched. Maintainer acceptance and existing unsigned-publisher/clean-machine
boundaries remain pending. M10 followed in 0.99.132.
[History-read contract and timings](dev/HISTORY_READS.md) ·
[Release evidence](dev/RELEASE_0_99_131.md).

Version **0.99.130** is the published M8 release: fair bounded dispatch across realms,
shared desktop/scheduler/CLI capacity, durable queued chat and cross-process cancellation.
The final publisher gate passed **4,198 tests** (six skipped); both exact-source Windows
CI jobs passed **4,200** (four skipped). Native shared-window confirmation passed **79**
checks, and all packaged lifecycle/recovery gates plus **72 signed-upgrade checks** passed.
Public signatures, package/source bytes, installer hash and matching website verified.
Owner app untouched. Maintainer acceptance and existing unsigned-publisher/clean-machine
boundaries remain pending. M9 implementation is recorded above.
[Execution admission](dev/EXECUTION_ADMISSION.md) · [Release evidence](dev/RELEASE_0_99_130.md).

Version **0.99.129** is the published M7 release: native renderer/browser recovery,
bounded script operations and unsent composer recovery without request replay.
The synthetic native probe passed **86 recovery/lifecycle checks**, including
same HWND/server/auth, shared-process companion recovery and full busy teardown.
Light/dark main and 400px companion recovery panels were reviewed. The full pinned
gate passed **4,166 tests** (six skipped), including the final probe correction.
The publisher repeated the full gate and all packaged native checks, including
**86** presentation checks. Both exact-source Windows CI jobs passed **4,168 tests**;
**72 signed-upgrade checks** passed. Public signatures, downloads/source bytes and
matching website verified. Owner app untouched; maintainer acceptance remains pending.
[Recovery contract](dev/DESKTOP_PRESENTATION_RECOVERY.md) ·
[Release evidence](dev/RELEASE_0_99_129.md).

Version **0.99.128** is the published M6 release: atomic exports with verified
manifests, visible incomplete-copy warnings and fresh paused recovery. Final pinned
gate: **4,139 passed**; both exact-source Windows CI jobs: **4,141 each**. Packaged
native lifecycle and **72 signed-upgrade checks** passed. Public signatures,
downloads/source bytes and matching website links verified. Owner app untouched;
maintainer acceptance and existing publisher/clean-machine boundaries remain open.
M7 followed in 0.99.129. [Export contract](dev/REALM_EXPORTS.md)
· [Release evidence](dev/RELEASE_0_99_128.md).

Version **0.99.127** is the published M5 release: damaged agent/job isolation,
strict admission, visible repair diagnostics and explicit owner repairs preserving
evidence. The final pinned suite passed **4,091 tests**; both Windows CI jobs passed
**4,093 each**. Packaged native lifecycle and **72 signed-upgrade checks** passed.
Public signatures/downloads and website links verified. Owner app untouched;
maintainer acceptance and existing publisher/clean-machine boundaries remain pending.
M6 followed in 0.99.128. [Record contract](dev/RECORD_HEALTH.md) ·
[Release evidence](dev/RELEASE_0_99_127.md).

Version **0.99.126** is the published M4 resilience release: bounded local HTTP
input/workers, reserved server control capacity and shared provider refresh. The
pinned suite passed 4,040 tests; both Windows CI jobs, packaged native lifecycle
checks, 79 native thread-window checks and 72 signed-upgrade checks passed. Public
signatures/downloads and website verified. Exact-installer Sandbox passed 26 checks
with the known WebView2 prerequisite failure; clean-machine GUI acceptance remains
unverified. [Limits](dev/HTTP_LIMITS.md) ·
[Evidence](dev/RELEASE_0_99_126.md).

Version **0.99.125** is the published installer correction before M4. It prevents
private DLL search inheritance, refuses locked installations before mutation and
verifies copied payload bytes before marking success. The pinned suite passed
4,010 tests; both Windows CI jobs, packaged native and 74 upgrade checks passed.
Public signatures/downloads and the matching website were verified. Exact-installer
Sandbox passed 26 checks; its WebView2 prerequisite failure still leaves
clean-machine GUI acceptance unverified. [Evidence and remaining boundaries](dev/RELEASE_0_99_125.md).

The Windows beta supports Claude Code, Codex CLI and Gemini through Antigravity CLI.
Users may connect any one engine or any combination. Threads, jobs, model selection
and connector checks share provider-neutral application contracts; adapter limitations
and differences in telemetry remain explicit.

The current release is recorded in the [README](../README.md),
[changelog](../armada/webui/changelog.py) and [GitHub releases](https://github.com/smikees/armada/releases).
Version **0.99.124** is the published runtime-security release for M3. It upgrades the
bundled interpreter to Python 3.14.10, shares one runtime definition across both
builders and the native launcher, and includes the Python patch in compatibility
tags. Versions before 0.99.124 need the full installer. The pinned gate passed
4,001 tests (6 skipped); both exact-source Windows CI jobs passed 4,003 (4 skipped).
Packaged recovery/session/tray/restart and 74 signed upgrade/boundary checks passed.
Public assets, signatures and website links verified; the owner app was untouched.
Publisher signing and clean-machine GUI acceptance remain unverified. M4 followed in 0.99.126.
[Runtime contract](dev/RUNTIME_SECURITY.md) · [Release evidence](dev/RELEASE_0_99_124.md).

Version **0.99.123** is the published security containment release for the
[stabilization plan](dev/STABILIZATION_PLAN_2026_11.md). Scoped agents cannot rewrite
live jobs or execution history through a broad folder grant; valid pending proposals
and own memory notes stay available within scope. Section file and snapshot paths
are confined using Windows-safe component checks. Published on GitHub and
armada.stamih.com after 3,988 isolated tests passed (6 skipped), both exact-source
Windows CI jobs, packaged recovery/session/tray/restart gates and 72 signed-upgrade
checks. A diagnosed native probe ordering race was corrected before publication.
Public signatures, package bytes, installer hash and website links were verified;
the owner's app was not restarted. M1/M2 are released.
[Release evidence](dev/RELEASE_0_99_123.md).

Version **0.99.122** replaces abrupt desktop update exit with normal native teardown
before process handover. The visible, tray and stalled-renderer restart checks verify
form/browser disposal, removal of the HWND and browser/tray shutdown. The reported
orphan surface was cleared without reboot by an owner-approved compositor restart;
the exact compositor failure has not been reproduced in a synthetic test.
Published on GitHub and armada.stamih.com after 3,915 isolated tests passed (5 skipped),
both Windows CI jobs, the packaged recovery/session/tray gates, all three restart
teardown cases and 72 signed-upgrade checks. Public signatures, package contents,
installer bytes and website links were verified; the owner's app was not restarted.
[Incident, validation and release evidence](dev/RELEASE_0_99_122.md).

Version **0.99.121** adds owner-controlled connector tool lists, realm default denials,
agent write scopes, protected realm paths and run-level refusal audits. Enforcement
is implemented in all three adapters and a guarded filesystem tool. Published on
GitHub and armada.stamih.com after 3,909 isolated tests passed (5 skipped), exact-source
Windows CI, actual-provider checks and synthetic owner-edit UI checks. Packaged
recovery, session, tray and signed-upgrade gates passed; all public assets, update
signatures and website links were verified. The owner's app was not restarted.
[Verification and maintenance beta boundaries](dev/RELEASE_0_99_121.md).

Version **0.99.120** requires explicit tools choices on agent job proposals, warns before
approving tool-dependent work without tools, and audits existing enabled jobs at startup
and daily without changing them. Output contracts fail before a model turn when tools
are off. Published on GitHub and armada.stamih.com; 3,868 isolated tests passed (5
skipped), exact-source CI and the native startup, session, tray and upgrade gates
passed. Public assets and update signatures were verified; the owner's app was not
restarted. [Verification and maintenance beta boundaries](dev/RELEASE_0_99_120.md).

Version **0.99.117** hardens close-to-tray, restore and Quit with nonblocking native
transitions, bounded state saves and a mandatory real tray lifecycle installer gate.
[Verification](dev/RELEASE_0_99_117.md). The reported white-window freeze was not reproduced;
confirmed lifecycle races and diagnostic coverage are addressed.
Published on GitHub and the website with 3,767 isolated tests passing, exact-source
Windows CI, and native recovery/session/upgrade checks. Public assets and signed updates were
verified. Publication did not restart the owner app.

Version **0.99.116** applies the supplied Armada II usage-bar style, shorter Reset labels
and responsive header layout. [Verification](dev/RELEASE_0_99_116.md).
Published on GitHub and the website with 3,756 isolated tests passing, exact-source
Windows CI, and native recovery/session/upgrade checks. Public assets and signed updates were
verified. The owner app was not restarted.

Version **0.99.115** keeps the page-find box stable while typing and removes capabilities
in place with pending, failure and reduced-motion states. [Verification](dev/RELEASE_0_99_115.md).
Published on GitHub and the website with 3,754 isolated tests passing, exact-source
Windows CI, and native recovery/session/upgrade checks. Public assets and signed updates were
verified. The owner app was not restarted.

Version **0.99.114** makes Capabilities navigation responsive, keeps reviews across navigation,
reuses verified unchanged reviews, and updates access grants in place. Ctrl+F searches visible
section text with live highlighting. [Verification](dev/RELEASE_0_99_114.md).
Published on GitHub and the website with 3,751 isolated tests passing, exact-source
Windows CI, and native recovery/session/upgrade checks. Public assets and signed updates were
verified. The owner app was not restarted.

Version **0.99.113** preserves natural Codex voice while making its actual spoken transcript
the visible conversation and subsequent agent context. Work result retains the underlying answer;
interrupted/unspoken output is explicit and local batching/refresh waits are shorter.
[Verification](dev/RELEASE_0_99_113.md). Published on GitHub and the website with
3,738 isolated tests passing, exact-source Windows CI and native recovery/session/upgrade checks.
All public assets, the signed package and website download are verified; the owner app was not restarted.

Version **0.99.112** checks actual voice output and supports switching between spoken and text-only
replies without reopening the microphone. Connection copy distinguishes mode setup from permission.
[Verification](dev/RELEASE_0_99_112.md). Published on GitHub and the website with
3,726 isolated tests passing, exact-source Windows CI and native recovery/session/upgrade checks.
All public assets, the signed package and website download are verified; the owner app was not restarted.

Version **0.99.111** makes voice an input/output layer for the normal agent runner. A connecting
spinner gates the microphone; End call leaves real agent work running, while Stop work cancels it.
[Verification](dev/RELEASE_0_99_111.md). Published on GitHub and the website with
3,722 isolated tests passing, exact-source Windows CI and native recovery/session/upgrade checks.
All public assets, the signed package and website download are verified; the owner app was not restarted.

Version **0.99.110** fixes voice-to-reasoning handoffs, adds measured microphone feedback and
shows live speech in the shared thread, retaining incomplete transcription after interruption.
[Verification](dev/RELEASE_0_99_110.md). Published on GitHub and the website with
3,706 isolated tests passing, exact-source Windows CI and native recovery/session/upgrade checks.
All public assets, the signed package and website download are verified; the owner app was not restarted.

Version **0.99.109** adds an experimental Codex Dictate / Voice chat preview, bundled formula
rendering, preserved sent-message line breaks and bullets, live sidebar previews and consistent
thread menu interactions. [Verification](dev/RELEASE_0_99_109.md). Published on GitHub and the website with
3,702 isolated tests passing, exact-source Windows CI and native recovery/session/upgrade checks.
All public assets, the signed package and website download are verified; the owner app was not restarted.

Version **0.99.108** lets chats continue with unavailable connector tools withheld, adds
owner-assisted connector setup in normal chats, fixes Claude HTTP/SSE sign-in checks and displays
the saved reply outcome in both thread views. [Verification](dev/RELEASE_0_99_108.md).
Published on GitHub and the website with 3,657 tests passing, exact-source Windows CI,
5 recovery, 16 session and 69 upgrade checks. All public assets and the signed package
are verified; the owner’s running app was not restarted.

Version **0.99.107** tells agents whether a turn is a conversation, a one-off request or a scheduled
job run, so job-ending rules in profiles stay in jobs; Armada II starts at 13 px, the ready sound moves to
Advanced, and inspector agents carry a scan mark. [Verification](dev/RELEASE_0_99_107.md).

Version **0.99.106** adds the optional Armada II theme: IBM Plex typography, 15 px starting size,
softer corners and muted job status colors, with live previews in Settings. A quiet Windows
desktop-ready cue plays once per launch and can be disabled in Settings.
[Verification](dev/RELEASE_0_99_106.md).

Version **0.99.105** refines Add a capability after owner review: search as the main column, one
link field (repositories, skills, MCP addresses) in a side panel, Review before every add, and
"In this realm" as status text with Go to buttons. [Verification](dev/RELEASE_0_99_105.md).

Version **0.99.104** makes Add a capability a search: Alexander searches the sources the owner
switches on (what you have, and directories including ChatGPT’s plugins via Codex) and returns
cards built only from what sources returned; adding still goes through review or the engine’s consent.
[Design](dev/SMART_SEARCH.md) · [verification](dev/RELEASE_0_99_104.md).

Version **0.99.103** corrects false startup failures when restoring Settings or another page
without the optional icon helper, and preserves the saved route through authentication.
Native startup and packaged update gates now cover these paths.
[Incident and verification](dev/RELEASE_0_99_103.md). Owner acceptance milestones remain open.
Published on GitHub and the website with 3,604 tests passing, exact-source Windows CI,
9 native startup checks, 5 launcher recovery checks, 16 session checks and 69 upgrade checks.
The owner installation was successfully repaired through the normal update API; its window
and scheduler are healthy and saved preferences are unchanged.

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
