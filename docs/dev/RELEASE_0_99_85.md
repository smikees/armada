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

## Publication verification

Published [v0.99.85](https://github.com/smikees/armada/releases/tag/v0.99.85)
from source commit `c4e0225220deb738015d5f2c521f00f87417b403`.
The final isolated local suite passed **3,165 tests, 5 skipped**, in 424.00 seconds.
[Exact-source Windows/PHP CI](https://github.com/smikees/armada/actions/runs/37451309203) passed.
Installer staging passed five native recovery cases and 16 real WebView2 session
checks. The signed-asset packaged 0.99.84-to-0.99.85 upgrade passed 29 checks,
including complete isolated process-tree termination.
Installer SHA-256: `9b7966dd414f5502c68a8ee36e2cfd8a3ed5c11cc7a4888751d3d20d969948c7`.
