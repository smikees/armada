# 2026-10-08 job and realm lifecycle incident

## Causes and verified observations

Two daily ARMADA jobs each made four attempts. Their first shell calls failed with
`helper_unknown_error: setup refresh had errors`. The Codex Windows sandbox log traced this
to runtime read/execute validation opening an in-use `node_repl.exe` for an ACL update
(Windows sharing error 32). Login/version checks alone had passed. Both the desktop
0.162.0-alpha.2 CLI and standalone 0.161.0 reproduced the failure. Standalone 0.157.1
passed a real sandbox command and model turn using its available/default model, but did
not support the newer explicitly selected model. No sandbox was disabled.

Separately, an older execution pipeline produced the successful daily outputs. A publication
fragment matched the public file byte-for-byte, and the price-check receipt recorded accepted
delivery. Those outputs were not from the failed ARMADA attempts. Historical local schedule
metadata had migrated remote triggers; their current state was not queried. Do not relabel
failed ARMADA runs or rerun deliveries to make the calendar green. Consolidating the other
scheduler requires checking its current supported management interface after recovery.

The Finance connector startup exhausted a 25-second Claude MCP inventory timeout. A real
read-only retry completed in about 39 seconds with the admitted broker connector connected.
The inventory health-checks all configured connectors, including ungranted ones.

A calendar research job used audit findings/missing-input fields for normal calendar facts and
unannounced optional dates. ARMADA correctly held the contradictory audit claim; the prompt
contract needed separate research evidence fields. Actual audit contradictions remain held.

Realm deletion failed with Windows shell code 124. A scheduler's lifetime kernel lease was
inside the folder. The daemon adopted new realms but never released archived/removed ones.
A synthetic worker-thread Recycle Bin operation succeeded without the lease, failed with it,
and succeeded after release. The archived realm was preserved; no real realm was deleted.

## Changes in 0.99.91

- Verify sandbox execution and explicit model availability before a Codex model turn.
  An autodiscovered desktop failure may use an already installed standalone CLI only after
  verification under the same sandbox/roots/network policy. Explicit CLI paths are honored.
  Preserve the runtime decision and startup failure separately from model output.
- Hold business-job retries on typed startup failures. Keep permanent retry-series metadata
  in each new report and correlate older attempts only using exact journal run IDs.
- Use a bounded 90-second Claude connector inventory health budget; retain strict grants.
- Add optional observations/expected_unknowns evidence without loosening financial audit rules.
- Pause dispatch outside a deleting realm, await cooperative idle lease release, and preserve
  the folder with an actionable error if an old daemon does not respond. Release archived,
  unregistered and missing realms between passes and during idle waits. Stop the primary
  listener on release; prevent late polling writes from recreating a deleted realm.

## Remaining external work

The upstream Codex runtime ACL bug requires a vendor repair. CLI fallback cannot promise
availability of a model an older CLI/account does not offer. ARMADA never changes an explicit
model automatically. Check the older remote schedules before disabling a working publisher;
this code release does not prove ownership of those triggers.

## Release-gate startup race

Pinned-Python Windows CI exposed a concurrent activation failure that the local gate and
current-Python CI did not reproduce. Activation treated an empty owner lookup (including a
transient Windows read failure during atomic owner-file replacement) as a changed owner nonce,
and failed immediately. It now waits within its existing 10-second deadline for the same owner
to finish promotion. A nonempty different nonce still fails closed. Deterministic regression
tests cover both cases; the real concurrent child-server and native startup checks remain required.
