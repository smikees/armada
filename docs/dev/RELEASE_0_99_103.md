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
