# ARMADA 0.99.79 verification

## Update state and instance ownership

The prior banner mapped scheduler existence to "running jobs". Desktop launches
could create another window attached to the same HTTP server, or choose another
port. Concurrent Windows listeners could also bind the same port through
SO_REUSEADDR, replacing each other's authentication metadata.

- An account-wide kernel-held lock now covers desktop/server startup and lifetime,
  before active-realm selection. Secondary launches activate the existing window.
  It spans realms, ports and installation folders and releases after process death.
- Windows HTTP listeners use exclusive binding. A failed duplicate bind cannot
  overwrite the first server's credential.
- Update progress identifies actual active work across realms, scheduler shutdown,
  restart, or unreadable activity. Dead/finished markers and unlocked system claims
  are not running jobs.
- Shared admission locking serializes update requests with conversation, agent-job
  and system-job starts. The scheduler checks updates before dispatch and wakes from
  its idle interval promptly. Its replacement desktop starts the new owned scheduler.
- The server can complete an idle requested update without a running scheduler.
  Restart requests use the registered port and are coalesced in-process.

## Documentation

Public guides present Claude, Codex and Gemini as independent choices, usable alone
or together. Provider-specific limitations remain explicit. User documentation,
setup guidance, specification, roadmap, schema examples and generated references
were updated. Personal deployment histories and account details were removed from
the current public documentation; Git history was not rewritten. Original internal
planning material was preserved outside the repository before public replacement.

## Verification

Focused instance/update tests: 57 passed. Scheduler, execution, system-job and
instance checks: 146 passed. Native tests cover simultaneous launches, alternate
ports/modes, crash recovery, socket ownership and immediate rebinding. Update tests
cover an idle scheduler, another realm's live work, dead/finished receipts, stale
system claims and non-default ports. JavaScript syntax passed.

Full isolated suite: **3,087 passed, five skipped**. Documentation, broad-exception logging
and rendered-page checks also passed after the final copy cleanup. Package startup and all
five native interrupted-update recovery checks passed. The local update signature, source
commit, ZIP size and SHA-256 were verified.

[Exact-commit Windows/PHP CI](https://github.com/smikees/armada/actions/runs/37219871609)
passed on Python 3.12.10 and current 3.12, plus the PHP relay checks. Public latest-release
manifest signature, commit, ZIP size/hash and installer hash were verified after publication.

## Distribution boundaries

The runtime and stable bootstrap are unchanged; installed 0.99.75+ copies can use
the signed package update. Older versions can require a full tray quit and one
manual launch if duplicate windows or the old restart path leave an update waiting.
New instance ownership takes effect after the corrected version starts.

This continues the owner-authorized unsigned maintenance beta. Authenticode and
clean-Sandbox GUI acceptance remain unverified, and error 4551 is not resolved.
The standard public release gates remain unchanged and are not represented as passed.

## Published release metadata

Release: [v0.99.79](https://github.com/smikees/armada/releases/tag/v0.99.79).
Installer and package source: `cc47b584613b06de40b3e600e7d41b64546a20fc`.
Runtime: `py3.12-abe4061a3fa70426`. Subsequent metadata edits change documentation only.
Installer SHA-256: `02c0bf49a894a7d88bcd64752f1a16c072b2287590374acb22f410038960d6c4`.
Update ZIP SHA-256: `32a4a103d05299bce43b27c101130dc50e1448db8c3a6e219640a16b3320b567`.

GitHub About states that any provider or combination is supported. Website download
links were updated through verified FTPS with a backup of the replaced index; the report
relay was unchanged. No live realm or scheduled job was modified for this release.
