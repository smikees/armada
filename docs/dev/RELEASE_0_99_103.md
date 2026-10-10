# 0.99.103 — Settings startup rollback

## Incident, 2026-10-10

The owner restarted from Settings to install 0.99.102. The package verified, the new server
and scheduler started, but desktop readiness was never acknowledged. After 45 seconds the
desktop reported an initialization failure; the bootstrap restored 0.99.101 and quarantined
0.99.102. There was no package-integrity failure or evidence of lost realm data.

The readiness check incorrectly required `window.mcIcon`. Settings and other `_page_shell`
pages intentionally omit that optional helper. A native reproduction displayed a complete
Settings page with CSS and the shared font controller loaded, while `desktop_ready` remained
false. This was an existing startup defect exposed by restarting from Settings, rather than
a failure in the new font settings.

There was also a navigation race: separate JavaScript queries could observe different
documents during the local authentication redirect. A healthy pending navigation could be
mistaken for a failed saved page, causing a fallback to Overview. That sometimes masked the
readiness defect. A single snapshot now checks document completion, authentication state,
the page shell and the shared controller. Authentication/loading documents are left to finish.
Readiness still requires the authenticated server's version and instance nonce, followed by
scheduler health before committing an update. Rollback/quarantine protection remains enabled.

## Fix and regression coverage

- Check `mcFontSize.get`, loaded by `CSS_LINKS` on all first-party pages, rather than `mcIcon`.
- Log shared-controller and authenticated-identity failures without credentials or page text.
- Native startup regression restores an icon-helper-free page through real authentication,
  checks the retained route, then exercises error recovery and native close (9 checks passed).
- The signed-package upgrade gate now restarts from actual Settings and requires the successor
  to reopen Settings and acknowledge health. The previous gate visited Settings but only tested
  initial readiness on Overview, so its passing result did not cover this incident.
- The isolated Settings reproduction changes from `desktop_ready: false` to `true` with the fix.

## Release boundary

Prepared from the published 0.99.102 source in the isolated release checkout. Unfinished
capability-search changes in the original checkout are excluded. Provider defaults, package
compatibility and the installed runtime are unchanged. Full pinned tests, exact-source Windows
CI, native session/recovery and signed-package upgrade checks remain mandatory for publication.
The owner's standing unsigned maintenance-beta exception applies; Ed25519 update signing is
retained. Authenticode and clean Windows Sandbox acceptance are not claimed.

Publication includes GitHub and https://armada.stamih.com. The quarantined older package must
not simply be retried: the corrected version supersedes it through the normal update flow.

## Published and recovered — 2026-10-10

- Published normal/latest [v0.99.103](https://github.com/smikees/armada/releases/tag/v0.99.103)
  from source `103688b5c9c3410969d6f88786d5af8572001edc` through the enforced maintenance publisher.
- Full pinned suite: **3,604 passed, 5 skipped**. Both Windows Python configurations and the
  relay checks passed in [exact-source CI](https://github.com/smikees/armada/actions/runs/38072864534).
- Final native startup/recovery: 9 checks; launcher interruption recovery: 5; multi-window
  sessions: 16; exact signed-package upgrade from 0.99.102: 69 checks, including Settings restoration.
- Verified all public assets against local build hashes, the Ed25519 manifest signature,
  source commit and all 341 packaged source files. The website was backed up and published;
  public HTTPS content and the linked installer download were verified.
- Repaired the owner's quarantined installation through the normal authenticated update API,
  from 0.99.101 to 0.99.103. No active-work blockers were reported. The desktop acknowledged
  startup, the scheduler ran, the monitor reported `complete`, and the health transaction committed.
  Installed startup code matched the release, and saved preferences retained their exact hash.
  The older quarantine was not bypassed or cleared to force another attempt at 0.99.102.

| Public artifact | SHA-256 |
| --- | --- |
| `ARMADA-Setup-0.99.103.exe` | `2caefa3a73420056cc443d39677f5b7c628067bf8cc60454a7eee7e1f3596ef0` |
| `armada-0.99.103.zip` | `2b0053a6adb2c6c22a088086db782b3183c6d6213526d88db171d1b85ea55a71` |
| `armada-update.json` | `e98a18b5098681711fdbe30578c18f2bc2842cd6613aaa53bbf338c3c39fcf11` |
| `armada-update.json.sig` | `4193958eff6764d81ca689f0a50e3d0160b007fc8565268d37d9b57a3304581a` |
| Website source `index.html` | `a09462556393b56633b47a61e975b5ba78af57b9582725b96a5a01dad4b1336d` |

Local evidence: `build/publish103.log`, `build/release-evidence-0.99.103.json`,
`build/startup-recovery-103-final.json`, `build/upgrade-0.99.103.json`,
`build/public-0.99.103-verification.json`, `build/website-0.99.103-publication.json`,
and the ignored `build/startup-incident-103/` diagnostics/recovery record.
This evidence-only follow-up does not change the tagged application source.
