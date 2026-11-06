# ARMADA stabilization implementation plan

Started 5 November 2026 against 0.99.122 (`2487d89`). The owner authorized the plan
and implementation after the codebase review. Work proceeds in the order below,
with a checklist update and owner progress report after each implementation milestone.

## Working agreement

- Security containment first, then resilience, execution/performance, and CX.
- Preserve provider neutrality, portable realms, durable claims and signed updates.
- Use synthetic realms and isolated browser/native profiles. Do not restart the
  owner's app, execute business jobs, or use live connectors to validate changes.
- Keep each release focused. Passing checks marks implementation verified, not
  maintainer acceptance. Maintainer acceptance is recorded separately.
- Each completed milestone records changed behavior, tests, remaining limitations
  and release status here. Keep docs, version/changelog and generated references
  current at each release boundary; follow `RELEASING.md` in full.

## Ordered milestones

| ID | Work and intended outcome | Required evidence | Implementation | Acceptance |
|---|---|---|---|---|
| M1 | Protect control records: one shared classification; scoped raw writes cannot change live jobs, approvals, history, configuration or managed state. Keep artifacts writable and legitimate mutations behind validated operations. | Broad own-folder grants refuse control writes, preserve bytes and emit audit warnings; builder/owner behavior and existing provider policy tests pass. | **Verified; released 0.99.123** | Pending |
| M2 | Confine section assets, entries, snapshots and local pages using component-aware path validation, including Windows path/link edge cases. | Synthetic HTTP traversal regression, snapshot write refusal, allowed nested assets, content-origin and fallback checks. | **Verified; released 0.99.123** | Pending |
| M3 | Maintain the shipped runtime: inventory components and select/test a security-maintained Windows Python baseline; record publisher-signing and clean-machine distribution limits separately. | Official advisories, dependency compatibility, packaged native lifecycle/update gates and an installer migration plan. | **Verified; released 0.99.124** | Pending |
| M4 | Bound HTTP input and background probes: admission limits, header/body deadlines, strict body errors, shared provider refresh and unchanged-state write suppression. | Slow/incomplete clients, oversized/invalid bodies, bounded workers, Stop/health responsiveness, concurrent refresh tests. | **Verified; released 0.99.126** | Pending |
| M5 | Isolate corrupt records: tolerant presentation reads, strict execution/policy reads, visible repair information without permissive defaults. | One damaged agent/job does not break healthy views; affected work is held; repair preserves evidence. | **Verified; released 0.99.127** | Pending |
| M6 | Make exports collision-resistant and atomic, with a verified manifest and clear consistency/restore semantics. | Same-time exports, interrupted archive creation, skipped files, escaping links, synthetic restore. | **Verified; released 0.99.128** | Pending |
| M7 | Add explicit desktop presentation recovery for renderer/browser failure and unresponsiveness. Keep execution independent and never replay work. | Packaged native failure injection, bounded recovery/close, repeated tray/update cycles, drafts restored, no orphan surfaces. | **Locally and packaged verified; public release gates pending** | Pending |
| M8 | Separate scheduling from execution with bounded fair dispatch, per-provider/resource limits and cross-process admission ownership. | Independent realms progress under a slow job; capacity/ordering hold; queued/running cancellation; uncertain outcomes never replay automatically. | Pending | Pending |
| M9 | Remove lifetime-history work from common reads: narrow queries, rebuildable incremental summaries, independent thread previews and coalesced cache rebuilds. | Long-history and multi-window p50/p95; external edit/truncation invalidation; fresh policy checks remain authoritative. | Pending | Pending |
| M10 | Reduce page work: defer unused math/avatar/settings resources and move missing-snapshot fetches out of render requests. Preserve interaction state. | Browser resource measurements, slow snapshot source, warm navigation, selected tab/filter/focus/draft/scroll behavior. | Pending | Pending |
| M11 | Improve owner workflows: responsive dashboard/navigation, clear effective permissions with previews, attention summary and consistent operation outcomes; keyboard/zoom/accessibility pass. | Synthetic 1024px and scaled-display journeys, accurate policy summaries, keyboard/focus/dialog tests and reviewed light/dark captures. | Pending | Pending |
| M12 | Consolidate ownership/contracts and current security documentation; add repeatable stress/performance gates and finish release acceptance evidence. | Current guarantee matrix, module/adapter contracts, bounded multi-realm/window soak, restore and native release evidence; explicit maintainer sign-off. | Pending | Pending |

