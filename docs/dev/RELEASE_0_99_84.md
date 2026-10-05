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
