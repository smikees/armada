# 0.99.91 verification

Maintenance release for the [job/lifecycle incident](INCIDENT_2026_10_08_JOBS.md).
Runtime compatibility is unchanged. Update manifests remain Ed25519-signed; the installer
continues the owner-authorized unsigned Windows beta distribution. Clean-Sandbox GUI and
trusted publisher-signing acceptance remain outstanding.

## Validation

- Synthetic tests reproduce runtime admission/fallback, model mismatch, startup retry holds,
  research evidence, known retry grouping and cooperative scheduler lease release.
- Real Windows Codex probes verified command/exec fields against generated CLI schemas.
  Desktop 0.162.0-alpha.2 and standalone 0.161.0 reproduced the locked-runtime failure;
  standalone 0.157.1 executed sandboxed commands and harmless model turns with both its default model and explicit GPT-6-Sol. The latter returned READY and a verified command-result marker.
- A real separate daemon released its kernel lease during its 60-second idle wait; Windows recycled the synthetic realm in 1.14 seconds while the daemon stayed alive. The native startup recovery probe passed all 8 checks.
- The enforced maintenance publisher passed **3,337 tests with 5 skips**, then verified
  successful Windows CI for the exact released commit on both Python 3.12.10 and current
  Python 3.12, plus the relay gate:
  [CI run 37778113187](https://github.com/smikees/armada/actions/runs/37778113187).
- The compiled launcher passed all **5 interruption recovery checks**. The staged branded
  runtime passed all **16 WebView2 multi-window session checks**.
- The exact signed package passed **63 native upgrade checks** from 0.99.90 to 0.99.91,
  including real Settings/Docs/Threads navigation, authenticated companion behavior,
  scheduler recovery, monitored restart and cleanup.
- Fresh public downloads verified the Ed25519 manifest signature, all asset sizes/hashes
  against GitHub's published metadata, and byte-for-byte contents of the changed runtime,
  UI and in-app documentation files against the released source. The public installer
  digest matches the locally built installer.
- The live application downloaded and verified 0.99.91 through its authenticated
  `/api/check-update` endpoint. It is staged; the existing 0.99.90 process and instance
  nonce were preserved. Applying the update awaits the owner's normal restart.

No user realm or publication job is used as a release fixture. Original failed runs remain
unchanged. Restoring job model settings and reconciling legacy remote schedules are separate
operational actions, not a claim that these failed runs succeeded.

The first release candidate passed the local isolated gate (3,334 tests, 5 skips) and current
Python Windows CI. Pinned-Python CI exposed a transient owner-read activation race. The release
was withheld, the bounded same-owner wait was fixed and tested, and the final source is revalidated
by the enforced publication workflow. No failed CI run is treated as successful evidence.

The final result evaluator discards model-supplied startup_failure fields; only engine
readiness can attach admission evidence. A regression test verifies a model's final block
cannot turn completed work into a claimed non-start. The second in-progress validation was
superseded before packaging to include this hardening in the exact final source gate.

## Publication

[Release v0.99.91](https://github.com/smikees/armada/releases/tag/v0.99.91) was published
on 2026-10-08 at 12:47:24 UTC from commit
`edc25aff9ef33b66159b70a15bf8c5ebe09ea9e9`.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| ARMADA-Setup-0.99.91.exe | 20,433,108 | `fe07b1cab0b59f7e9b4d31bc988cc8174680f661cc9835ed72adc27780511af5` |
| armada-0.99.91.zip | 5,482,580 | `a0f404937a2b0de7399185305f7da63d4321c6fa975006836a199382e4bb6d41` |
| armada-update.json | 347 | `d2a79e6689164ddf84d6ba02b7c8cf4bea32d9dc4a143a25bf0c157343ea125d` |
| armada-update.json.sig | 89 | `4ce3638110a44fb74389c53203df634ab561fc0960423522e6920794316077de` |

Local evidence is retained under `build/`: `publish-0.99.91-published.log`,
`release-evidence-0.99.91.json`, `startup-0.99.91-final.json`,
`upgrade-0.99.91.json`, `verification-0.99.91/result.json` and
`staging-0.99.91-live.json`. These generated artifacts remain outside source control.

## Operational handoff

The live app is now running 0.99.91 with its scheduler healthy. After the owner selected
GPT-6-Sol, both job-specific overrides were saved through the realm-bound authenticated
job API. Their original schedules and every other setting were verified unchanged.
The standalone 0.157.1 CLI passed sandbox command/model-availability probes under each job's
actual policy, and a separate synthetic GPT-6-Sol turn returned a verified command marker.
The newer desktop CLI still reproduces the upstream sandbox error; verified fallback is
working. The Finance connector inventory also passed in 13.77 seconds under its actual
grants, with the broker connector connected and no broker-data tool called. These checks
do not claim that a business delivery was rerun.

Browser authentication was unavailable during the earlier investigation, but the existing
Claude Code 2.1.289 subscription login can manage remote routines with the documented
`/schedule` command and its `RemoteTrigger` tool. An actual authenticated listing returned
15 routines, 14 still enabled. The owner approved pausing the two duplicates and then
explicitly approved pausing the other twelve. Minimal updates set only `enabled=false`.
A fresh complete server listing verified **zero enabled routines**, all 15 definitions
preserved, and unchanged names, cron expressions, prompts, folders, connectors, models,
plugin settings and session configuration. No vendor cache was rewritten and no delivery
job was rerun. ARMADA is the chosen scheduler.

Follow-up evidence remains local in `build/job-recovery-20261008/`: `model-settings.json`,
`readiness.json`, `codex-safe-command/result.json`, `claude-verify/result.json` and
`finance-readiness.json`.
See [Claude's documented routine management](https://code.claude.com/docs/en/routines#manage-routines-from-the-cli).