M4 includes provider-status coalescing because it is part of bounding background
work. M6 precedes native recovery so reliable exports are available before larger
lifecycle changes. M9 indexes remain disposable: JSON/Markdown stays authoritative.

## M4 verified and released — 5 November 2026

- Added a shared header gate, bounded request lanes and separate control capacity.
  Header/body deadlines and strict framing/JSON errors apply before mutation dispatch.
  Shared refusal draining preserves errors when uploads arrive late, without workers.
- Provider refreshes share three workers and one in-flight observation per provider,
  including the older authentication-status endpoint. Identical observations skip
  configuration writes; Disconnect remains authoritative during a refresh.
- Published **0.99.126** after **4,040 pinned tests** (six skipped), both exact-source
  Windows CI jobs (**4,042 each**, four skipped), all packaged native lifecycle
  checks and **72 signed-upgrade checks** passed. Final native thread-window probe:
  **79 checks passed**. Public signatures, downloads and matching website verified.
- Exact installer Sandbox: **26 passed**, one known WebView2 prerequisite failure.
  Clean-machine GUI and publisher signing remain unverified. The initial intermittent
  native-test timeout and the Windows refusal fixes are retained in
  [release evidence](RELEASE_0_99_126.md). [Resource contract](HTTP_LIMITS.md).
- Owner app was not restarted. Maintainer acceptance remains pending.

## M5: isolate damaged records

1. Keep presentation diagnostics separate from strict policy/execution reads.
2. Show damaged agents/jobs with repair information and hold their work; healthy
   siblings remain usable. Reads must preserve the original bytes.
3. Validate owner-requested repairs, preserve evidence and use shared locks/atomic
   replacement. Never reset security or execution state to permissive defaults.
4. Test malformed JSON, wrong field types, duplicate keys, unreadable encoding and
   damaged history rows using synthetic realms; verify refusal before model dispatch.

### M5 locally verified — 5 November 2026

- Added strict record shape checks and diagnostic presentation entries. Healthy
  pages remain available; damaged agents/jobs show an explicit owner repair page.
- Commands and automatic job/inbox dispatch validate affected records. Corrupt
  history holds scheduling without replaying uncertain work or dropping evidence.
- Owner repair verifies the reviewed digest under the shared lock, validates the
  replacement and preserves original bytes plus an audit receipt before atomic replace.
- Pinned isolated gate at `c2ffa92`: **4,087 passed, six skipped**. Final review
  additionally reproduced an invalid retry-count detail-page failure; shared retry
  validation now routes it to repair. **383 focused checks passed** after that fix.
  The earlier combined final page/state/reference check passed 401 tests.
- Public push was initially blocked by automatic approval review. The owner
  explicitly approved the 0.99.127 push and publication on 6 November.

### M5 published — 6 November 2026

- Released **0.99.127** from `719de63` through the mandatory publisher. Final pinned
  gate: **4,091 passed / six skipped**. Both exact-source Windows CI jobs:
  **4,093 passed / four skipped**; relay passed.
- Packaged launcher recovery/DLL isolation, 16 WebView2 session checks, 68 tray checks,
  69 checks in each restart mode and **72 signed-upgrade checks** all passed.
- Public manifest signature, package/source bytes, installer hash and matching
  website links verified. Website files were backed up; index.html published last.
- Owner app was not restarted. Maintainer acceptance remains pending. Existing
  unsigned publisher and clean-machine WebView2 boundaries remain explicit;
  Sandbox was not rerun for this app-only change. [Release evidence](RELEASE_0_99_127.md).
- Next: **M6**, atomic exports, collision-resistant filenames, manifests and restore
  semantics. Read-only review confirms exports currently write directly to a final
  ZIP named with minute precision; M6 implementation follows below.

## M6: verified exports and paused recovery — 6 November 2026

- Implemented unique filenames, same-volume staging, full manifest/hash verification
  and atomic publication that cannot overwrite an existing export.
- Added visible incomplete-copy/change reporting, explicit live-copy semantics,
  link/reparse exclusion and destination-outside-source enforcement. Durable claims,
  history and skill pins are preserved; credential/runtime omissions are listed.
- Added owner CLI verification/recovery into a fresh Windows folder. Recovery checks
  archive paths/hashes, pauses all job switches and retains claims/policies. It never
  registers, launches or merges realms. Incomplete recovery requires an explicit flag.
- Synthetic tests cover concurrency, write/read failures, hard process exit, changes,
  junction escape, ZIP64, hostile archives, limits and paused recovery/failure paths.
