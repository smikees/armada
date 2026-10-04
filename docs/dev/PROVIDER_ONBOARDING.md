# Provider onboarding and Alexander preferences

October 4, 2026 / v0.99.76: team defaults now have their own release policy in
`armada/engine/defaults.py`, independent of Alexander. The priority is Claude
(Opus 5.5, then Sonnet 5), Codex (GPT-6.1 Sol, then GPT-6 Sol), then Gemini
(3.8 Flash, then 3.7 Flash), considering only connected providers. This is a
reviewable general-purpose release preference, not a quality ranking for every task.
A preferred model must appear in vendor metadata: Claude's live model catalogue,
Codex's CLI model cache, or Antigravity's live models response. UI seed lists do not
prove availability. Unknown, empty or unavailable catalogues select the provider's
own default with automatic effort, omitting the model/effort overrides where applicable.
The chosen values and release/reason are saved before the first realm preflight; new
agents inherit them. Existing realms, adopted realms and explicit agent/job choices
are not migrated. Revisit the policy at each release. The provider-default fallback
also lets an older installer work with an unfamiliar future model catalogue.

Background CLI probes share `background.process_options()`: CREATE_NO_WINDOW plus
STARTF_USESHOWWINDOW/SW_HIDE on Windows. Git update checks had no visibility flags;
these now use the same policy. Interactive sign-in actions remain explicit. Regression
coverage includes an actual Windows child process with no attached console.

Gemini regression: the isolated custom agent excludes the vendor's default components,
including cwd context. A native headless test reproduced the reported first-prompt failure:
`list_dir` guessed `/workspace` on Windows and was denied. Explicitly naming the approved
Windows folder succeeded. Each run now injects the real task folder plus absolute-path
instructions; the temporary CLI launch directory is identified as runtime scaffolding.
Permission errors preserve the vendor diagnostics and add the attempted file-tool path.
No wildcard filesystem permission, skip-permissions flag, or global settings edit is added.
Vendor behavior reference: https://antigravity.google/docs/cli/headless (permissions section).


October 3, 2026 update: setup accepts one or more of Claude, Codex and Gemini.
Both the Windows installer (optional unchecked tasks) and the in-app wizard can
install their vendor CLIs. Gemini uses Google's Antigravity CLI and its official
Windows installer. Missing installation and missing sign-in are separate states.
The server now includes Gemini when validating a new wizard team and sets executable
defaults for Gemini-only setups. The wizard's copy, tour and portrait match the current app.

To review the complete real flow without resetting live settings or realms, run
`python tools/review_setup.py`. It uses installed ARMADA's runtime, current working-tree
source, an independent Explorer-owned window and fresh Armada data under `build/setup-review-*`.
It retains the Windows user's HOME, USERPROFILE, LOCALAPPDATA, APPDATA and provider config
homes. Only `ARMADA_DATA_DIR` redirects the review's registry, configuration and scheduler data.
The earlier review launcher redirected vendor homes too, incorrectly reporting valid Claude
and Codex logins as signed out; that isolation bug is fixed. Installed CLI binaries and saved
vendor sign-ins are reused in place, without copying credentials. Each run's `review.json`
records its URL, PID, profile, Windows home and discovered CLI launchers.
The default realm root is inside that disposable profile. Installation and model turns
are real, with the normal provider quotas; auto-update and outgoing notifications are muted
in this review profile.

The Check step uses three equal compact cards with independent CLI and authentication pills,
original provider colors, fixed status/action rows and the supplied subscription guidance.
Signed-in engines show a Subscription type row directly below authentication. The row uses
the provider-reported plan (including ChatGPT Pro for `prolite`/`promax`) and shows
"Not reported by CLI" if unavailable; it never assumes a Gemini account is free. Signed-out
or failed-check states hide and clear the subscription row, with card/button alignment retained.
Authentication remains visible when a signed-in provider is disabled in Armada; a failed probe
is displayed as unavailable rather than falsely reporting a sign-out. The welcome copy and
tagline now use the October 3 wording. `--resume <review-folder>` preserves an unfinished test.

