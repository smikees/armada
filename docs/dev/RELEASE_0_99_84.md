# ARMADA 0.99.84 verification

The installer Welcome and Finished panels now place “Create, empower and control
your army of agents” beneath the original ARMADA logo. The sentence uses two
centered lines, preserving readable text and margins at all four shipped scales.
The source artwork generator and committed panels are updated together. All
four sizes were regenerated and checked for text fit; the smallest and largest
were visually reviewed. Existing corner symbols and logo proportions are retained.

This release changes branding only. It adds no installed dependency or service
and does not change update execution, runtime compatibility or realm data.
The mandatory publisher verifies the final isolated suite, exact-source Windows
CI, native recovery/browser sessions and the signed packaged upgrade before
publishing. Exact-source evidence is retained under `build/`.

The [update review](UPDATE_RELIABILITY.md#remaining-improvements-reviewed-2026-10-05)
identifies further work; those recommendations are not implemented in this release.
Continuing owner-authorized unsigned beta distribution retains the existing
publisher-signing and clean-Sandbox acceptance boundaries.

## Publication verification

Published [v0.99.84](https://github.com/smikees/armada/releases/tag/v0.99.84)
from source commit `1fbd45f9c7d1d23e936667e4d334c8d714295506`. The final isolated local suite passed
**3,159 tests, 5 skipped**, in 416.19 seconds.
[Exact-source Windows/PHP CI](https://github.com/smikees/armada/actions/runs/37353425810) passed.
Installer staging passed all five native recovery cases and 16 real WebView2
session checks; the signed-asset packaged 0.99.83-to-0.99.84 upgrade passed
28 real-page/restart checks.
Installer SHA-256: `992b590d5fb15924dfada3fe96826a03a35899e5bb59cfcc7c082b0c7f5f89b8`.
