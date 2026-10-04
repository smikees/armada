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

Full isolated suite, exact-commit CI, packaging and public download validation: pending.

## Distribution boundaries

The runtime and stable bootstrap are unchanged; installed 0.99.75+ copies can use
the signed package update. Older versions can require a full tray quit and one
manual launch if duplicate windows or the old restart path leave an update waiting.
New instance ownership takes effect after the corrected version starts.

This continues the owner-authorized unsigned maintenance beta. Authenticode and
clean-Sandbox GUI acceptance remain unverified, and error 4551 is not resolved.
The standard public release gates remain unchanged and are not represented as passed.
