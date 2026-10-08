# 0.99.93 verification

Draft-only job tests and inspector agents. The maintainer chose temporary drafts,
read-only production inputs, no publication/notifications and explicit dry-run
commands for scripts. Runtime compatibility is unchanged. Update manifests are
Ed25519-signed; the installer follows the existing owner-authorized unsigned
Windows beta distribution. Trusted publisher signing and clean-Sandbox GUI
acceptance remain outstanding.

## Behavior and boundaries

Jobs and Edit job expose a separate Dry runs section with an explicit available
model, Start, Stop and historical output selection. Disabled jobs can be tested.
The saved production configuration, schedule, retries, calendar and job history
remain independent. Token accounting records tests separately.

Each invocation snapshots its job and stores drafts, final answer, transcript,
run state and optional tool capture under the realm's
`.armada/dry-runs/<agent>/<job>/<run-id>/` tree. Housekeeping prunes the whole
finished test after its original retention period: seven days by default,
configurable from 1 to 365 days. Active owned tests survive pruning; durable Stop
requests reach workers in another process.

Model tests expose only ARMADA's scoped input-read and draft-write MCP tools.
They use saved files and previously captured connector responses. Live connectors,
shell commands, ambient plugins/hooks and publication tools are unavailable.
This tests draft quality; it does not replay the production tool chain. Command
jobs require a user-saved draft-only command, authorized on this machine and
fingerprinted against its definition/environment. The trusted script must honor
that contract; no operating-system sandbox guarantee is claimed. Unsupported
command tool capture is recorded, and require_capture fails the test without
interrupting its draft execution.

Configure → Advanced → Is inspector requires both the portable flag and an
owner-approved machine-local grant. Each call checks revocation. Inspectors can
test any realm job, choose an available model, read recorded output artifacts
and review dry-run files. They can write only their own review artifacts. They
cannot authorize themselves, change production jobs/models, run production jobs
or edit other agents' outputs. Realm/path checks reject traversal, Windows aliases
and linked files/folders. Two simultaneous tests per realm and four launches per
inspector turn bound costs.

## Validation

- **23 synthetic tests** cover model selection, disabled jobs, independent output
  and production history, atomic writes, path safety, inspector self-authorization,
  revocation and turn expiration, artifact reads, command approval, cancellation,
  inspector-free context compaction,
  cross-process Stop/liveness, retention, stdio MCP transport, provider configuration,
  raw result bytes/hashes and required/unsupported capture.
  Metadata readers and writers share a lock; only transient PermissionError is
  retried, with a bounded delay. Corrupt state and persistent denial still surface.
  The scoped stdio bridge is also exercised with Unicode file names and content;
  the existing branded embedded pythonw runtime successfully initializes it.
- The native WebView2 Jobs probe passed **15 checks at each of 1280 and 660 pixels**.
  It exercises actual browser controls with a deterministic engine through the real
  run coordinator: missing-model feedback, changing models, Stop, history selection,
  unchanged production definition, navigation recovery, bounded layout and saving
  inspector authority. No business job or real realm is used.
- Light/wide and dark/narrow visual confirmation passed. Screenshots render the
  native WebView2 DOM in an isolated headless Chromium profile, because occluded
  WebView2 preview capture can wait indefinitely for a compositor frame.
- The Impeccable detector was run once on all changed UI files. Its one warning
  refers to the existing result-status accent border in pages.py, outside this
  feature's edits. The incumbent appearance is preserved.
- Actual installed Claude, Codex and Antigravity/Gemini CLIs each made real scoped
  MCP calls, wrote the expected synthetic draft and refused a production-file
  write. Production fixture bytes remained identical. The probes caught Claude
  authentication flags and Gemini tool discovery issues before release.
- Release-owned provider preferences were reviewed and are unchanged. Connected
  provider filtering and the CLI-default fallback remain in place.
- Module references and HTML snapshots were regenerated. Every changed snapshot
  was reviewed: the new shared script, handbook text and changelog account for
  all differences. JavaScript syntax and the full pinned isolated gate are required.

The first full gate found one error-handling accounting violation in the broker:
its returned MCP errors intentionally avoid logging private input data. The handler
now documents that exception explicitly. All 3,364 other tests passed; the enforced
publisher reruns the complete suite on the final commit after this correction.

A subsequent concurrent local gate found a genuine Windows sharing race opening
run.json during replacement. The test completed with correct output, but polling
raised a transient access error. Coordinated metadata reads/writes and a bounded
PermissionError retry fix the application path. A synthetic regression covers both
transient recovery and persistent/corrupt-state failure without hiding either.

The enforced publisher also requires successful Windows CI for the exact source,
compiled-launcher recovery, branded multi-window sessions and the exact signed
package upgrade probe before publication. Build outputs, provider evidence and
screenshots remain under ignored build/dist paths.

## Publication

[Release v0.99.93](https://github.com/smikees/armada/releases/tag/v0.99.93) was
published at 2026-10-08T16:51:55Z from source commit
`7454f631c7f273faf6215e49c4226a8f404911cd`.

- The final enforced publisher passed **3,370 isolated tests with 5 skips**.
  Exact-commit Windows CI passed on pinned Python 3.12.10 and current Python 3.12:
  [CI run 37810543848](https://github.com/smikees/armada/actions/runs/37810543848).
- The compiled launcher passed all **5 interruption recovery checks**. The branded
  runtime passed **16 native multi-window session checks**.
- The exact signed package passed **63 native upgrade checks** from 0.99.92 to
  0.99.93, including authenticated real-page navigation, scheduler/restart recovery
  and cleanup.
- Fresh public downloads verified the Ed25519 manifest signature, all four asset
  digests/sizes, the local installer digest and all **331 packaged source files**
  byte for byte against the local tracked source.
- The newly packaged embedded pythonw runtime made real stdio MCP requests:
  initialize/list, exact Unicode draft write and input read, and refusal of a
  production write. Original production fixture bytes remained unchanged.
- The live authenticated update check staged **0.99.93** in the running **0.99.92**
  app. Its process and instance nonce were preserved; applying it awaits the
  owner's normal restart. No business job or external delivery was run.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| armada-0.99.93.zip | 5,503,720 | `747ab451486008cf1771bd3531cb089abb0920aeafc1cee40d7ddde8fe62b5ab` |
| ARMADA-Setup-0.99.93.exe | 20,449,494 | `eb4ff1dd2d9e4501bb9470d19460fb06b3ac1d9d9419685307ecc5377738147c` |
| armada-update.json | 347 | `5f207897a04535f685418824c7dd15b38bf4b59c0f64bee4dfe88af9f699c659` |
| armada-update.json.sig | 89 | `ce5b57e783c4261928e0aeada438bb0eb2eb6cdaa7cf4cdf13c46bb86bdfff91` |

Generated evidence remains under ignored build paths: `publish-0.99.93-complete.log`,
`release-evidence-0.99.93.json`, `upgrade-0.99.93.json`,
`verification-0.99.93/result.json`, `packaged-managed-0.99.93.json`,
`managed-tools-probe/final-result.json`, `dry-run-ui-0.99.93.json`,
`dry-run-ui-0.99.93-narrow.json` and `staging-0.99.93-live.json`.
