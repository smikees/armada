# ARMADA 0.99.88 verification

This release combines the requested job tool-result capture and separate thread windows
with the startup/recovery fixes from the [October 7 incident](INCIDENT_2026_10_07_STARTUP.md).
The owner explicitly requested packaging and publication after reviewing the investigation.

## Scope

- Job settings opt into matching full tool names, workspace-safe raw folders and retention.
  Captures preserve the CLI result bytes received before display formatting, commit payloads
  atomically, record hashes and arguments in the manifest, and expose the folder during the run.
  Failures remain visible; required capture fails incomplete runs.
- A thread can open beside the main app in its own native window, sharing the saved conversation,
  live progress and controls. Windows stay tied to their original realm and show the agent's
  avatar and color crescent. Closing a window does not delete the thread.
- A compatible headless owner can open its desktop without replacing its server. Unsupported
  activation is visible, failed native opening preserves background service, page errors have
  recovery actions and diagnostic references, config writes require readable state, and full
  quit saves state off the UI thread with a bounded wait.

No runtime dependency or bootstrap protocol changed. Existing v0.99.82+ installations can
use the compatible signed package update; v0.99.81 and earlier still need the installer once.
The user's running desktop is not restarted merely to publish.

## Pre-publication validation

- Pinned isolated Windows suite: **3,302 passed, 5 skipped in 511.02 seconds**.
- Focused startup/recovery/authentication/restart/logging checks: **67 passed**.
- Actual hidden WebView2 thread-window probe: **21 checks passed**, including two-way messages,
  live progress, cancellation visibility, original-realm binding and close/reopen.
- Actual hidden WebView2 startup/recovery probe: **8 checks passed**, including in-place desktop
  activation, preserved ownership/authentication, both recovery navigation paths, and clean close
  with persisted window state.
- Real synthetic MCP checks for Claude Code, Codex exec, Codex app-server and Antigravity each
  produced three payloads and manifest rows, with byte hashes verified against the original stream.
  See [capture evidence and transport limits](TOOL_CAPTURE.md).
- Changed golden pages were reviewed; private realm data and credentials are not part of the
  release. Fixtures use only synthetic tool results.

The enforced maintenance publisher must rerun the pinned suite, require successful Windows CI
for the exact source commit, build both artifacts, run packaged native launcher/session gates,
and rehearse the signed upgrade from the latest published version before creating the release.
The publication gate completed successfully; final evidence is recorded below.

## Provider and runtime review — 2026-10-07

Existing provider preferences remain filtered against actual connected-provider metadata, with
the provider default retained when a preferred model is unavailable. The primary preferences
were reviewed against the official [Claude Opus 5.5 documentation](https://platform.claude.com/docs/en/models/opus-5-5/overview),
[Antigravity model catalogue](https://antigravity.google/docs/models), and the installed Codex
catalogue, which includes gpt-6.1-sol and gpt-6-sol. This release does not change existing
agent/job model choices.

Python's [3.12.15 security release](https://www.python.org/downloads/release/python-31215/)
was reviewed. Later 3.12 releases are source-only; 3.12.10 was the last with upstream Windows
binary installers. This compatible maintenance release retains the existing 3.12.10 embedded
runtime and does not claim to include those later security fixes. A runtime refresh requires
a separately validated installer transition.

## Distribution boundaries

This continues the recorded owner-authorized unsigned maintenance beta through
tools/publish_release.py --maintenance-unsigned. Update manifests are Ed25519-signed.
The installer lacks Windows publisher signing and can be blocked by Application Control
(error 4551). Clean-Sandbox installer acceptance remains unverified; native packaged upgrade
validation is mandatory. These boundaries are retained in the release notes and evidence.
The existing recoverable update journal and monitored restart remain the rollback mechanism.


## Published evidence — 2026-10-07

- Published at **19:30 Europe/Madrid** as the normal latest release:
  [ARMADA v0.99.88](https://github.com/smikees/armada/releases/tag/v0.99.88).
- Source commit: `a20cc814fb84aa59d9490937563590f6166e49aa`.
- Publisher's fresh isolated suite: **3,304 passed, 5 skipped in 499.52 seconds**.
- [Exact-commit Windows CI](https://github.com/smikees/armada/actions/runs/37658114503):
  both Python matrix jobs and the relay job passed.
- Packaged native launcher recovery: **5 interruption points passed**.
- Packaged WebView2 session gate: **16 checks passed**.
- Signed v0.99.87 to v0.99.88 upgrade: **63 checks passed**, including real scheduler leases,
  forced-exit recovery, Settings and thread navigation, companion authentication, restart-health
  acknowledgement, preserved state, and complete test-process cleanup.
- Installer SHA-256:
  `75ddc1ea8e586c41abd393db113f7f3dbd756053d751b561f34a72a34b88b6e2`.
- Update archive SHA-256:
  `cca01f1010a19d87aa44d4fb89d695378522f250f4e1171ff13fbff60e16b1ca`.
- The public latest-download URLs returned a valid Ed25519 manifest/signature pair and an archive
  matching that manifest's commit, size and SHA-256. Required capture, thread-window and recovery
  modules were present. GitHub's uploaded asset digests also match the local installer and archive.
- The owner's installed v0.99.87 updater recognized and staged v0.99.88 successfully. The same
  desktop remained ready on v0.99.87, with no restart requested; installation is left to the owner's
  **Restart to update** action.

Detailed machine-local evidence is retained under `build/release-evidence-0.99.88.json`,
`build/upgrade-0.99.88.json`, `build/publish-0.99.88.log` and `build/verification-0.99.88/`.
The maintenance installer remains unsigned and clean-Sandbox acceptance remains unverified.
