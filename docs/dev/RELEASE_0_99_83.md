# ARMADA 0.99.83 verification

The update banner previously trusted the account's last `needs-installer` result.
Full installation preserves that check history, so the newly installed release
could advertise itself until the next successful online check.

The status endpoint now compares cached availability with the running version on
every request without network access or rewriting check history. The banner also
requires the endpoint's explicit newer-version signal. Current, older, missing
and invalid cached versions cannot advertise an update. Newer verified stages,
installer requirements and operational errors remain visible.

Targeted updater/progress/hardening suite: **76 passed**. Regression checks cover
all three availability states, equal/older/missing/invalid versions, preservation
of saved check timestamps and errors, real newer installers and verified stages.
The Node browser harness verifies notification removal and preservation of errors.

The mandatory publisher runs the final isolated suite, exact-source Windows CI,
native recovery and WebView2 session checks, and the signed packaged upgrade gate
before publication. Its source-bound evidence is retained under `build/`.

This is a compatible package update from 0.99.82. Earlier versions need the full
protocol-2 installer once. No runtime dependency, background service or realm
format changes. Continuing owner-authorized unsigned beta distribution retains
the existing Windows publisher-signing and clean-Sandbox acceptance boundary.

## Publication verification

Published [v0.99.83](https://github.com/smikees/armada/releases/tag/v0.99.83)
from source commit `1726694232491a1b7f917d4fe8d0891dcac50d79`. The final isolated local suite passed
**3,157 tests, five skipped**, in 439.80 seconds.
[Exact-source Windows/PHP CI](https://github.com/smikees/armada/actions/runs/37335085571) passed.
Installer staging passed native recovery and real WebView2 session checks;
the signed-asset packaged 0.99.82-to-0.99.83 upgrade passed.
Installer SHA-256: `d2c66a3d5bdca3a572f7b780f2001e3447d008c8ca80899ec83ef1b9af061bfd`.
