# 0.99.145 - Owner chat admission and visible session limits

Published on 12 November 2026 from `74884b3c2b1a181407a52fec73e65355c19abf41`.
The [GitHub release](https://github.com/smikees/armada/releases/tag/v0.99.145)
and [website](https://armada.stamih.com/) both offer this version.

Owner chats no longer inherit the unattended-work hold at the default 80%
session-use threshold. The reported Fable chat could be held at a 93% reading before reaching the
provider. Critical-job priority, its protected local slot, conversation FIFO and
API accounting remain enforced. Invalid, old or expired usage windows cannot
impose a background quota hold. Queue messages explain their blocker and persist
on the original turn, shared by standard and detached views.

Missing Codex and Gemini session rows were present but clipped: the Claude API
credit annotation created an implicit third grid row and stretched the neighboring
columns. Credit and bucket controls now sit on the title line, outside the aligned
two-row provider grids. The native test reproduces the mixed readings with API
credit and multiple Codex buckets, and checks actual visible bounds in light and
dark Armada II. The earlier test had checked DOM presence without the clipping
container and omitted credit. See the [diagnosis and regression evidence](INCIDENT_2026_11_12_QUEUE_AND_LIMITS.md).

The final publisher passed **4,510 tests with 6 skips** in 1054.77
seconds. [Exact-source Windows CI](https://github.com/smikees/armada/actions/runs/43292689076)
passed both Python jobs (**4,512 tests with 4 skips** each, in 793.34 and 751.59
seconds) and relay. Final-source stabilization passed in
**364.92 seconds**: fault injection, load, performance, three
**163-check** native thread/window cycles, page work and
**33 owner-workflow checks**.
Evidence: `build/stabilization-20261112-204120-431265`.

The freshly staged runtime separately passed **33 native
owner-workflow checks** in `build/limits-bundled-0.99.145.json`. Mixed-limit captures
and the packaged light/dark presentation-recovery captures were reviewed.
The initial stability attempt caught a synthetic approval-isolation defect; its
failed evidence is retained and the fixture correction is documented in the incident.

The installer passed native launcher recovery, DLL isolation, WebView2 sessions,
tray lifecycle, all three restart cases and presentation recovery. The signed
upgrade from v0.99.144 passed **72 checks**.
Public verification checked the Ed25519 signature, tag/manifest commit, ZIP hash,
all **496 packaged files**, installer hash and website links.
The **23,426,723-byte** installer has SHA-256
`2828b2db4c6a529f3d6cadd82021ef188d11e71d88c5db414fc1719520412d98`; the update ZIP has SHA-256
`3bf1645956d05c955af54cb33f5d0c9eb316dcbc34ab53c67ef6b88604f39197`.
Evidence: `build/release-evidence-0.99.145.json`, `build/upgrade-0.99.145.json`
and `build/public-release-0.99.145.json`.

This continues the owner-authorized unsigned maintenance beta distribution.
Trusted Windows publisher signing and clean-machine Sandbox acceptance remain
unverified. Hardware KVM switching and mixed-DPI display removal remain unverified.
The previously documented snapshot path-resolution race remains a known limitation.
No real provider/model call or business tool was used to validate this fix. The
owner app was not restarted; live realms, job controls and the temporary Windows
worker account were left unchanged.
