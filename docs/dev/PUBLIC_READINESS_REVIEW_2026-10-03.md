# ARMADA review before public announcement

**Recommendation:** complete a focused reliability and security pass before actively promoting the current installer. Keep the local, file-based architecture. The necessary refactoring concerns process ownership, registry persistence and update recovery; the broader UI cleanup can remain incremental.

Reviewed ARMADA **0.99.74**, commit **957ed54**, on 3 October 2026. The repository was clean at the start. Implementation began at Mihai's request after the review. Statuses below distinguish verified code changes from external acceptance gates; they do not constitute a launch sign-off.

## Findings at a glance

P1 findings should be resolved before broad promotion of the installer. P2 findings should be included in the same stabilization pass. These priorities reflect the move from an invited, single-user beta to wider distribution; they are not claims that every issue affects every installation.

| ID | Priority | Finding | Evidence | Scope of change | Implementation status |
|---|---|---|---|---|---|
| R1 | P1 | Installer distributes the support-mail credential | Build code and local 0.99.74 installer staging | Small to remove direct sending; medium for a relay | Implemented; live relay and inbox delivery verified. Private installer payload and signed update archive contain neither old nor replacement key. |
| R2 | P1 | Local control API does not authenticate its caller | HTTP dispatch and existing threat model T7 | Medium, across startup and API clients | Implemented; HTTP/startup/ACL checks and packaged native-browser authentication pass. Fresh-VM lifecycle rehearsal remains in R7. |
| R3 | P1 | Interrupted update can leave no importable app package | Reproduced by terminating between the two renames | Medium to large, bootstrap and update lifecycle | Implemented; crash recovery at all five durable steps passed through the compiled native launcher. Concurrency, active-work refusal and rejected-stage recovery tests passed. |
| R4 | P1 | Command descendants survive a reported timeout | Reproduced with a real child process | Medium, reuse existing process ownership | Implemented; 159 command/process, result, retry and keepalive checks passed. |
| R5 | P1 | Packaged Windows runtime silently ignores named timezones | Packaged-runtime check and frozen-clock probe | Small, dependency and validation changes | Implemented; zone/DST and explicit local-clock tests pass, including New York conversion in the bundled Python runtime and clean VM. |
| R6 | P2 | Realm-registry writes lose concurrent changes and overwrite corrupt input | Both failures reproduced in temporary files | Small to medium, one domain service and its callers | Implemented; caller, process/thread concurrency, corruption and rollback checks passed. |
| R7 | P2 | Release checks are neither fully isolated nor enforced | Full suite invoked installed Claude CLI; no declared CI gate | Medium, test boundaries and release tooling | Implementation complete; 3,020 tests passed, five skipped, exact-commit Windows/PHP CI passed and local installation was verified. 0.99.75 published as an unsigned beta at Mihai's request. Trusted publisher signing and clean-VM GUI acceptance remain open. |

R1 and R2 are previously documented beta exceptions, now relevant to a wider announcement. R3–R6 are concrete gaps in the current implementation. R7 extends the already-open release-gate work with newly observed test-isolation evidence. The September review's repaired findings are not being reopened wholesale.

## Implementation log

