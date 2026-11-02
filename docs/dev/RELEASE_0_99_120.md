# 0.99.120 — Explicit tools for proposed jobs

Agent proposals previously accepted an omitted tools choice, so tool-dependent work
could reach its due date without the tools needed to produce its output.

## Changes

- Agent proposals require an explicit JSON boolean `allow_tools`. Approval displays
  and edits the choice; text-only proposals with file, connector or messaging hints
  require a warning acknowledgment. Command proposals keep their existing behavior.
- Agent guidance includes the field and directs tool-dependent drafts to choose true.
  No missing field is converted to true by validation, approval, lint or execution.
- Enabled jobs in every registered active realm are audited at startup and daily.
  Jobs pages read the current findings locally. One durable review notification per
  job uses existing approval-needed channel settings; job files remain unchanged.
- Saved job choices override agent/caller tools flags. A required output or destination
  with tools off fails before engine selection or context/model work, records a startup
  configuration failure and uses the existing failure notification without retrying.
- Approval and notification history use shared locks and atomic writes.

The warning heuristic does not block legitimate text-only work. The hard guard is
limited to required result-contract outputs/destinations and invalid boolean values.
Daily scans are local file reads, with no provider polling or page-render network work.
Five-field cron expressions recur annually even if they name a month and day, so this
release does not label them as jobs that will never run again.

## Validation

Synthetic tests cover explicit booleans, editable approval and warning confirmation,
immutable legacy jobs, notification deduplication, all-realm daily checks and pre-run
failures across Claude, Codex and Gemini without an engine/model call. Publication
evidence is recorded after the required release gates complete. Tests do not use
personal realm data or restart the owner's running application.

The clean baseline passed 3,817 tests (5 skipped). Existing permission, memory,
provider-translation and Gemini fixtures now explicitly enable tools for the tool
behavior they exercise; all four regression groups pass with their original denial
and isolation assertions intact. Approval, documentation and golden checks passed
316 tests. Synthetic browser checks covered missing choices, warning confirmation,
light/dark appearance and an empty error console. Golden changes are limited to the
Jobs help search text and changelog.

On November 2, read-only provider metadata confirmed the preferred Claude Opus,
Codex Sol and Gemini Flash entries. Defaults and provider authentication remain
unchanged. The final pinned suite and exact-source CI are enforced again by the
publisher before packaging or publication.
