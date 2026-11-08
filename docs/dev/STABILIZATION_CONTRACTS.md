# Stabilization contracts and acceptance

Current contract, 8 November 2026. This consolidates M1–M12; historical architecture
and threat-model passages remain dated history. Tests establish the behavior below,
not a guarantee against every Windows, provider, hardware or malicious-local-process
failure. Acceptance belongs to the maintainer and is recorded separately in the
[milestone checklist](STABILIZATION_PLAN_2026_11.md).

## Authority and module ownership

| Boundary | Owning modules | Required contract for future changes |
|---|---|---|
| Canonical records | `util`, `record_health`, `control_files` | JSON/Markdown is authoritative. Mutations use shared locks and atomic replacement. Tolerant display reads never become permissive execution defaults. Preserve damaged bytes and repair evidence. |
| Realm/request identity | `request_context`, `local_auth`, `serve`, `origins` | Capture immutable request/run context; authenticate owner actions and bind them to the intended realm. Server/control capacity is bounded. Untrusted content does not inherit owner-origin privileges. |
| Connector and file policy | `capabilities`, `access_policy`, `tool_admission`, `policy_tools` | Validate before dispatch, compile from current grants, and check guarded writes on each call. Agent deny wins; explicit agent allow may override a realm default, never a withheld connector grant. Missing glob inventory refuses execution. |
| Scheduling and execution | `daemon`, `execution_admission`, `runner`, `coordinator`, engine adapters | Discovery does not hold the execution loop. Admission tickets own capacity, not authorization. Revalidate after waiting. Run-specific durable claims prevent automatic replay of uncertain outcomes. |
| Presentation reads | `run_summary`, `view_cache`, `reader`, `thread_windows` | Bounded, disposable caches may accelerate display. They cannot authorize work or replace fresh canonical execution/policy reads. Detect append/replacement/truncation and pending history transactions. |
| Desktop lifecycle | `app`, `desktop_launch`, `instance`, desktop recovery modules | Keep model execution separate from renderer recovery; preserve authentication and unsent drafts. Never replay submitted work. Dispose native controls before process handover. |
| Snapshot refresh | `section_snapshots`, dashboard routes | Render the existing copy or placeholder without source network I/O. Coalesce bounded background refreshes; verify configuration and target again before atomic publication. |
| Owner workflow | `accesspolicy`, `attention`, `dialogs.js`, `dash.js`, `page_state.js` | Preview is advisory and does not save. Distinguish pending/success/failure/unknown outcomes. Serialize layout saves; require reload after an uncertain write. Restore only presentation state and unsent drafts. |
| Export/recovery | `realm_export` | Publish verified archives atomically without replacing another export. Restore only into a fresh folder with all execution switches paused. Never register, launch or merge automatically. |
| Distribution | runtime definition, launcher, release tools | Build from the committed source; verify pinned runtime/update signatures and exact-source CI. Native lifecycle and signed-upgrade gates precede publication. Website links must match released assets. |

Names identify ownership, not permission to bypass the public seam. New code should
extend the shared contract, rather than introduce another independent parser,
authorization decision, mutation lock or process launcher. The generated
[module reference](reference/index.md) lists current APIs.

## Provider adapter contract

Claude, Codex and Gemini/Antigravity are equal choices. A caller selects through the
engine seam; an adapter owns provider-specific configuration, authentication,
tool serialization, subprocess cancellation and telemetry. Shared orchestration
must not infer access from a model's text or a provider's display label.

- Preserve whole-connector grants **and** compiled per-tool restrictions. Multiple
  logical capabilities sharing one registration intersect their restrictions.
- Offer only admitted tools. Capture the offered inventory and refusal evidence in
  the run audit. Missing policy support, malformed policy or unknown required
  inventory stops execution with an actionable error; never retry unrestricted.
- A write-scoped turn removes native shell/write/child-agent escape routes and uses
  the guarded file tool. A scope grants no connector. Builder/owner exemptions and
  protected control records retain their documented semantics.
- Queueing, cancellation and transport failure must preserve whether the outcome is
  known. Adapter retries cannot resend uncertain external actions automatically.
- Native Codex apps cannot currently enforce individual tool policies; a supported
  MCP connection is required. CLI version floors and compatibility refusal live in
  [access policy](ACCESS_POLICY.md), not in UI assumptions.

## Guarantee matrix and limits

