# 0.99.123 — Protect control records and section files

First security containment release from the November stabilization review, covering
implementation milestones M1 and M2 in [the plan](STABILIZATION_PLAN_2026_11.md).
Maintainer acceptance remains separate from implementation verification.

## Changes

Broad scoped filesystem grants previously admitted writes to an agent's live job
definitions and run history. A shared control-record classification now refuses those
writes, along with conversation state, profiles, notifications and managed records.
Refusals preserve existing bytes and appear in the normal policy audit/notification
flow. Inspector grants use the same reserved names and managed-tree classification.

The agent's own Markdown memory notes remain available within owner scope. Pending
job proposals remain writable but must pass job validation and match their filename.
The broker clears claimed approval, records the actual agent as proposer and keeps
the proposal disabled. The scheduler does not enumerate pending files; only the owner
approval operation creates a live job. Read-only and scope restrictions still apply.
Builder exemption and owner APIs are preserved. No provider transport is changed.

Section asset, entry, local-page and snapshot paths previously used string-prefix
containment, admitting similarly named sibling directories. They now share the
Windows-safe relative-path primitive. Invalid traversal, drive/UNC names, alternate
streams, device aliases and links/reparse points are refused. Snapshot writes recheck
their target under the shared file lock before atomic replacement. An invalid
snapshot destination cannot be reported as a successful existing output.

## Verification

- New regressions first reproduced unauthorized control writes and section escape.
- M1 targeted access-policy, inspector, proposal and dry-run suites: 137 passed.
- M2 targeted section, content-origin, static-content and access-policy suites:
  132 passed, two symlink checks skipped because the account could not create links.
- Full pinned gate, exact-source Windows CI, native installer/session/restart and
  signed upgrade validation: pending publication procedure.
- All tests use synthetic realms. No owner app restart, live job or provider call.

The first publication attempt stopped before uploading anything: its local suite
passed 3,985 tests (6 skipped) and both Windows CI jobs passed 3,987 (4 skipped),
but a native restart probe reported `close hides main 1`. Investigation reproduced
a probe ordering race: an already-visible window satisfied the Open assertion
before the queued tray callback ran, allowing that earlier Open to arrive after
Close. The application correctly honored the newly delivered restore request.

The probe now waits for its actual Open callback to finish before testing Close;
it still fails on callback timeout or error. Three regression tests and the existing
visibility tests passed (12 total). The same controlled native race then passed all
69 restart checks. Application code is unchanged by this probe correction. The
full exact-commit release gates must pass again before publication.

## Provider and runtime review

Release preferences were reviewed on November 5 against official metadata:
[Claude Opus 5.5](https://platform.claude.com/docs/en/models/opus-5-5/overview),
[GPT-6.1 Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol), and
[Gemini 3.8 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash).
Preferences are unchanged. Actual selection still requires the connected provider's
reported catalogue; these documents do not establish an owner's CLI entitlement.

This focused patch preserves runtime compatibility. The embedded Python 3.12.10
security gap remains explicitly open as M3: Python 3.12.16 is a source-only security
release ([official advisory](https://www.python.org/downloads/release/python-31216/)).
The runtime upgrade requires its own compatibility and installer evidence.

Publication follows the existing owner-authorized unsigned maintenance-beta path.
Update manifests/packages are signed; Windows publisher signing and clean-machine
Sandbox acceptance remain unverified, as documented in [Releasing](RELEASING.md).

## Publication

Pending. Record source commit, full-suite/CI results, packaged gate evidence, signed
asset hashes and public website/download verification after successful publication.
