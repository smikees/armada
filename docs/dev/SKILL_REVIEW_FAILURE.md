# Skill review exit error (2026-10-09)

The Bring a link review returned only `CLI exited with code 1:`. Reproduction through the
actual sealed Claude invocation found a valid JSON terminal result with `is_error: true`,
`subtype: success`, `terminal_reason: api_error` and `api_error_status: 429`. Its `result`
contained the session-limit explanation and reset time. Stderr was empty; no web tool ran.

The process supervisor correctly recorded a failed exit. Both Claude adapter paths then
preferred this generic exit message over the structured provider refusal. The catalogue
route returned the adapter error, hiding the useful explanation already present in stdout.

`engine.claude._failure_reason` now prefers the structured refusal only when the supervisor
error exactly equals its generated nonzero-exit diagnostic. Additional stderr is retained.
Deadlines, cancellation, protocol, reader and cleanup errors remain authoritative, and a
successful JSON payload cannot turn a nonzero exit into success. Streaming errors and
nonstreaming review errors use the same rule.

Thirteen offline regressions cover both adapter paths, empty/additional stderr, quota-shaped
terminal events, host errors, false-success prevention and the catalogue review's web-only
tool boundary. A second actual invocation returned the full session-limit explanation through
`review_url`. No skill was installed, no provider connection was altered and no business job ran.

The account's limit itself is not an ARMADA defect. The review remains Claude-only; switching
an agent's model or connector does not change this internal review's provider. Retrying after
the provider's reset is the appropriate recovery for this response.

After the provider’s stated reset, the original repository completed its review successfully
through the same sealed invocation. The fix ships in [0.99.97](RELEASE_0_99_97.md).