- Also removed the calendar expiry from M5's damaged-history test by freezing its clock.
- Full pinned isolated gate: **4,139 passed, six skipped** (660.73s). The focused
  export fault/recovery suite passed all **44 checks**. Both changed golden pages
  were reviewed; references and JavaScript/Python syntax checks are current.
- Owner approved push/publication after automatic approval review required explicit
  authorization. Released **0.99.128** from `7d06e68` through the mandatory publisher.
  Its final-source local gate again passed **4,139 / six skipped**; both exact-source
  Windows CI jobs passed **4,141 / four skipped**, and relay passed.
- Packaged launcher recovery/DLL isolation, 16 WebView2 session checks, 68 tray checks,
  69 checks in each restart mode and **72 signed-upgrade checks** passed.
- Public signatures, package/source bytes, installer hash and matching website links
  verified. Website files were backed up and index.html published last.
- Owner app was not restarted. Maintainer acceptance remains pending. Existing
  unsigned publisher and clean-machine WebView2 boundaries remain explicit;
  Sandbox was not rerun for this app-only change.
- Contract: [Realm exports](REALM_EXPORTS.md). [Release evidence](RELEASE_0_99_128.md).
  Next: **M7**, native presentation recovery.

## M7 implementation — 6 November 2026

- Added per-window native recovery, bounded browser operations, retry limits and
  authenticated return to the last safe display route without restarting execution.
- Added realm/page-bound unsent draft recovery, including a bounded native copy
  for fresh text lost before browser storage flushes. Uncertain submitted work is
  never resent across a renderer generation change.
- Native failure injection verified renderer crash, an infinite JavaScript loop,
  shared browser-process loss, companion recovery, preserved HWND/server/auth,
  one in-flight request completing exactly once, and busy restart teardown.
- The focused desktop/companion/thread suite passed **121 tests**; the final native
  probe passed **86 checks** and detached-thread probe **79**. Main/compact recovery
  controls were reviewed in both themes. The first full suite exposed four
  documentation/diagnostic/fixture issues; the corrected targeted suite passed
  **323 tests**. Corrected full pinned gate: **4,166 passed, six skipped** (634.23s).
  The final probe correction repeated that result in **642.07s**. Packaged launcher
  recovery/DLL isolation, session16, tray68, restart69 in each mode and presentation86
  all passed. Exact-source CI, signed-upgrade gate and publication remain pending.
  No owner app restart or live provider call.
- [Recovery contract and limits](DESKTOP_PRESENTATION_RECOVERY.md). The historical
  compositor ghost incident is not claimed conclusively reproduced or eliminated.

## Release boundaries

1. **Security containment patch:** M1 + M2, followed by the pinned full isolated
   gate, exact-source Windows CI, packaged native/upgrade checks and publication.
2. **Runtime security installer:** M3 independently, with explicit runtime
   compatibility/migration and clean-machine evidence.
3. **Resilience releases:** M4–M6 in focused batches; M7 as its own native lifecycle
   release. Retain any unverified acceptance limitations rather than checking them off.
4. **Execution and read performance:** M8 and M9 separately to keep concurrency and
   cache-invalidation regressions attributable.
5. **CX and contracts:** M10–M12 in small reviewed releases, with measured benefits.

No production data migration or new OS sandbox is assumed by this plan. Stronger
isolation of arbitrary third-party execution requires a separate design decision;
tool filtering and guarded file operations are not a hostile-code sandbox.

## Measurement and completion criteria

- Negative authorization tests cover Claude, Codex and Gemini plus managed tools.
  Malformed policy always refuses execution.
- One corrupt record cannot take healthy agents/views down; failures remain visible.
- A fixed load profile records thread count, memory, queue depth and latency until
  stable. Reserve capacity for Stop/health. Do not infer stress resilience from unit tests.
- Measure packaged first-usable-window time and warm-navigation p95 on a named
  machine. Candidate targets: warm core navigation <200ms and local Stop acknowledgement
  <250ms, with process cleanup bounded independently of UI delivery. Validate budgets
  before enforcing them as release gates.
- Native faults recover to a usable presentation or a bounded actionable failure,
  without duplicate external actions. App-owned renderer recovery needs no reboot.
- Core flows fit a 1024px window and common Windows scaling/zoom configurations.
- Exports preserve previous successes, identify incomplete content and restore into
  a fresh synthetic realm.

## Milestone log

### Installer regression — 5 November 2026, before M4