Native Windows verification on October 3 found Claude 2.1.286, Codex 0.160.0 and Antigravity
1.2.16 in their real per-user installations. Codex and Gemini reported signed in. Claude's
official `auth status --json` returned `loggedIn:false`, `authMethod:none` from both the Windows
home and checkout; the live installed Armada also reported that state. The review now agrees
with those authoritative checks, rather than hiding existing credentials in a disposable home.
Further read-only inspection through the native Windows process confirmed an empty Claude
engine-login record: no access token, no refresh token, expiry zero. This explains why the CLI
cannot recognize or renew a saved engine login; the cause of its clearance is not established.
No account credential was copied, changed or included in the diagnostic report.
Focused verification: 112 provider/review/documentation checks passed, plus 24 provider/auth
checks. The native Check page was reviewed with all three cards aligned and original colors.
Subscription follow-up: 111 focused checks passed; Settings plan rendering and signed-in,
signed-out, disabled-provider, unreported-plan and failed-refresh wizard cases were verified.

September 28, 2026. Implements Mihai's request for one or both providers during setup and
connection management after setup. Source implementation; installed-app acceptance remains open.

## Behavior

- Setup and Settings → App share connection controls for Claude and Codex.
- Connect reuses a valid CLI login or starts the official browser flow (`claude auth login
  --claudeai` / `codex login`) without a console. Credentials remain with the provider CLI;
  Armada stores connection preferences and observed availability, never tokens or OAuth URLs.
- Status refreshes while visible and when returning to the app. Incomplete login expires after
  ten minutes; retry is available. An OAuth callback cannot undo an explicit Disconnect.
- Disconnect applies across Armada's realms and blocks new provider runs. It preserves shared
  CLI credentials, existing in-flight work and saved agent/job models. Reconnect restores access.
- Model choices use the last observed usable connections; rendering never invokes a CLI.
  Existing unavailable selections remain visible and calls explain how to reconnect. Legacy
  realms retain their old provider list until the first app connection observation.
- Setup requires at least one usable provider. A Codex-only realm inherits Codex defaults and
  reruns preflight after setting them so the scheduler cannot retain an initial Claude hold.

## Alexander

App → Advanced stores model and effort across realms, independent of realm defaults.

| Automatic selection | Model | Effort |
|---|---|---|
| Claude alone, or both providers | Claude Opus 5.5 | Medium |
| Codex alone | GPT-6 Sol | Medium |
| Neither | Actionable connection error | — |

Explicit overrides persist through disconnect and are never silently replaced. Effort choices
respect cached Codex model metadata. An unavailable account model produces a message directing
the owner to Advanced. Alexander retains the same prompt, context, validated action cards and
no-tool execution policy. Usage records the selected model.

The settings panel introduces Alexander's role. Both selectors label their automatic option
**Automatic (default)** so owners can restore defaults without explanatory model copy in the panel.
Mihai requested Medium for Claude and approved the testing plan on September 28.
This refinement passed 156 focused checks, including all 20 page goldens and documentation
references; the provider JavaScript syntax check passed.

