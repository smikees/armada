# Agent-reported faults, 14 November 2026

Fixes following reports against 0.99.148. No live jobs are replayed and historical
accounting is not rewritten by this repair.

## Schedule loss

The editor represented only five-field cron, leaving its cron box empty for a
supported legacy cadence. Every save sent that empty box. The endpoint also
interpreted an omitted cron field as manual. Both paths could erase a schedule
when the owner changed an unrelated setting.

The endpoint now preserves cadence unless explicitly supplied. The editor shows
the saved cadence and sends cron only after a cadence control changes. Successful
saves disclose changed cadence/start windows. The before value is captured under
the mutation lock. Approval still covers the resulting schedule and critical flag.

## Late Claude events

The streaming parser raised on every event after a validated terminal result.
That exception became a process failure, replacing a completed turn's status.
Late events now produce a bounded diagnostic in `protocol_warnings`; the first
terminal output, usage and status remain intact. Late text/tools are not delivered
again. Nonzero process exits, cancellation, deadlines, malformed input and missing
terminal results remain failures. Interactive multi-turn continuations retain
their existing lifecycle handling.

## Connector evidence

Claude admission includes native/display identities and optional direct
registration aliases. The missing-server check treated those alternatives as
independent requirements. Startup admission and capability status now share
alias normalization. Missing alternative aliases no longer create false faults.
Per-turn Claude init evidence with actual callable tools supersedes preflight
failures in the run record. Preflight text explicitly describes its timing and
does not claim to be the actual runtime inventory.

## Optional extension failures

Every unavailable connector previously became a job `app_error`, even if unused.
Only required or attempted connectors now affect the job result; all startup
diagnostics remain in `connector_runtime`. The preamble tells agents not to copy
unused optional failures into missing inputs or risk gates. Explicit unresolved
audit findings, missing required inputs and risk gates still warn.

The reported local failures were independently reproduced: two obsolete Claude
Desktop extension entry points no longer existed, and the installed Windows MCP
CLI required a `serve` subcommand absent from its saved registration. This repair
does not reinstall extensions, expand their grants or change provider login.

## API fallback explanation

The reported refusal was an ordinary chat after tool use, not an approved critical
job. The owner-selected critical-only policy remains in force. Eligibility is now
explained before replay eligibility; refused-attempt metadata, usage and partial
output survive blocked fallback. Eligible critical jobs still switch once when
replay-safe, while unsafe actions, connector loss and provider budget refusals
continue to block. The setup dialog explicitly states the chat/inbox boundary.

## Regression coverage

`test_agent_reported_faults.py` and `job_schedule_harness.js` cover legacy/cron
preservation, explicit manual conversion, save disclosure, aliases, actual
runtime evidence, late-event output/usage preservation and required/attempted
connector distinctions. Existing process, job transcript, API fallback and
connector suites exercise these changes through their callers.

`tools/job_readiness_probe.py` adds native WebView2 checks for Critical-only saves
and explicit schedule-change confirmation. These checks use isolated synthetic
realms. No paid model calls or live broker sign-ins are needed.

Validation on 14 November 2026:

- Final pinned isolated Windows gate: **4,663 passed, 6 skipped**, 850.35 seconds.
- Native WebView2 journey: **14 checks passed**.
- Installed Claude CLI against the synthetic provider: API fallback succeeded;
  a simulated Console spending refusal stopped without retry. **Zero paid requests**.
- The changed settings golden differs only by the intended eligibility/replay
  explanation. Generated module references and JavaScript syntax were checked.

The first full gate exposed pre-engine reporting regressions and an obsolete
optional-connector warning assertion. These were corrected; the final gate above
passed on the resulting source. This validation does not publish or install a release.
