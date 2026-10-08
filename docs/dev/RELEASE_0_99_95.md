# 0.99.95 verification

This release adds the Feynman reviewer workflow to the draft-only tests from
0.99.93/0.99.94. [Technical design](DRAFT_REVIEW_ARCHITECTURE.md) describes the
execution boundary, private comparison state and retention. The
[Jobs handbook](../../armada/docs/user/jobs.md) explains configuration and tools.

## Behavior and configuration

- **Per-job inspectors.** An agent's owner-approved `is_inspector` grant authorizes
  review access; `job.inspector: true` selects inspector tools for that job turn.
  Chat, Inbox and unflagged jobs keep normal grants. Inspector turns omit normal
  shell/live connector configuration, and context compaction receives no inspector
  action tools. Existing inspectors must mark their review jobs in Edit job.
- **Approved Python and Node.js skill scripts.** Jobs declare their own allowed
  script entry points. Explicit owner approval fingerprints the complete skill
  bundles, job prompt, allowed skills and selected inputs. Changing any approved
  content requires reapproval. The managed `run_skill` tool runs only that set,
  with the dry-run environment and cwd, read-only staged inputs/code, and writes
  confined to draft output. No general shell is exposed.
- **Effective job metadata.** Inspector `list_jobs` resolves model, provider and
  effort through job → agent → realm inheritance, and includes agent defaults,
  configured overrides, schedule and enabled state.
- **Blind A/B comparisons.** `start_dry_run_pair` copies approved inputs once,
  captures job/context once, reserves two slots and randomly assigns A/B labels.
  Model mapping and raw telemetry remain private. `record_scores` atomically
  commits immutable scores before revealing the mapping. Anonymous ZIP exports
  allow another agent to review the pair without host identity metadata.
- **Effort overrides.** Managed launches and the Jobs dry-run selector can override
  effort for the test without changing production settings.

The isolated launcher uses Windows LPAC, no network capabilities, restricted child
creation and a kill-on-close Job Object assigned before the suspended process
resumes. Python uses a staged standard library and approved skill imports; Node.js
uses its permission mode and approved bundles. Neither inherits provider secrets
or user startup hooks. Script execution fails closed on unsupported platforms or
launcher errors. The separate owner-approved `dry_run_command` remains a trusted
command contract rather than this managed sandbox.

Pair retention removes both candidates, the shared snapshot, private originals and
mapping together after completion. Exported ZIPs remain ordinary review artifacts.
Exact selected model IDs are masked in text; binary artifacts are preserved and
writing style or self-authored metadata can still suggest identity.

## Validation

- **44 reviewer tests** cover scope, inheritance, approvals/revocation, frozen
  inputs, actual Python/Node isolation, deadlines/cancellation, pair admission,
  hidden partial results, immutable score reveal, export and retention.
- **115 process, engine and access regressions** passed. The native script lifetime
  checks measure running-process cleanup separately from disk-dependent runtime
  staging, and cancellation starts after the real child is bound.
- Actual Claude, Codex and Gemini CLI draft turns each ran approved Python and
  Node.js scripts, returned exact synthetic values and refused production writes.
- The branded embedded Python runtime passed the isolated script/import probe,
  including standard-library extension modules.
- Native WebView2 Jobs/editor probes passed **21 desktop and 21 narrow checks**,
  covering inspector scope, explicit script approval/reset, effort styling,
  independent draft history and real owned Stop. Light/dark evidence was reviewed.
- Module references are current. Only the handbook search text and changelog HTML
  golden pages changed; both diffs were reviewed. The single design detector pass
  reported existing findings outside the changed controls.

The final enforced local release gate passed **3,397 tests with 5 skips** in
475.62 seconds. Exact-source Windows CI passed both Python 3.12.10 and current
Python 3.12, each with **3,398 tests and 4 skips**:
[CI run 37834639805](https://github.com/smikees/armada/actions/runs/37834639805).

The compiled launcher passed all **5 interruption recovery checks**, the branded
runtime passed **16 native multi-window session checks**, and the exact signed
package passed **63 native upgrade checks** from 0.99.94 to 0.99.95.

## Publication

[Release v0.99.95](https://github.com/smikees/armada/releases/tag/v0.99.95) was
published at **2026-10-08T19:59:30Z** from source commit
`6d434362ff89ae35869463737102e41984791708`.

Fresh public downloads verified the Ed25519 manifest signature, all four asset
sizes/hashes against GitHub and the local build, and all **335 packaged source
files** byte for byte against the release source.

The authenticated live update check staged **0.99.95** in the running **0.99.94**
app. Its process and instance nonce were preserved; the app was not restarted.
The owner can apply it through Settings → Restart to update.

This continues the owner-authorized unsigned maintenance beta distribution.
Update manifests remain signed; trusted Windows publisher signing and clean-
Sandbox GUI acceptance remain outstanding.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| armada-0.99.95.zip | 5,523,625 | `f8081427adb321937fe818f492f3880acc321377e8c3f2946ba15f0f6552fb76` |
| ARMADA-Setup-0.99.95.exe | 20,459,000 | `6e092e6724321c106740ec80ea7b920d2c88519ca2ef35988a847c3614b2f31c` |
| armada-update.json | 347 | `4b88d859ae7daa2ebeba916859d94c1047d90d3f959177f7c31f1e6d7bb6cb1a` |
| armada-update.json.sig | 89 | `4a1c82b4267a26ae47375408e31db3ea86349b2c1cc1573c065c30401b104991` |

Generated evidence remains under ignored build paths: `publish-0.99.95-complete.log`,
`ci-0.99.95-passed.log`, `release-evidence-0.99.95.json`, `upgrade-0.99.95.json`,
`verification-0.99.95/result.json`, `dry-run-ui-0.99.95-final.json`,
`dry-run-ui-0.99.95-final-narrow.json`, `reviewer-provider-probe/result.json`,
`embedded-skill-probe/result.json` and `staging-0.99.95-live.json`.
