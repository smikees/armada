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

- **22 synthetic tests** cover model selection, disabled jobs, independent output
  and production history, atomic writes, path safety, inspector self-authorization,
  revocation and turn expiration, artifact reads, command approval, cancellation,
  inspector-free context compaction,
  cross-process Stop/liveness, retention, stdio MCP transport, provider configuration,
  raw result bytes/hashes and required/unsupported capture.
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

The enforced publisher also requires successful Windows CI for the exact source,
compiled-launcher recovery, branded multi-window sessions and the exact signed
package upgrade probe before publication. Build outputs, provider evidence and
screenshots remain under ignored build/dist paths.