- 4 October publication update: Mihai explicitly requested an unsigned version on the website after discussing Application Control restrictions. [v0.99.75](https://github.com/smikees/armada/releases/tag/v0.99.75) publishes the exact locally verified installer below, with the signed update manifest referencing source commit `c2be69684220c7a72ee10261a93ba8196510ef9a`. [Windows and PHP CI passed for that commit](https://github.com/smikees/armada/actions/runs/37197850193). Installer payload/build inputs match that source; the update archive contains no old or replacement report key. The website and README now link to 0.99.75 and state the unsigned-installation limitation. This is a one-release owner-authorized exception to the signing and Sandbox GUI gates, not evidence that error 4551 or the WebView2 prerequisite failure was fixed. General release gates and launch acceptance checkboxes remain unchanged.
- Publication verification: all four assets were downloaded over public HTTPS and matched local SHA-256 hashes; the downloaded manifest signature passed the updater's verifier. GitHub reports 0.99.75 as the latest normal release. The live website matches the uploaded page after accounting for the host's existing monitoring-script insertion, and its installer link was verified. All 106 documentation-reference checks passed. Only the backed-up landing page was replaced on hosting; the report relay was preserved.

- Final 0.99.75 default suite: **3,020 passed, five skipped, exit 0**, in **461.06 seconds**. The installed application matches all 308 source application/bootstrap files. PHP tests passed 23 assertions without network. GitHub Windows validation runs for the source push; the two remaining public-installer blockers below remain open.

- 4 October, version 0.99.75: Mihai requested source publication and a local upgrade. The private installer passed imports, named-timezone conversion, native browser authentication and all five native recovery interruption points. Artifact inspection found zero matches for either report credential across 1,428 staged files and 307 ZIP members. Installed locally over 0.99.73 with exit 0; the same realm reopened, registry/config hashes were unchanged by Setup, and the scheduler became ready. Independent API access returns 401, the stable bootstrap is present and the old key file is absent. No Windows reboot was required. Private installer SHA-256: `a6968f9d98419ebb367f43b607330bf465dd1028e0586e020cc8dee49dc5672b`.
- The reported error 4551 on another machine identifies an additional public-distribution blocker: Windows rejects the unsigned extracted Inno Setup executable. Public builds now require Authenticode signing for Setup, its temporary copy/uninstaller and unsigned native payload images. Inspection found 132 valid upstream signatures and seven unsigned images. A trusted signing account is not configured, so actual signed-build acceptance remains pending. The existing website download remains 0.99.74; do not describe the private local build as fixing Application Control. See [Inno's temporary-copy signing behavior](https://jrsoftware.org/ishelp/topic_setup_signeduninstaller.htm) and [Microsoft's signing guidance](https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/code-signing-for-smart-app-control).
- Version-bump validation: the initial full run passed 3,018 tests with five skips; two failures were a machine-local documentation link and the intentionally changed Settings changelog. The local link was removed and only the new changelog section was approved in the snapshot diff. All 177 affected documentation, golden-page, installer, signing and release-gate tests then passed. A final full run and exact-commit Windows CI are required before public installer publication, alongside signing and the unresolved clean-VM prerequisite check.

- R1: credential copying/carry-forward removed and build rejection added. In-app sending uses the PHP relay deployed at `https://armada.stamih.com/api/report.php`. The replacement key and library are outside `public_html`, with 0700 directory/0600 configuration permissions. The old key was deleted. Local relay tests passed 23 assertions; live checks rejected recipient overrides and oversized input, verified private URLs return 404, and exercised an identical retry. Resend accepted the one approved verification email and Mihai confirmed inbox arrival. Temporary deployment helpers were removed. Existing clients need the next app release; final package inspection is included in R7.
- R2: privileged HTTP reads/writes require a per-launch capability; the desktop exchanges it for an HttpOnly cookie through a fragment bootstrap. Windows ACLs restrict bootstrap files to the owner and SYSTEM. Content-origin guards and internal authenticated restart/discovery clients are covered. The R1/R2 focused suite passed, followed by 115 startup/authentication/timezone checks after cleanup hardening. Native installed-window validation remains in R7.
- R5: pinned `tzdata==2026.5`; unresolved configured zones now hold scheduling with an actionable error, while existing explicit local settings remain valid. Tests cover the package fallback without OS zone data, different day boundaries, gap catch-up and once-per-day dispatch across the repeated DST hour. New York conversion passed in both the bundled runtime and a clean Windows Sandbox.
- R6: all registry mutations now use the strict domain service and an exclusive read-modify-write transaction. Folder-move rollback no longer restores stale registry snapshots. The first 141 caller regression checks passed, followed by 84 checks including concurrent thread/process writes, malformed input, transaction rollback and a folder-move failure interleaved with another registration.

- R4: commands and the keepalive call use the owned process supervisor. Raw stdout/whitespace and environment/argv handling are preserved; output over 4 MiB stdout or 1 MiB stderr terminates the tree with an explicit failure. Commands participate in cancellation tracking. Windows cleanup now retains descendant handles and waits for termination before reporting completion. All 159 focused checks passed, including real parent/child/grandchild timeout, cancellation, inherited-pipe cleanup and output floods.

- R3: the compiled launcher now enters a stable bootstrap outside the replaceable package. A durable journal, installation lock and process leases protect package replacement; restarts refuse new work once requested. Interruption at all five durable steps recovered on the next native launch. Additional tests cover simultaneous launches/downloads, locked processes, rollback, active-work refusal, older stages and recovery after a rejected stage. Rejected packages are visible in Settings and require a new verified download before retry.
- R7: pinned development dependencies, isolated homes, external-network/provider guards, a Windows CI matrix and an enforced publish gate are implemented. The first complete gate passed 2,995 tests with 5 skips; final validation is recorded below when finished. The private candidate also exposed a pre-existing installer process-discovery bug: a 32-bit PowerShell process could miss the path of the 64-bit native host. CIM executable-path matching now stops only this installation's processes; clean-VM uninstall/reinstall checks passed. WebView2 installation in the VM still requires investigation before native-window acceptance can be marked complete.
- Artifact inspection: private candidate 3 installer SHA-256 `8e2e2d5c2f3f31d8bb49a01d496c4fb9f657127af985514472e3f1cbe59aa280`; signed update ZIP SHA-256 `dbb5d36c00259b3ceef4d6f459b79b9f284f91d038ed63c2b8725c84d854f094`. Inspection covered 1,398 staged installer files and 307 update members, comparing both sending credentials without displaying them: zero matches. Candidate runtime and installer source match the working checkout. These are private validation artifacts retaining the current version label, not a new published release.
- R2 native check: a hidden instance of the packaged launcher/runtime used a temporary home, with machine-wide startup/tray effects disabled. Its real WebView authenticated through the fragment bootstrap, removed the fragment, kept the cookie inaccessible to JavaScript and received HTTP 200 on a privileged API. An independent unauthenticated client received HTTP 401. The existing user app and scheduler were left running.
- Final default suite: **2,999 passed, 5 skipped, exit 0**, in **476.90 seconds**, through the pinned release gate. An additional focused pass validated scheduler DST dispatch and the process-guard subclass contract. Default live-realm checks are intentionally skipped; no paid provider was invoked. Windows CI is defined and enforced by the publish script, but has not run remotely because these changes have not been pushed.
- R7 outstanding acceptance (4 October): this Windows 11 Sandbox image rejects both Microsoft's signed web bootstrapper and signed standalone installer with `0x80040902`, internal code 11, reporting that it cannot create a temporary directory. Reproduced from a local VM copy with over 82 GB free; SYSTEM write probes succeeded in Windows Temp, SystemTemp and Microsoft Temp. This is not yet explained. ARMADA install/import/timezone checks and process shutdown/uninstall/reinstall passed; the packaged browser authentication passed separately on the host with isolated data. The clean-VM GUI, first-job and native restart sequence remains unverified, and the publish gate intentionally rejects the failed VM result. Diagnostic logs are retained in `D:/Work/armada-review-2026-10-03/webview-diagnostics` and `build/sandbox-runs/20261003-235804`. Disposable VMs and hidden test app instances have been closed. Use a working clean Windows environment or resolve the Microsoft dependency failure before marking R7 accepted.
- Rehearsal tooling follow-up: live runs also exposed transient Windows sharing violations while reading the VM report and console encoding errors while printing it. The gate now tolerates an in-progress report write, saves artifact evidence before printing, and handles console encoding safely. Targeted release-gate/installer/documentation checks passed after these fixes. The saved failed VM evidence was reconstructed from the preserved report and exact artifact hash; it is not a successful rehearsal.

## R1 Remove the distributed support credential

**Locations:** `tools/build_installer.py` (reviewed line 203), `armada/support.py` (reviewed line 159), `armada/support.py` (reviewed line 201), `armada/updater.py` (reviewed line 82), `docs/dev/THREAT_MODEL.md:87`.

The installer explicitly copies `armada/support_key.txt`; the support sender reads it and calls Resend directly. The local 0.99.74 staging directory contains this file. I checked its presence and size without reading or displaying the key. I did not download and independently unpack the public installer.

Anyone with a build containing the key can bypass the application's fixed recipient and client-side hourly limit. Keeping the file out of Git does not protect a credential shipped in an installer. The threat model already requires a relay before public release, but understates abuse by suggesting the extracted key is confined to the support inbox. Resend's documented sending permission permits sending email; an application-level recipient restriction is not a provider-side restriction. Actual account configuration and usage limits were not queried. [Resend API key documentation](https://resend.com/docs/api-reference/api-keys/create-api-key).

**Proposed change:** move sending behind a small service that fixes the recipient and enforces payload limits and abuse controls. Keep the Resend credential server-side. Remove the installer copy and updater carry-forward behavior, then revoke or rotate the previously distributed credential. Merely removing it from the next build leaves old copies usable. If the relay would delay the announcement, use the existing save-report-and-email-manually fallback in the public build.

**Acceptance:** inspect the final installer and update package for credentials; verify arbitrary recipients are rejected by the service; verify server-side throttling and the local fallback. Plan the transition for old clients before revocation. No relay deployment or credential rotation was performed in this review.

## R2 Authenticate access to the local control API

**Locations:** `armada/serve.py` (reviewed line 135), `armada/serve.py` (reviewed line 185), `armada/serve.py` (reviewed line 329), `armada/request_context.py` (reviewed line 32), `docs/dev/THREAT_MODEL.md:83`.

The Host and Origin guards provide useful browser protections. They do not authenticate a local caller: a request with no Origin passes `_same_origin`, and privileged routes require no secret. Realm identifiers prevent operations targeting the wrong realm, but are discoverable through the API and are not credentials.

Another Windows account or untrusted local process can reach the owner's loopback server and invoke operations with the owner's application privileges. This is the already-accepted single-user-beta limitation T7, not evidence of an Internet-exposed listener or a newly demonstrated browser-origin bypass.

**Proposed change:** require an unguessable per-launch capability for privileged reads and writes, delivered through a bootstrap restricted to the owning OS user. Define the limited unauthenticated health response deliberately. Update browser startup, the desktop host, scheduler restart requests and other internal clients together. Preserve the existing Host, Origin and content-isolation protections; keep the capability out of artifact content, logs and exported realms.

**Acceptance:** use a second local account or an unauthenticated client to verify that neither sensitive reads nor mutations succeed; verify a normal app launch and scheduler restart still work; verify content-origin pages cannot obtain or use the capability. This does not attempt to defend against malware already running with full access to the owner's files.

## R3 Make updates recoverable before importing ARMADA

**Locations:** `armada/updater.py` (reviewed line 282), `armada/updater.py` (reviewed line 367), `armada/updater.py` (reviewed line 382), `armada/__main__.py` (reviewed line 1), `installer/ArmadaLauncher.cs:27`.

`apply_staged` first renames the live package to `armada.previous`, then renames the staged package into place. It rolls back an ordinary exception in the second operation. It cannot roll back a process termination or power loss between those operations. Recovery currently lives inside the package that may now be missing; the native launcher only starts Python.

**Reproduction:** in a disposable fake installation, exit the updater process immediately after its successful first rename. The process exited with code 77, `armada/` was absent, and both `armada.previous/` and `armada.staged/` remained. A normal `python -m armada` launch cannot import the missing package to reach `updater.boot`. Existing tests cover a raised exception during the swap, not this interruption.

The same lifecycle needs serialization: `_stage` uses a shared staging path and removes the previous staging directory, while UI and scheduler checks can both reach it. There is no installation-wide lock around staging/application. That concurrency risk is a source finding; the deterministic reproduction above exercises the interrupted swap.

**Proposed change:** introduce a small stable bootstrap outside the replaceable package, with a durable update journal and recovery before package import. Give one installation-wide owner the staging and apply operations, use unique download staging directories, and quiesce active work before replacement. Preserve manifest/signature verification and the recoverable previous version.

**Acceptance:** terminate an update at each durable step and prove the next normal launch recovers to a complete old or new version. Exercise simultaneous update checks, competing startup attempts, locked files and update requests during an active turn. Verify this through the installed launcher, not only by importing `updater` in a unit test.

## R4 Give command jobs the existing process lifetime guarantees

**Locations:** `armada/runner.py` (reviewed line 1158), `armada/runner.py` (reviewed line 1194), `armada/engine/process.py` (reviewed line 63). The separate keepalive path at `armada/sysjobs.py` (reviewed line 173) should be considered in the same subprocess inventory.

Agent adapters use the shared supervisor with Windows Job Object ownership, cancellation and bounded output handling. Command jobs use `subprocess.run(..., timeout=..., capture_output=True)` instead. A timeout terminates the direct process while descendants can continue doing work; captured output is also unbounded.

**Reproduction:** a command spawned a child that waited 2.5 seconds and wrote a marker, then the parent exceeded a one-second timeout. ARMADA returned `timed_out` after 1.04 seconds with no marker present. The child subsequently wrote it. The timeout result therefore does not establish that command activity has stopped. Later runs or eligible retries can overlap surviving work.

**Proposed change:** extract or extend the shared supervisor's generic transport so command jobs use the same process-tree ownership and cleanup. Preserve raw argv, environment, working-directory and stdout/stderr semantics without forcing commands through a model protocol parser. Give command output an explicit bounded policy, with truncation or spooling reported honestly.

**Acceptance:** real parent/grandchild tests for timeout and cancellation, including inherited pipes and heavy output; verify no descendant can write after terminal completion. Cover ordinary command success and failure and preserve job-result/retry semantics. Audit remaining long-running subprocess call sites, rather than mechanically replacing every short utility command.

## R5 Package timezone data and reject unresolved configured zones

**Locations:** `requirements.txt:1`, `armada/scheduler.py` (reviewed line 219), `armada/scheduler.py` (reviewed line 230), `tools/build_installer.py` (reviewed line 48).

The runtime requirements omit `tzdata`. The staged installer runtime is Python 3.12.10 with an empty `zoneinfo.TZPATH` and no `tzdata` package. Constructing `ZoneInfo('America/New_York')` in that runtime raises `ZoneInfoNotFoundError`. `_tz` suppresses that error and silently uses local time.

**Reproduction:** freeze the clock at 12:00 UTC on 3 October 2026 and request the New York realm timezone. `now_in` returned 12:00 UTC instead of 08:00 in New York. Users whose realm and computer timezones happen to agree can miss the problem; travelling or configuring a different realm timezone exposes incorrect scheduling and day boundaries.

Python explicitly recommends a `tzdata` dependency for cross-platform applications needing IANA zones, particularly on Windows. [Python zoneinfo documentation](https://docs.python.org/3.12/library/zoneinfo.html#data-sources).

**Proposed change:** pin and include `tzdata`; validate configured zone names and surface an actionable hold/error when they cannot be resolved. Keep local time as an intentional option when no named zone is configured, rather than as a silent recovery from invalid configuration.

**Acceptance:** named-zone checks in the actual installer runtime; schedule/day-boundary tests where realm and machine zones differ; DST transition tests for both skipped and repeated local times. Changing requirements changes the runtime compatibility tag, so include this in the new-installer and existing-installation upgrade rehearsal.

## R6 Move realm registration into a strict persistence service

**Locations:** `armada/routes/_shared.py` (reviewed line 71), `armada/routes/_shared.py` (reviewed line 80), `armada/routes/_shared.py` (reviewed line 86), `armada/routes/_shared.py` (reviewed line 109), `armada/setupfolder.py` (reviewed line 67), `armada/request_context.py` (reviewed line 53).

The registry uses atomic replacement, but `_reg_ensure` and `_reg_rename` do not lock the complete read-modify-write operation. Some callers acquire a registry lock, while others do not, so the protection is inconsistent. `_reg_load` also converts unreadable or invalid JSON into an empty list, which a subsequent write replaces.

**Reproduction:** synchronize two `_reg_ensure` calls after both read the empty registry. Both returned without error, but only one realm was retained. In a separate probe, registering a realm over malformed registry JSON overwrote the corrupt bytes instead of preserving them. Realm folders are not deleted by these failures, but entries disappear from discovery and the switcher, with consequences for future scheduler discovery.

**Proposed change:** create a domain-level `realm_registry` service with validated list/record loading and one exclusive read-modify-write boundary. Distinguish missing state from invalid state and preserve invalid bytes for recovery. Migrate all creation, adoption, rename, removal and folder-move callers. This also removes the dependency from domain/startup code on private HTTP-route helpers.

**Acceptance:** concurrent add/add, add/rename and add/remove interleavings; malformed JSON and wrong top-level types preserved; folder-move failure cannot overwrite a registration made by another writer. Exercise both threads and independent processes using the existing kernel-lock mechanism.

## R7 Finish the release gate and prevent tests from reaching real providers

**Locations:** `tests/conftest.py` (reviewed line 1), `tests/test_scheduler_lock.py` (reviewed line 119), `armada/sysjobs.py` (reviewed line 173), `tools/publish_release.py` (reviewed line 50), `requirements.txt:1`. Existing plan items: 2.21, 5.10 and 8.1.

The full suite finished successfully: **2,927 passed, 2 skipped, exit code 0**, in **757.95 seconds**, on Windows/Python 3.12.14. That is useful regression evidence, but it is not a fully isolated release gate.

The standalone scheduler-lock test reached real system upkeep. Its temporary `system_jobs.json` records the installed `claude.exe` being invoked with a one-word keepalive prompt, then timing out after 120 seconds. Capability upkeep also took approximately 50 seconds. The conftest disables Gemini launch and several outbound channels but does not globally prevent Claude launches or all outbound operations. No successful provider response was observed for this keepalive. A default unit suite should not depend on installed credentials, consume provider quota or wait on external tools.

The checkout has no tracked Windows CI workflow or pinned development/test dependency set. The publish script verifies Git state and builds artifacts, but does not require a successful test result for that commit. The developer test runtime is also newer than the Python 3.12.10 runtime being packaged. This is a finding about the checkout and its publish path; external repository branch-protection settings were not audited.

**Proposed change:** fail closed on external network/provider calls in default tests, isolate the process environment and user data roots, and make real-provider integration tests explicit opt-ins. Scheduler ownership tests should fake upkeep; upkeep tests should exercise controlled adapters. Pin test tools and declare required Windows checks for the release commit. Add actual packaged-runtime smoke checks and complete the separate clean-machine installer rehearsal. Define a supported Python runtime refresh policy.

**Acceptance:** the default suite passes without installed providers, credentials or network and does not create external provider processes. The release gate records the tested commit and artifact identities. A fresh Windows user/VM can install, complete setup, run a first job, recover from an interrupted update and reopen existing realms. The pass count above does not complete these outstanding checks.

## Refactoring that can follow the announcement

The existing modular monolith fits this product. Portable JSON/Markdown realms, server-rendered pages, a separate scheduler and provider CLI adapters remain reasonable choices. The recent immutable run context, shared turn coordinator, strict state readers, scheduler claims and isolated content origin are meaningful improvements.

The three refactorings to prioritize now are **update ownership/recovery**, **shared command-process supervision**, and **a dedicated realm-registry service**. Each closes an observed failure and establishes a reusable boundary.

Other cleanup has a lower immediate return:

- **Explicit UI imports and exports:** finish the already-deferred D.8 work incrementally. `webui/__init__.py` (reviewed line 18) and `webui/pages.py` (reviewed line 18) still copy namespaces using `globals().update`. Replace them page by page, preserve the renderer facade, and use deterministic goldens to verify behavior.
- **Smaller page modules:** `webui/pages.py` is 1,656 lines and `render_settings` spans 416 lines. Split by settings area or rendering responsibility when those areas change. File length alone is not a release blocker.
- **Smaller lifecycle methods:** `TurnCoordinator.run` spans 211 lines. Separate preparation, execution and finalization when doing lifecycle work, while retaining one authoritative owner of admission, cancellation and terminal persistence. Avoid recreating independent entry-point lifecycles.
- **Provider-specific policy:** extend explicit adapter capabilities where concrete differences require it. Avoid a speculative plugin framework or a broad provider abstraction rewrite ahead of user feedback.

I found no reason in this review to replace the frontend framework, introduce microservices, or migrate all realm state to a database for the announcement.

## Proposed delivery order

1. Remove public-build credential distribution and plan revocation; establish the API authentication boundary. These are the invited-beta assumptions that should change before wider distribution.
2. Add timezone data and strict registry persistence. These are comparatively contained fixes with deterministic acceptance tests.
3. Unify command-process ownership and make update recovery work through the installed bootstrap. These have the largest lifecycle impact and need interruption tests.
4. Complete test isolation, required Windows checks and the clean-machine/upgrade rehearsal on the resulting build. Add regressions alongside each fix; do not postpone them until this final step.

Leave general UI and coordinator decomposition as follow-up work unless a concrete fix needs a local extraction. No estimate here assumes access to a relay deployment, code-signing certificate or fresh Windows VM.

## Review coverage and evidence

The source inventory contains 137 Python modules under `armada/`, totaling 37,332 lines. The review traced execution and provider boundaries, request/realm identity, scheduler claims and system jobs, file mutation contracts, memory handling, content isolation, update verification/application, installer/release tooling and UI module structure. It cross-checked the architecture, conventions, threat model, launch plan and September review. This was risk-focused inspection, not a claim of line-by-line verification of every module.

The four targeted reproductions used temporary fixture directories and controlled child processes. They changed no live realm and made no provider or mail calls. The full suite separately exposed the installed-CLI invocation described in R7. The suite's temporary files and test log remain available as evidence. An earlier test invocation failed at setup because the reviewer had not created the parent of the requested basetemp directory; that invocation is excluded from the product findings and result above.

Local evidence:

- Probe script and results: probes.py and probe-results.json in the private review evidence folder.
- Complete initial test output: `tests.log` in that folder.
- Initial scheduler fixture: `pytest-run-1/test_a_standalone_tick_takes_a0/r/system_jobs.json` in that folder.

These machine-local artifacts are intentionally not repository links or prerequisites for CI.

Source locations in this document are repository-relative at the reviewed commit. No live paid-provider acceptance test, independent dependency vulnerability audit, browser penetration test or clean-machine installation was completed. Installer signing is already documented as absent; update-manifest signing is a separate, implemented protection. A wider-distribution decision should retain that distinction.
