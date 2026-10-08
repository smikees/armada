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
- Full isolated release suite, exact-commit Windows CI, installer/update hashes and packaged
  native gates will be recorded after completion; this file alone is not publication evidence.

No user realm or publication job is used as a release fixture. Original failed runs remain
unchanged. Restoring job model settings and reconciling legacy remote schedules are separate
operational actions, not a claim that these failed runs succeeded.

The first release candidate passed the local isolated gate (3,334 tests, 5 skips) and current
Python Windows CI. Pinned-Python CI exposed a transient owner-read activation race. The release
was withheld, the bounded same-owner wait was fixed and tested, and the final source is revalidated
by the enforced publication workflow. No failed CI run is treated as successful evidence.