- Owner reported access denied replacing `python/vcruntime140.dll` in the full
  0.99.124 installer. Read-only inspection confirmed Python 3.14.10 installed but
  the skipped CRT remained 14.42.34438.0 instead of packaged 14.51.36247.0.
- An external Claude browser helper was observed loading ARMADA's private CRT.
  The native launcher used inheritable `SetDllDirectory(runtime)`; a synthetic
  child reproduced that inheritance. Process-local DLL search configuration and
  clearing the inherited path removed it in the same reproduction.
- Installer preparation now checks existing files without changing them and
  refuses locked/inaccessible payloads before deletion; it no longer force-stops
  ARMADA during upgrade. Automatic Setup logging is enabled.
- 20 installer/preflight checks passed, including lock refusal, byte preservation
  and retry after release. Inno Setup compilation and 68 native tray/lifecycle
  checks through the corrected launcher passed. Full release validation remains
  pending; this fix is not published yet.
- Owner installation remains unchanged. Repair requires a coordinated app quit;
  M4 follows this installer correction.

### Authorized local installer repair — 5 November 2026

- Owner confirmed no running jobs and authorized repair. ARMADA exited through
  normal window teardown; its original close-to-tray preference was restored.
  Only the verified browser helper still holding the CRT was stopped.
- Backed up both originals, verified prepared hashes, and atomically replaced
  `vcruntime140.dll` plus the corrected native launcher. The installed runtime
  probe passed and its inheritable DLL directory is empty.
- Reopened through the production desktop launcher. Authenticated desktop health,
  normal rendered Jobs page and loaded CRT 14.51.36247.0 verified. No realm/job
  records were changed by the repair. Backups and hash evidence are retained locally.
- This is a local repair of 0.99.124, not a new public release. Installer/launcher
  source changes still require the full release procedure before publication.

### Installer correction released — 5 November 2026

- Prepared 0.99.125 before M4. Added embedded payload hashes and post-copy
  verification before the compatibility marker, so skipping a required file
  cannot produce a successful installation. Whole-installer atomicity is not claimed.
- Launcher protocol 2 participates in runtime compatibility; versions through
  0.99.124 require the full installer. The native inheritance probe is mandatory
  during staging and covers clean and legacy parents using a synthetic child.
- Focused installer/runtime/update/release checks and 21 reviewed page snapshots
  passed. Sandbox now reproduces the locked-CRT case before normal installation.
  Published 0.99.125 after 4,010 pinned tests, both exact-source Windows CI jobs,
  all packaged native gates and 74 signed-upgrade checks passed. Public signatures,
  downloads and website verified. Exact public installer Sandbox: 26 passes and
  the known WebView2 prerequisite failure; clean-machine GUI acceptance remains
  unverified. See [release evidence](RELEASE_0_99_125.md).

### Plan baseline — 5 November 2026

- Repository clean at `2487d89`, version 0.99.122.
- Review reproduced scoped writes to live jobs/run history, section sibling-path
  escape, unbounded idle HTTP workers, corrupt-record read failure and export collisions.
- Review baseline: 239 existing tests passed / one skipped; eleven synthetic audit
  probes passed. Those probes confirmed defects, not desired behavior.
- M1 begins with failing regression tests; M2 follows before the first release.
- No implementation milestone or maintainer acceptance is marked complete yet.

### M1 implementation verified — 5 November 2026

- Added shared control-file names/tree classification for scoped tools and inspectors.
  Broad grants now refuse live jobs, runs/annotations, threads, shared/other-agent memory,
  managed inbox/goals, profiles, notification state and nested realms.
- Preserved the agent's own Markdown memory notes and pending JSON proposals within
  owner scope. Pending proposals must validate, match the filename, remain disabled,
  and cannot claim owner approval/provenance. Only owner approval makes them live.
- Regression cases first reproduced the defects. The access-policy, inspector,
  job-proposal and dry-run suites then passed (137 tests). These include all three
  adapters' existing policy assertions; no live provider was called.
- Remaining: full release gate/packaged validation after M2. Builder exemption and
  owner API edits are unchanged; these guards are not an OS hostile-code sandbox.

### M2 implementation verified — 5 November 2026

- Assets, entry pages, realm-local pages and snapshot destinations now share the
  existing Windows-safe relative-path primitive. It rejects sibling-prefix escapes,
  absolute/drive/UNC names, traversal, stream/device aliases and linked targets.
- Snapshot refresh rechecks the destination under its shared write lock. The owner
  refresh endpoint cannot report an existing out-of-realm file as a successful snapshot.
