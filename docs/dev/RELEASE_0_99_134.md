# 0.99.134 — Repeatable stabilization evidence

M12 released from `71159870ac08eee1d6ad41b5d7f1b6f84b08d855` on 8 November 2026.
Maintainer acceptance remains pending.
This is an internal verification/documentation release; application behavior is
unchanged. [Current contracts, gate and acceptance limits](STABILIZATION_CONTRACTS.md).

The first synthetic stress run completed 360 concurrent reads, 90 allowed writes,
90 admissions, 180 protected-write refusals and three verified paused restores
across three realms. Its fault matrix passed 233 tests. The 30,000-run history
benchmark recorded warm realm p95 4.309ms, usage 54.526ms, unchanged poll 33.507ms
and four-window batch 79.070ms; the single cold observation was 670.939ms.
Measurements are local observations under concurrent release-test load, not an SLA.
The full development gate passed in 214.7s: three native shared-window cycles
(79 checks each), six page-work checks and 16 owner-workflow checks. Evidence
validation and documentation checks passed 344 tests. The final clean committed-source
stress/native gate passed in 205.82s.

Publisher: **4,309 passed / six skipped**; both exact-source Windows CI jobs:
**4,311 / four skipped**. Packaged launcher recovery/DLL isolation, 16 session checks,
68 tray checks, 69 checks in each restart mode, 86 presentation checks and
**72 signed-upgrade checks** passed. Fresh recovery captures were reviewed. Public
signatures, package/source bytes, installer hash and matching website links verified.
Installer SHA-256: `00115e2db2bdeffb2efa25a3e30e99438b32c0030fbb903b2e9ca47fb4f5e6f6`.

Final-source warm p95: realm 4.894ms, usage 53.905ms, unchanged poll 17.817ms,
four-window batch 59.392ms. Single cold read: 578.428ms. Evidence directory:
`build/stabilization-20261108-192458-345589`.

The gate retains isolated logs and source identity, fails on missing/nonfinite or
over-budget performance evidence, and bounds child execution time. It supplements
the mandatory full pinned suite, exact-source Windows CI, packaged lifecycle and
signed-upgrade checks. Twelve concurrent logical readers are distinct from the
three repeated real native shared-window cycles.

Provider model preferences were reviewed against official documentation during
M10 on 8 November; no selection changes are included. Python 3.14.10 and launcher
protocol 2 are unchanged. Publication uses the existing unsigned Windows beta
maintenance distribution with Ed25519-signed update manifests. Windows publisher
signing, clean-machine WebView2 GUI acceptance and maintainer product acceptance
remain open. No owner app restart or live realm/provider testing.
