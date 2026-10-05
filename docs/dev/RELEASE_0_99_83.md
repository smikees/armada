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
