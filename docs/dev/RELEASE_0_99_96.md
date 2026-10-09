# 0.99.96 verification

This release lets a scoped inspector job complete its review, write its report and
notify the owner in one turn. It also adds readable blind-pair exports and a
dismiss button for the new-version ribbon. The [technical design](DRAFT_REVIEW_ARCHITECTURE.md)
and [Jobs handbook](../../armada/docs/user/jobs.md) describe the managed boundary.

## Behavior and configuration

- **Approved inspector outputs.** `write_file(path, content)` admits the running
  inspector job's owner-approved write roots plus the agent's own artifacts.
  Grants and the path are rechecked on every call, including the original spelling
  of approved roots before resolving links. Foreign agent folders, realm controls,
  memory, jobs, credentials, device aliases, traversal and reparse escapes are
  refused. Writes hold the shared file lock and replace a complete UTF-8 temporary
  file atomically. The limit is 1 MiB of actual encoded bytes. `write_draft` keeps
  its narrower own-artifacts contract.
- **Owner messages.** `notify_owner(text)` has no destination, attachment or markup
  parameters. ARMADA sends to its own linked Telegram chat, or dispatches the
  desktop notification when Telegram is unlinked. Text is limited to 1,000
  characters and two valid attempts per turn; chat links and mentions are refused.
  Failed and suppressed attempts consume the same budget. Delivery status and the
  exact text remain in the job report and persisted transcript, including when
  the provider subsequently fails. Explicit messages are independent of automatic
  job-event notification settings; the host external-notification mute is honored.
  Desktop preferences and deduplication remain in force. A dispatched desktop
  notification is a queued attempt, not proof that Windows displayed it.
- **Readable anonymous exports.** `export_dry_run_pair(..., unpacked=true)` writes
  the ZIP plus a unique sibling folder containing `A/`, `B/` and `comparison.json`.
  Folder bytes match the ZIP, and model mapping/private telemetry stay excluded
  before and after score reveal. The folder appears only after the complete tree
  is staged; interrupted exports remove their temporary tree. Export artifacts
  remain separate from temporary pair retention.
- **Dismissible update notice.** The ribbon's accessible × button persists dismissal
  for that version across polling and navigation, and synchronizes app views.
  Later versions appear again. Active update progress and errors stay visible;
  Settings still offers the normal update action.
- **Correct script exit status.** Native probing reproduced a Windows teardown race
  that could overwrite a completed script's successful exit with code 1. The native
  wrapper now checks the process signal before reading and caching its terminal
  status. Job ownership, cleanup, cancellation and isolation limits stay intact.

Inspector turns still expose no shell, web, live connector or production
job/model mutation tools. Host-managed delivery does not grant a model a Telegram
connector or arbitrary recipient. Successful writes appear in inspector history,
including approved output folders outside the agent's artifacts. Completed or
stopped turns cannot keep using the managed action broker.

## Validation

- **32 follow-up tests** cover exact UTF-8 writes, limits, atomic failure, grant
  revocation, original-root and child reparse escapes, aliases/control paths,
  foreign agents, concurrent notification limits, fixed recipients, mute/failure
  receipts, stopped turns, provider failure, artifact discovery, readable anonymous
  exports and interrupted-export cleanup.
- Related dry-run/reviewer/updater, notification/access and documentation/golden
  regressions passed. Generated references are current. Only the Jobs/Settings
  handbook search text and the new changelog block changed in HTML goldens; their
  mechanical diffs were reviewed.
- Actual Claude, Codex and Gemini CLI inspector turns each called both new tools,
  wrote the exact synthetic value and refused a foreign-agent write. Owner delivery
  was stubbed; no real messages or business artifacts were touched.
- Native WebView2 checks passed **28 desktop and 28 narrow checks**, including
  dismissal persistence, a later version, progress/errors and existing Jobs/editor
  controls. Light/dark evidence was reviewed. The one design detector pass reported
  only preexisting side-tab findings outside the changed controls.
- **6 native exit regressions** and **30 actual Node sandbox repetitions** passed
  after the process-signal fix, with no premature exits or false failures. The
  reviewer/isolation suite and then **262 process/golden/reference checks** passed.
  The additional changelog golden diff was reviewed as one exact bullet insertion.

The final enforced local release gate passed **3,437 tests with 5 skips**
in 514.72 seconds. Exact-source Windows CI passed Python 3.12.10 and current
Python 3.12, each with **3,438 tests and 4 skips**:
[CI run 37931126367](https://github.com/smikees/armada/actions/runs/37931126367).
An earlier source run hit the unchanged registry concurrency test's five-second
lock deadline. All 37 locking regressions and ten separate repetitions passed
locally; the registry also passed the CI retry. That retry exposed the separate
Node exit race. Instrumentation observed exit code 0 before the process was
signaled in all eleven attempts, and false code 1 in the eleventh. The race was
fixed in source and this final commit passed a fresh full gate and both CI jobs.
No isolation or locking test was weakened or skipped for publication.

The compiled launcher passed all **5 interruption recovery checks**, the branded
runtime passed **16 native multi-window session checks**, and the exact signed
package passed **63 native upgrade checks** from
0.99.95 to 0.99.96.

## Publication

[Release v0.99.96](https://github.com/smikees/armada/releases/tag/v0.99.96) was published at **2026-10-09T12:49:56Z**
from source commit `c8c65e3d249525b47de7f4c26895cbce1b8e1636`.

Fresh public downloads verified the Ed25519 manifest signature, all four asset
sizes/hashes against GitHub and the local build, and all
**335 packaged source files** byte for byte.

The authenticated live update check staged **0.99.96** in the running
**0.99.95** app. Its process and instance nonce were preserved;
the app was not restarted. The owner can apply it through Settings → Restart to update.

This continues the owner-authorized unsigned maintenance beta distribution.
Update manifests remain signed; trusted Windows publisher signing and clean-
Sandbox GUI acceptance remain outstanding.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| armada-0.99.96.zip | 5,528,586 | `2c83697792613854c9e9f159db2958df52f4984057946ebfea7170ce9ef7772d` |
| ARMADA-Setup-0.99.96.exe | 20,469,214 | `cf4b457df2167a6c535d3e2ae4d92156c01c00b305c8ea7b42655eb838d996ca` |
| armada-update.json | 347 | `625aedd6d8e29261a5411b89170449b97ef59b037d2ecef7e2084027a334a7ac` |
| armada-update.json.sig | 89 | `63c5ad85291084dcd45944fef3beb584df4c001a18efe088af8325cbf27aada4` |

Generated evidence remains under ignored build paths: `publish-0.99.96-final.log`,
`ci-0.99.96-passed.log`, `ci-0.99.96-failed-job.log`, `ci-lock-investigation.log`,
`ci-lock-stress.log`, `ci-0.99.96-retry-job.log`, `native-poll-probe.log`,
`native-poll-fixed-probe.json`, `node-fix-final-validation.log`,
`release-evidence-0.99.96.json`, `upgrade-0.99.96.json`,
`verification-0.99.96/result.json`, `inspector-verified-tests.log`,
`inspector-ui-0.99.96.json`, `inspector-ui-0.99.96-narrow.json`,
`inspector-provider-probe/result.json` and `staging-0.99.96-live.json`.
