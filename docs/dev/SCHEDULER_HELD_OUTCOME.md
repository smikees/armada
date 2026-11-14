# Held-job outcome crashed the scheduler

Investigated on 14 November 2026 against installed v0.99.150; fixed in v0.99.151.

## Cause

The scheduler log repeatedly showed `KeyError: 'kind'` at the daemon's status
printing statement. Several early hold paths in `tick()` returned agent, job,
status and detail without kind. The proactive approval check introduced in
v0.99.150 made this latent reporting defect reachable before a job was due.
The reporting loop was outside the per-realm tick exception boundary: displaying
one held job terminated the whole daemon, releasing every realm lease. Restarting
repeated the same crash; this was not stale UI status or a provider limit.

## Repair

Every job outcome now starts from a shared identity, kind and schedule record,
including unreadable jobs/agents, changed approval, retry/history errors, invalid
schedules and skipped starts while prerequisites are pending. The daemon also
tolerates missing diagnostic fields rather than indexing them unconditionally.
It labels output as a job outcome rather than claiming a held job fired.

A hold remains a hold. No approval, job setting, historical attempt or live realm
file is changed by this repair, and uncertain attempts are not replayed.

## Regression coverage

Parameterized tests exercise seven early hold paths for agent and command jobs.
An integration test seals a synthetic job, changes it without approval, and drives
the real daemon, tick, leases and dispatcher across two realms and repeated
passes. Only healthy jobs execute, once each; held work stays held and leases
release on shutdown. Another daemon test accepts incomplete diagnostic records.
The default suite previously tested tick's holds and daemon exceptions separately
without driving an actual held record through the daemon's reporting loop.

Release evidence is recorded separately after full validation and publication.
