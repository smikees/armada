# 0.99.94 verification

The Jobs and Edit job dry-run section now uses the same disclosure component as
Prompt, Output and Run history: the shared 14-pixel chevron, heading typography,
spacing, indentation and divider. Its title is **Dry run history**. Both pickers
use the existing run-output select styling; body text uses the same 13-pixel
scale as production output. The duplicate Dry run action above the sections is
removed; Start dry run remains inside the expanded section.

The obsolete shortcut handler and its production-button disabling exception are
removed. Production and dry-run execution, selection and cancellation remain
independent. User documentation follows the new disclosure entry point.

The native Jobs probe opens the actual disclosure and checks its computed styles,
shared icon, alignment and single launch control, in addition to the existing
model selection, disabled-job, Stop, history and inspector authorization paths.
Both desktop and narrow layouts are required, with light/dark visual evidence.

Runtime and provider execution are unchanged. Release-owned provider preferences
retain connected-provider filtering and the provider-default fallback. This
continues the existing owner-authorized unsigned Windows beta distribution;
update manifests remain Ed25519-signed. Trusted publisher signing and clean-
Sandbox GUI acceptance remain outstanding.

## Validation and publication

- Job-row and dry-run tests: **78 passed**. Snapshot and documentation-reference
  verification: **179 passed**. Python imports and both edited JavaScript syntax
  checks passed. Module references are current.
- The native WebView2 probe passed **16 checks at 1280 pixels and 16 at 660 pixels**.
  Light/desktop and dark/narrow rendered evidence was reviewed together; the
  shared disclosure, picker styling and body scale match the neighboring sections.
- Only two HTML snapshots changed: the handbook search text and the new changelog
  entry. Both diffs were reviewed.
- The required single Impeccable detector pass found seven existing brand.css
  warnings in untouched styles (accent borders, a capability stripe and an image
  comment). None belongs to the new rules; preserving the existing application
  appearance is part of this bounded polish request.

The final enforced publisher passed **3,372 isolated tests with 5 skips**.
Exact-source Windows CI passed on pinned Python 3.12.10 and current Python 3.12:
[CI run 37820999267](https://github.com/smikees/armada/actions/runs/37820999267).
The compiled launcher passed all **5 interruption recovery checks**; the branded
runtime passed **16 native multi-window session checks**. The exact signed package
passed **63 native upgrade checks** from 0.99.93 to 0.99.94.

## Publication

[Release v0.99.94](https://github.com/smikees/armada/releases/tag/v0.99.94) was
published at 2026-10-08T18:12:01Z from source commit
`e56be7d86f59448923e8b61c9f0ccaebee1291b8`.

Fresh public downloads verified the Ed25519 manifest signature, all four asset
sizes/hashes against GitHub and the local build, and all **331 packaged source
files** byte for byte against the release source.

The authenticated live update check staged **0.99.94** in the running **0.99.93** app.
Its process and instance nonce were preserved. Applying the update awaits the
owner's normal restart.

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| armada-0.99.94.zip | 5,503,743 | `f11a2b21858c0c3fbf718d698e7da6ca2433815b8809c7733d7be64001caddb7` |
| ARMADA-Setup-0.99.94.exe | 20,443,707 | `a987590caadbeac9d281e992a1cd5635997798bd3aad53d02cf6e511796e8631` |
| armada-update.json | 347 | `bc2ee794662890b110df71a5bcdc1deb620df8fcf65d762a97f9e83db8d7d39b` |
| armada-update.json.sig | 89 | `c8a683c979c90272d2b713b28755b00b8c95ff85a281da8acecfbfdc25f789a4` |

Generated evidence remains under ignored build paths: `publish-0.99.94-complete.log`,
`release-evidence-0.99.94.json`, `upgrade-0.99.94.json`,
`verification-0.99.94/result.json`, `dry-run-ui-0.99.94.json`,
`dry-run-ui-0.99.94-narrow.json` and `staging-0.99.94-live.json`.