Sol/Medium is the initial recommendation for responsive support with reasoning over app state,
logs and proposed actions. OpenAI's [model selection guidance](https://developers.openai.com/api/docs/guides/model-selection)
supports this balance; this is a product default, not an Armada-specific benchmark result.
Official [Codex authentication](https://learn.chatgpt.com/docs/auth) owns browser login.

## Verification and remaining acceptance

Final regression run: **2,519 passed, 2 skipped in 183.23 seconds**, including the 20 rendered
page goldens. JavaScript syntax checks and `git diff --check` passed.

Automated coverage includes all four connection combinations, connection persistence, unchanged
agent models after disconnect, blocked runtime calls, official login arguments, late OAuth
completion, abandoned/failed login, Alexander defaults and overrides, account effort validation,
and the Codex-only first-realm preflight correction.

An isolated browser profile with simulated provider authentication verified setup progression,
connecting both providers, disconnect/reconnect model updates, saving an Alexander override,
and persistence after reload. No live realms, credentials or paid model calls were used.

Before launch, use a fresh Windows Sandbox installation for real provider browser callbacks,
CLI missing/outdated states, cancellation and retry, then test the first job and artifact with
one provider at a time. Installer copy is updated; the installer has not been rebuilt or tested
in Sandbox for this change. Launch ticket 6.5 remains open for a new user's measured first value.

## Immediate CX walkthrough — September 28

At Mihai's request, prepared a separate current-working-tree installer in
`build/setup-cx-5xfga7nt/` and launched its `Start Armada setup test.wsb`. The snapshot includes
267 tracked and non-ignored new package files, checked against `source-manifest.json`, with the
existing pinned embedded runtime and dependency versions verified. Bundled-runtime import and
first-run HTTP smoke checks passed; Inno compilation succeeded. This is a local CX package,
not a published release or a commit. SHA-256:
`33ae509cd1404a00db6d1d46d47b9c03fd678ffeca0096c009a7382c2b9a594c`.

The Sandbox configuration requests the interactive installer at its welcome screen. Only the package (read-only)
and that run's results directory are mapped. Auto-update is disabled within the disposable
Sandbox profile to preserve this test snapshot. No host credentials or realms are copied.
Installer logs and launcher status are in the run's `results/` folder. The user can test the
current entire journey immediately; the first-work step still produces a streamed brief.
Real sign-in and first-artifact acceptance are not claimed by these smoke checks.

The user confirmed Sandbox reached the Windows desktop, but its automatic installer launcher
did not run (no guest status report). Manual entry point inside Sandbox:
`C:\armada-cx\ARMADA-CX-Setup.exe`. To unblock immediate setup testing, launched the same staged
app in a separate native window, **ARMADA — Setup CX test**, with an empty `local-profile/`
under the run directory. HOME, USERPROFILE, CODEX_HOME and CLAUDE_CONFIG_DIR are scoped to
that child; provider API-key environment overrides are removed. Its welcome page was verified
at `http://127.0.0.1:57641/`. The local copy is for wizard CX; it does not validate installation.

## CX feedback fixes — September 28

Mihai's walkthrough stopped at provider setup. The isolated launcher had not created Desktop or
the explicit CODEX_HOME directory: the native folder picker and Codex CLI therefore failed before
authentication. The test launcher now creates those folders. The application also starts the picker
in an existing directory and creates an explicitly configured Codex home before login.

- The first screen contains only the full logo, requested tagline, and **Start setup**.
- Optional unchecked installer tasks install Claude, Codex, or both using the vendors' official
  Windows installers. The same helper supports Install/Update in setup and App settings. Downloads
  require internet; failures leave a retry and installation guide. Installation uses owned process
  supervision, including deadline and descendant cleanup.
- Provider cards show CLI installation separately from authentication. Missing/outdated CLIs must
  be installed/updated before **Sign in (opens browser window)** becomes available. Native installs
  take precedence over stale npm shims. Disconnect appears only for a confirmed connection.
- Login failures and timeouts are visible. Pending logins can be cancelled or their validated official
  authorization URL reopened. URLs remain in memory only; CLI output is drained without persistence.
- Codex configuration failures are distinguished from signed-out status; malformed Claude login
  booleans are rejected. Existing-realm adoption can establish the app root before opening the realm.

The first regression run after these fixes passed **2,539 tests, 2 skipped** (178.67s).
Real vendor installation and browser callbacks remain acceptance checks; no live credentials or
realms were changed by automated tests. Ticket 6.5 remains open.

Follow-up checks after timeout cleanup, auth parsing and help-copy refinements: **105 provider/setup
tests passed**, plus **185 process lifecycle, page golden and documentation-reference checks passed**.
Both JavaScript files pass syntax checks. Regolded the intentionally changed Settings controls and
Getting started help content; reviewed those diffs. The rebuilt local package is
`build/setup-cx-xd45lydh/bundle/ARMADA-CX-Setup.exe` (269 manifest-verified package files), SHA-256
`7cc8f3e9dc9dbc79164b3e90643efe70daec318818f1b9e19dae852957ff00a0`.
Inno compilation and bundled-runtime first-run smoke checks passed. Browser verification of the
packaged app confirmed the minimal welcome screen, Start setup transition, installed-but-outdated
Claude, installed-but-signed-out Codex, exact sign-in label and pointer cursor on existing-realm
selection. Screenshots: `D:/Work/armada-setup-welcome.png` and `D:/Work/armada-setup-providers.png`.

## Roster and second CX feedback — September 28

Mihai selected the **prepared starter profiles**: Marcus, Graham, Ricardo, Wedgwood, Aristotle,
Galen, Palladio and Ibn Battuta. `starter_profiles.json` bundles the full Cabinet documents from
`templates/cabinet`; owner references use `{owner}`. Matching existing portraits were copied for
Marcus, Aristotle, Galen, Palladio and Ibn Battuta. The other profiles currently use the bundled
portrait set. Only chosen profiles are copied to a new realm; future app updates leave those copies
alone. Company and Crew keep simpler starter roles until their full profiles are authored.

Team now owns the required owner/realm names. Both must be entered before building a team. Roster
profiles can be dragged or added with a keyboard-accessible button; View more opens a native dialog
with the full profile and configuration defaults. Custom agents can supply a name, role, profile,
portrait, mission, soul and tenets. Draft selections persist when switching realm types. New agents
inherit the realm model/effort, and new realm defaults resolve the same preferences as Alexander,
including explicit app overrides. Folder now holds the existing-realm action. Check reports provider
versions plus Python (included in the installer) and WebView2. The greeting is smaller and single-line
at the desktop viewport; wizard content is unboxed with a subtle divider.

Two observed failures reproduced and corrected:

- The Claude installer could not find `Get-FileHash` because an inherited PowerShell module path hid
  Windows PowerShell's Utility module. Explicitly loading that module fixed the official installer:
  **Claude 2.1.283 installed successfully in the isolated test profile**. Failure diagnostics now reach
  the app log. No shared CLI credentials or live realms were changed.
- Realm creation printed a Unicode arrow to cp1252 stdout after writing files, then reported failure.
  Scaffolding now logs completion without depending on stdout. Regression coverage uses cp1252 with
  non-ASCII realm/agent/owner names and verifies full profile text, avatars and safe custom fields.

Focused backend checks: **68 passed**. An isolated browser walkthrough using simulated provider
connections verified required names, drag-and-drop, the personalized Marcus modal, custom-agent
creation and progression to Capabilities. The created realm had Opus 5.5/Medium defaults and the
expected owner and custom profile text. No model turn was run. Mechanical UI checks found only
existing accent-border rules and an `<img>` example inside a CSS comment; no new broken image.

Final regression: **2,551 passed, 2 skipped in 193.89 seconds**; JavaScript syntax and diff checks
passed. Rebuilt test installer: `build/setup-cx-8d21b_j3/bundle/ARMADA-CX-Setup.exe`, with 277
package files and successful embedded-runtime smoke checks. SHA-256:
`1596a0cabebcd90f6092ac8a9324eab157d9635bc0374a7e46df689a00cfa03b`.
The native **ARMADA — Setup CX test** window was refreshed, retaining the previous isolated
profile and Codex login. Its real status shows Claude 2.1.283 (signed out), Codex 0.157.1 (signed
in), Python 3.12.10 included and WebView2 153.0.4234.48. Packaged UI verified the step placement,
name gate and all eight portrait loads. Proof: `D:/Work/armada-team-roster-final.png` and
`D:/Work/armada-welcome-refined.png`. No published release or live-app restart was performed.
