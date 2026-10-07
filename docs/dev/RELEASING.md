# Releasing

Current procedure for the Windows beta, updated for v0.99.87. The public branch is `main`.
A release consists of the source commit, Windows installer and signed update assets on
[GitHub Releases](https://github.com/smikees/armada/releases). Website publication is separate.

## 1. Before

- The change is committed or ready, one concern per release where you can.
- The full Windows suite must pass. Investigate failures before publishing; do not treat a stale
  baseline or regenerated snapshots as proof of correctness.
- Review every added file for private realm data or credentials. Build output and signing keys
  stay outside version control.

## 2. Version and changelog

Review `armada/engine/defaults.py` against the providers' available models each release.
Keep the connected-provider filtering and provider-default escape hatch; never use a
UI seed catalogue as proof that a specific model is still supported.

1. Bump `__version__` in `armada/__init__.py` (for example `0.99.73` → `0.99.74`).
2. Add one entry at the **top** of `_CHANGELOG` in `armada/webui/changelog.py`:
   `("0.99.74", ["…", "…"])` — one string per thing the owner will notice.
   - Written for the owner, not for a developer: what changed for *them*, and why.
   - Nothing visible changed? Start with **"Internal only — nothing in the app looks or behaves
     differently."** and then say what and why anyway.
   - Security fixes say what could have happened, plainly, without drama.
   - Insert it with a small Python script that `repr()`s the string — hand-editing the file
     through tools that "smart-quote" corrupts it.
3. Update README release/download links, current provider documentation and GitHub About metadata.
   Keep historical changelog entries and ADRs historical; add a dated superseding note where needed.

## 3. Verify

1. Syntax: `python -c "import armada.webui, armada.serve"`; `node --check` each touched `.js`.
2. Regenerate the module reference: `python tools/gen_reference.py` (a test fails if it's stale).
3. Regold **after** step 2 and review every diff (TESTING.md). Editing a help page changes `docs.html` (the help index carries every page's
   text for search) — expected.
4. Full suite with the release changes in place. Record the result and any platform-only checks
   that remain unverified. Do not publish an installer while required checks fail.
5. Installer staging runs the mandatory hidden WebView2 session gate using the branded embedded
   runtime. It opens, closes and reopens Alexander through the production opener, verifies
   one-time support payload delivery after authentication and checks that cockpit Usage remains
   authenticated. Synthetic HTTP data and an isolated data folder keep live realms and providers
   out of this test. Unit tests with supplied Cookie headers cannot replace this browser gate.

## 4. Commit

```powershell
git diff -w --stat                      # the real changes; the rest is Windows line-ending noise
git add <files, by name>                # never `git add -A`
git commit -F msg.txt
```

Message: `v0.99.47 - <what, in a line>` then a paragraph on *why* and anything a future reader
would otherwise have to rediscover (a trap you avoided, a deliberate deviation from the plan, what
the tests now guard).

## 5. Ship to the running app

Windows installations live at `%LOCALAPPDATA%\Programs\ARMADA` by default.
Version 0.99.75 requires a full installer upgrade from older betas: the old runtime lacks the stable
bootstrap and timezone data. Wait for active jobs to finish, run the installer and reopen ARMADA;
verify the authenticated version endpoint. It preserves realms and settings. A private unsigned
candidate may be installed locally when the maintainer requests it, clearly recording that public release
validation is outstanding. It must not be published as the Application Control fix.

For subsequent compatible releases, do §6 and §6b first, then use Settings → Check for updates →
Restart to update. Local scripting must read the owner-protected authentication file without
printing its token:

```powershell
$b = "http://127.0.0.1:8756"
$auth = Get-Content "$env:USERPROFILE\.armada\local-auth\8756.json" -Raw | ConvertFrom-Json
$headers = @{Authorization=('Bearer ' + $auth.token)}
Invoke-RestMethod "$b/api/check-update" -Headers $headers -TimeoutSec 180
Invoke-RestMethod "$b/update" -Headers $headers -Method Post
# After restart, read the new token and check /api/update-status with the new headers.
```

Then open the pages the change touched, in light and dark mode, and check the browser console for
errors. The owned scheduler exits when an update is ready; the replacement desktop starts its successor.

A development-only check (the dev checkout on a spare port, not a live user window):
`.venv\Scripts\python -m armada serve --port 8799`.

## 6. Publish

Decided by the maintainer 2026-09-24: every release is pushed to the public repo
([github.com/smikees/armada](https://github.com/smikees/armada)) as part of the routine, not on request.

```powershell
# Authenticated through the GitHub CLI's sign-in (gh auth login), without changing git's global
# credential helper. cmd /c keeps PowerShell from mangling the quotes.
cmd /c 'git -c credential.helper= -c "credential.helper=!\"C:/Program Files/GitHub CLI/gh.exe\" auth git-credential" push origin main'
```

Before pushing, the commit must not add anything personal: no realm data, no keys (the Resend key
lives only in private hosting configuration, and never in a client build), no personal figures.
Commits are authored with the GitHub no-reply address (repo-local `user.email`). Only `main` is
pushed; `archive/private-history` stays local.

### 6b. Publish an update release (once installed copies exist — from 5.2 / 5.10 on)

Installed copies update themselves from GitHub Releases (5.4, [ADR-011](../adr/ADR-011-updater.md)).
Every release is published (the maintainer, 2026-09-24). Install the pinned runtime and development
dependencies, commit the release, push it, and wait for Windows validation to pass for that commit.
Then run the enforced publish path:

```powershell
.venv\Scripts\python tools\publish_release.py
```

It runs the isolated default suite, requires successful push CI for the exact HEAD, builds both
artifacts, and rehearses that exact installer in Windows Sandbox before publishing. A source
change during validation aborts publishing. Sandbox evidence includes the installer SHA-256,
report and first-window screenshot under build/sandbox-runs. To rehearse privately:

```powershell
.venv\Scripts\python tools\build_installer.py
.venv\Scripts\python tools\sandbox_test.py --installer dist\ARMADA-Setup-<version>.exe
```

The builder exercises interrupted-update recovery through the compiled native launcher and checks
named timezones in its bundled runtime. The default suite isolates user homes, refuses external
network connections and real provider launches, and skips live-realm checks unless --live-realm
is explicitly supplied. CI tests both the packaged Python patch version and the current 3.12 patch.
Review Python security updates before each release; refreshing the packaged runtime requires a
new installer and another Sandbox rehearsal.

No mail key belongs in either artifact. Report an issue sends through the PHP relay; see
the [relay deployment instructions](../../support-relay/README.md). The old beta sending key was
revoked and live relay delivery was confirmed on 2026-10-03.

Public installer builds now require `ARMADA_SIGNING_CONFIG`, pointing to private JSON outside
the repository. Its `command` is an argument array invoking the chosen signing provider with
exactly one `{file}` placeholder; `publisher` is the exact certificate subject. Configure SHA-256
file digests and RFC 3161 timestamping in the provider command. Keep credentials in the provider's
credential store, never in arguments or the JSON. For a certificate in the user's store, the
arguments are `signtool.exe`, `sign`, `/sha1`, the thumbprint, `/fd`, `SHA256`, `/tr`, the timestamp
URL, `/td`, `SHA256`, `{file}`. Use a certificate trusted by Windows for public distribution.

The builder signs unsigned PE files, including native Python modules, preserves valid upstream
signatures and rejects invalid ones. Inno Setup invokes the same signing helper with
`SignedUninstaller=yes`, covering its extracted temporary executable as well as Setup and
Uninstall. Every new signature must validate, match the configured publisher and carry a
timestamp. Test the signed result on a clean Windows installation with Smart App Control enabled;
signature inspection alone does not establish compliance with every managed enterprise policy.
Private local builds can use `tools/build_installer.py --allow-unsigned`; authorized maintenance
publication uses the explicit unified-gate exception documented below. `tools/sign_windows.py`
has been tested with a simulated signer; end-to-end
trusted signing remains pending the publisher account.

The stable bootstrap ships outside the replaceable package. Its protocol and dependencies form
the runtime compatibility tag; changing either requires a new installer. Existing beta clients
must install this stabilization release because their runtime lacks the bootstrap and timezone
data. Later compatible package updates recover through the journal before importing ARMADA.

Publish a normal release, never a pre-release or draft: the updater follows the latest release.
Never commit build outputs or signing credentials.

## 7. Record it

- Update "Where things stand" in `docs/LAUNCH_PLAN.md` with the version and validation evidence.
  The maintainer alone signs off acceptance steps and phase checkboxes.
- Tick tickets in `docs/dev/UI_AUDIT.md` / `THREAT_MODEL.md` if the release closed any.

## Release boundaries

The current published installer (0.99.87) lacks Authenticode signatures and can fail with error 4551
on protected machines. Version 0.99.75 used the explicit one-release exception below; 0.99.76 continues the owner's
requested unsigned beta distribution as a recorded maintenance-release deviation
([0.99.76 verification](RELEASE_0_99_76.md)); 0.99.77 follows the same recorded
maintenance distribution ([0.99.77 verification](RELEASE_0_99_77.md)). The restart fix in
0.99.78 continues it ([0.99.78 verification](RELEASE_0_99_78.md)), as does 0.99.79
([verification](RELEASE_0_99_79.md)). Version 0.99.80 continues the same maintenance distribution
([verification](RELEASE_0_99_80.md)), adding monitored update handover without changing the runtime.
The standard public build path requires publisher signing; the account is not yet configured.
Update manifests are Ed25519-signed; these are separate guarantees.
Test clean-machine installation using the sandbox procedure
above when changing packaging, launcher or runtime dependencies. Do not restart a user's running
app merely to publish a release. Announcements and website deployment need their own authorization.

### 2026-10-04: owner-authorized unsigned 0.99.75 publication

The maintainer explicitly requested publication of an unsigned version on the website after discussing
the Application Control limitation. This supersedes the signing and clean-Sandbox GUI gates
for this release only; the enforced publisher and future release procedure remain unchanged.

The existing private candidate was promoted without rebuilding: installer SHA-256
`a6968f9d98419ebb367f43b607330bf465dd1028e0586e020cc8dee49dc5672b`.
All application, packaging and launcher inputs match public commit
`c2be69684220c7a72ee10261a93ba8196510ef9a`. The isolated suite passed 3,020 tests with five skips;
23 PHP assertions and [exact-commit Windows/PHP CI](https://github.com/smikees/armada/actions/runs/37197850193)
passed. Local installation and launch preserved realms/settings, and the compiled launcher
passed all five recovery interruption points. The update manifest was rebuilt and verified
against the public commit using the existing Ed25519 key. No report credential ships in either payload.

[Release v0.99.75](https://github.com/smikees/armada/releases/tag/v0.99.75) and the website explicitly
label the installer unsigned. The release notes record both error 4551 and the unresolved
WebView2 prerequisite failure in Windows Sandbox. Neither trusted signing nor clean-VM GUI
acceptance is marked passed. Older installations need this full installer once. Website
publication replaces only its backed-up landing page; the report relay is unchanged.

Version 0.99.81 keeps the same runtime and bootstrap, and adds a mandatory native multi-window
WebView2 session gate to installer staging ([verification](RELEASE_0_99_81.md)).

### 2026-10-05: unified maintenance gate (0.99.82)

The maintainer's continuing unsigned beta distribution uses
`python tools/publish_release.py --maintenance-unsigned`. It keeps the exact-source
local suite and Windows CI, mandatory installer native recovery/session checks and
the signed-asset packaged upgrade gate. Only publisher signing and the clean-Sandbox
acceptance boundary differ, and the release notes/evidence explicitly record them.
Do not manually bypass this command to publish a maintenance release.

Protocol 2 requires a full installer from 0.99.81 and earlier. The native upgrade
gate starts the last published application payload in the current staged runtime
and exercises a compatible production API update. This does not certify the full
installer transition on a clean PC. See [the reliability contract](UPDATE_RELIABILITY.md).
The saved release evidence binds installer/package hashes, source commit and the
specific native upgrade run. Both publication paths abort on changed source.
If CI is still running after the local gate, publication waits up to fifteen minutes
for that exact push commit. A completed failure or missing successful result aborts
publication; an earlier commit cannot satisfy this requirement.