| Area | Verified behavior | Deliberate limit / remaining acceptance |
|---|---|---|
| Tool/file containment | Fresh policy validation; deny precedence; guarded atomic file writes; refusal audit and first-agent/day notification | This is not an OS sandbox. A permitted external connector may perform its own file/network effects. Host administrators, hostile local processes and provider bugs are outside this boundary. Reads remain unchanged. |
| Control integrity | Scoped raw writes cannot alter configuration, approvals, live jobs, history or managed state; validated note/proposal operations remain possible | Owner/builder authority is intentional. Per-file atomicity is not a transaction across arbitrary files. |
| Local HTTP | Bounded lanes, headers/bodies/deadlines and reserved control capacity; authenticated realm-bound actions | A continuously flooding local process can still deny service. See [HTTP limits](HTTP_LIMITS.md) for exact bounds. |
| Execution | Four account slots, two per provider/realm, one per conversation; bounded queue; kernel ownership; cross-process Stop | Cancellation cannot undo an external action already accepted by a provider. Crash release of capacity does not prove the external outcome. [Admission](EXECUTION_ADMISSION.md). |
| Corrupt records | Healthy views survive damaged siblings; affected work is held; reviewed repairs retain evidence | Not automatic semantic repair or recovery of arbitrary missing data. [Record health](RECORD_HEALTH.md). |
| History/cache | Incremental common reads, invalidation and bounded retained summaries/views | Cold builds and rebuild working memory remain proportional to source size. Cached display can briefly lag edits; authorization is never cached here. [History reads](HISTORY_READS.md). |
| Snapshot work | Two workers, eight admissions, bounded payloads and configuration-bound commits; last copy survives failure | Local/network-drive reads may block a worker. HTTP total budget can extend by one socket read. [Page work](PAGE_WORK.md). |
| Export/restore | Hash-verified immutable archive, collision resistance, paused new-folder recovery | Live exports are a best-effort capture, not a globally consistent database snapshot. Credentials/runtime omissions and incomplete files are explicit. [Exports](REALM_EXPORTS.md). |
| Desktop recovery | Tested renderer/browser crashes and stalls, bounded retries, draft preservation, no replay, disposal before restart | The original Windows compositor ghost was not conclusively reproduced or eliminated. OS compositor/driver failures may need separate recovery. [Desktop recovery](DESKTOP_PRESENTATION_RECOVERY.md). |
| Navigation/accessibility | Tested keyboard focus/Cancel/Escape, named dialogs, 1024px and 150% native zoom, visible operation outcomes | Not a complete screen-reader/WCAG certification. Simultaneous windows use last completed layout write; they are not collaborative layout editors. [Owner workflows](OWNER_WORKFLOWS.md). |
| Updates/distribution | Ed25519-signed update manifests, source/hash verification, pinned runtime, packaged upgrade/lifecycle gates | Existing beta installer remains unsigned by a Windows publisher. Clean-machine WebView2 GUI acceptance remains open. Update signing does not replace publisher signing. [Runtime security](RUNTIME_SECURITY.md). |

## Repeatable stabilization gate

Run from a Windows checkout with the pinned development dependencies, pywebview and
WebView2 available:

```powershell
python tools/stabilization_gate.py --output build/stabilization.json
```

The tool accepts no existing realm/account path. It creates temporary synthetic
homes, disables external notifications/model sync, and never attaches to the owner
app. It records source commit and dirty state, isolated child logs, per-stage JSON
and overall success. A failed or timed-out stage fails the gate. Each child has a
deadline; timeout cleanup targets only that child process tree. Retain its unique
evidence directory together with the summary. A dirty-source run is development
evidence; release validation must use the final committed source.

1. Run the security, slow-client, admission/crash, damaged-record, snapshot and
   export fault matrix. Existing dedicated tests exercise failures that are unsafe
   or nondeterministic to inject into the load loop.
2. Run 30 iterations across three realms: twelve concurrent logical window readers,
   three writers, 360 reads, 90 valid writes/admissions and 180 refused protected
   writes. Verify control/skill bytes and realm-specific output contents; admission
   must drain. Export, verify and restore each realm paused with policies preserved.
3. Benchmark 30,000 historical runs and 21 threads of 1,000 messages. Report one cold
   observation separately from 12-sample warm p50/p95. Four-window timing measures
   a whole concurrent batch, not a single window or application startup.
4. Repeat the real native shared-window/Stop probe three times, then run page-work
   and owner-workflow probes. These use actual isolated WebView2 windows. The twelve
   logical readers in step 2 are not twelve native windows.

Gross-regression ceilings are intentionally above the M9 measurements: warm realm
and metadata p95 100ms, usage 500ms, unchanged poll 250ms, four-window batch 1,000ms;
one cold read 10s; concurrent soak read p95 5s. They catch large regressions, not
promise a user latency SLA. Record hardware/load context when comparing reports.
Do not raise a budget to make a failure pass without investigating and documenting
the cause. This bounded minutes-long gate is not an overnight soak, an RSS/leak
proof, or sustained live-provider load testing.

The ordinary full pinned suite, exact-source Windows CI, packaged lifecycle and
signed-upgrade gates remain mandatory. This tool supplements them; it does not
replace them. Re-run it for changes spanning admission, persistence, history reads
or desktop lifecycle; preserve focused gates for narrower changes.

## Maintainer acceptance checklist

- Review permission wording and scope behavior in a disposable realm before
  applying the intended finance policy. No personal realm was modified by this work.
- Accept the overview/navigation, keyboard and scaled-display workflows in normal
  use. Record any accessibility or hardware-specific issues explicitly.
- Confirm installed-update behavior after jobs finish, at the owner's chosen time;
  publishing must not restart the running app merely to test.
- Complete Windows publisher signing and clean-machine WebView2 acceptance before
  claiming those distribution guarantees.
- Record maintainer approval in the milestone plan. Automated checks do not sign
  off product acceptance on the maintainer's behalf.
