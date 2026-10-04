# Provider onboarding

Claude Code, Codex CLI and Gemini through Antigravity CLI are equal connection
choices. Setup requires at least one authenticated provider, not a specific one.
Users can enable any combination and choose models per agent or job.

## Detection and sign-in

Resolve CLIs in the native Windows user's environment. Report installation,
authentication and subscription separately. Probe failure means unavailable or
unknown, not automatically signed out. Show a subscription name only if reported;
do not infer tier or price. Setup and App Settings can install or update selected
CLIs and open provider sign-in. Reuse saved logins without copying secrets into realms.
Background probes use `background.process_options()` and never open console windows.

## Model defaults

`engine/defaults.py` holds release preferences, filtered against connected engines
and real provider metadata. Seed catalogues do not prove availability. Unfamiliar
or unavailable catalogues use provider defaults, supporting older installers.
Persist the choice and release/reason when creating a team. Agents inherit realm
defaults; agent/job overrides take precedence. Existing choices are preserved.
Alexander's model settings are independent from team defaults.

## Capabilities

Resolve grants for the actual provider each run. Connector authorization for one
engine does not authorize another. Show per-provider availability and specific errors.
Gemini receives approved workspace roots even when they contain its working directory.
See [Gemini](../../armada/docs/user/gemini.md) and [memory boundaries](MEMORY_BOUNDARIES.md)
for supported features and restrictions.

## Verification

Cover every provider combination, discovery after reboot, login reuse, unsupported
features, unknown catalogues, and hidden background probes. Default tests use synthetic
realms and isolated homes, not personal deployments or live provider credentials.