- Real synthetic HTTP tests cover content-origin and fallback serving; valid nested
  assets and Windows-style snapshot paths remain usable. A targeted combined run
  passed 132 tests with two symlink checks skipped by this account's privileges.
- Additional reparse-root and read-only-exception checks join the full release gate.
- M1 + M2 are prepared for 0.99.123. Full gate, exact-source CI, packaged native
  checks and publication are pending; the owner app remains untouched.

### Release validation correction — 5 November 2026

- The owner explicitly authorized the 0.99.123 public push, GitHub release and
  matching website publication using the existing unsigned-beta distribution.
- The first publisher attempt passed its local suite and exact-source Windows CI,
  then correctly stopped at a failed native restart assertion before any upload.
- A controlled reproduction identified a probe ordering race: already-visible
  state did not acknowledge the queued tray Open callback. The probe now waits
  for that callback before sending Close and fails on missing/failed callbacks.
- Twelve focused tests passed; the same controlled native race passed 69 checks.
  The application payload is unchanged by this correction. Full release gates
  are being rerun against the corrected probe commit; M1/M2 remain release pending.


### M1 + M2 published — 5 November 2026

- Released 0.99.123 from `e3f7c2b` on GitHub and armada.stamih.com through the
  mandatory publisher after correcting the native probe ordering race.
- Final publisher gate: 3,988 passed / 6 skipped. Both exact-source Windows CI
  jobs: 3,990 passed / 4 skipped; PHP relay passed. Packaged recovery/session/tray,
  all three restart cases and 72 signed-upgrade checks passed.
- Downloaded public signatures, package/module bytes and installer hash verified;
  live website version and release/download links match. Replaced website files
  were backed up and upload hashes checked before publication.
- The owner app was not restarted. Builder/owner boundaries are preserved.
  Maintainer acceptance remains pending; unsigned publisher/clean-machine and
  runtime-security limitations remain explicit in the release evidence.
- Next: M3. Initial Windows x64 / Python 3.14 dependency-resolution preflight
  succeeded for the nine existing pins; actual runtime/native compatibility and
  installer migration are not yet implemented or verified.

### M3 implementation — 5 November 2026

- Selected and verified Python 3.14.10 x64 from the maintained binary line. A shared
  runtime definition supplies both builders, the generated launcher DLL constant,
  wheel ABI and full-patch security baseline. Builds record actual components and
  a separately verified upstream inventory.
- Old runtime tags require the full installer before package download; matching
  baselines still stage normally. The previous-client release probe also checks
  refusal and preservation of synthetic data before a compatible native upgrade.
- 104 focused checks passed on the new interpreter before the additional marker
  recovery test; the compiled launcher and 68 real native tray checks also passed.
- Prepared 0.99.124, owner upgrade instructions and runtime/security documentation.
  Full isolated/CI, packaged checks, Sandbox evidence and publication are pending.
  No owner app was restarted. Acceptance remains separate.

### M3 published — 5 November 2026

- Released 0.99.124 from `e3bd5f2` on GitHub and armada.stamih.com. Public update
  signature, package/source bytes, installer hash and website links all verified.
- Final pinned gate: 4,001 passed / 6 skipped. Both exact-source Windows CI jobs:
  4,003 passed / 4 skipped; relay passed. Each suite reported one Python 3.14
  syntax warning for the existing voice-queue `return` in `finally`; include its
  exception-preservation cleanup in M8 rather than suppressing the warning.
- Packaged launcher recovery passed five interruption points; WebView2 sessions
  passed 16 checks, tray 68, each restart case 69, and signed upgrade/boundary 74.
  An additional preserved Python 3.12.10 / 0.99.123 preflight also refused the new
  runtime without downloading code or changing synthetic pending work.
- The isolated build host exposed a script-directory import assumption in release
  helpers. Explicit repository-package imports fixed it; 42 focused checks and
  the complete release gates then passed against the final source.
- Full installer required from 0.99.123 and earlier. The runtime definition,
  archive/inventory verification and generated component inventory are shipped.
  Exact-installer Sandbox rehearsal completed with 23 passed checks and one
  WebView2 prerequisite failure; clean-machine GUI acceptance is not passed.
  Windows publisher signing and clean-machine GUI acceptance remain limited by
  the existing maintenance distribution; see the exact [release evidence](RELEASE_0_99_124.md).
- Owner app and live realms untouched. Maintainer acceptance remains pending.
  Next: M4, bounded HTTP input/workers and coalesced provider-status refresh.
