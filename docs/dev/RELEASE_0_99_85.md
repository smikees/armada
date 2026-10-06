# ARMADA 0.99.85 verification

Two detached restart monitors from failed earlier upgrade rehearsals survived
test cleanup and displayed error dialogs. They were isolated test processes,
not additional realm owners. The desktop/server singleton guard was intact.
The dialogs were closed with their window and executable identities verified;
the real desktop and scheduler were left running.

The native upgrade probe now starts suspended, joins an existing Windows Job
Object implementation before resuming, and owns every successor, monitor and
WebView descendant. Cleanup no longer depends on mutable instance/status files
or parent-process ancestry. Zero remaining test processes must be verified before
the gate accepts success. Job-assignment failure stops the suspended child;
unrelated processes remain outside this job.

The copied restart worker honors the existing external-notification mute flag
used by isolated tests. Specific errors, status and startup logs remain available.
Normal user launches retain their restart-failure dialog. This adds no service,
runtime dependency or persistent process and leaves the account-wide app guard
and independent desktop launch unchanged.

Regression tests exercise successful and failing probes whose parent has already
exited, with no status files remaining; an unrelated process must survive both.
They also cover failed job assignment and recorded errors with muted dialogs.
The mandatory publisher runs the isolated suite, exact-source Windows CI,
native recovery/browser checks and the signed packaged upgrade/cleanup gate.
Exact evidence is retained under `build/`.

The existing unsigned beta publisher-signing and clean-Sandbox acceptance
boundaries remain; this release does not claim to resolve them.
