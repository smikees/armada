# ARMADA 0.99.76 candidate verification

This candidate addresses new-team model selection, unattended Windows probes and
Gemini's missing task-folder context. Public publication is pending.

## Behavior

- New wizard teams choose among connected engines using the policy in
  `armada/engine/defaults.py`. Models must appear in vendor metadata; otherwise
  use that provider's default and automatic effort. Save defaults before preflight.
- Alexander's settings no longer choose team defaults. Existing/adopted realm
  choices and agent/job overrides are preserved.
- Background provider, capability, quota and Git probes use CREATE_NO_WINDOW and
  STARTF_USESHOWWINDOW/SW_HIDE. Interactive sign-in actions remain explicit.
- Gemini's isolated custom agent now gets the real task folder as absolute Windows
  context. No extra filesystem permission or global setting is added. Permission
  failures retain original diagnostics and record requested tool paths.

## Verification

- Focused provider/setup/selection tests: 145 passed before the Gemini follow-up.
- Final focused defaults/background/Gemini/catalogue checks: 73 passed.
- Native Gemini reproduction: explicit fixture folder listing and read succeeded;
  asking for the current directory without explicit context guessed `/workspace`
  and failed with the user's exact headless `read_file` denial. The same request
  after the fix listed the approved Windows fixture directory and returned DONE.
  No user realm, broker connector, scheduled job, or global CLI permission was changed.
- Real Windows child process: GetConsoleWindow returned zero with background options.
- Golden HTML review: the provider-default option, new changelog and settings help
  text account for the changes; no unrelated page-layout change.
- Final isolated default suite: 3,055 passed, five skipped (386.37 seconds).
- Package checks: pending.

## Distribution

This candidate does not change publisher signing. Version 0.99.75's unsigned public
publication was a one-release exception. The normal public gate still requires
publisher signing and clean-VM GUI acceptance. Any local unsigned installer is a
private test candidate, not an Application Control fix.
