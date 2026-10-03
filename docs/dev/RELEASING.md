# Releasing

Current procedure for the Windows beta, updated for v0.99.74. The public branch is `main`.
A release consists of the source commit, Windows installer and signed update assets on
[GitHub Releases](https://github.com/smikees/armada/releases). Website publication is separate.

## 1. Before

- The change is committed or ready, one concern per release where you can.
- The full Windows suite must pass. Investigate failures before publishing; do not treat a stale
  baseline or regenerated snapshots as proof of correctness.
- Review every added file for private realm data or credentials. Build output and signing keys
  stay outside version control.

## 2. Version and changelog

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

Since 2026-09-24 Mihai's everyday ARMADA is the **installed** copy (`%LOCALAPPDATA%\Programs\ARMADA`),
so a change reaches him as a release: do §6 and §6b first, then update his copy the way Check for
updates → Restart to update does, and confirm the version:

```powershell
$b = "http://127.0.0.1:8756"
Invoke-RestMethod "$b/api/check-update" -TimeoutSec 180          # downloads, verifies, stages
$u = Invoke-RestMethod "$b/update" -Method Post                  # swaps it in (or asks the scheduler to)
if ($u.applied) { Invoke-RestMethod "$b/restart" -Method Post }
Start-Sleep 8; (Invoke-RestMethod "$b/api/update-status").version
```

Then open the pages the change touched, in light and dark mode, and check the browser console for
errors. The scheduler is a separate process: it restarts itself onto new code when it's idle (the
updater), or on its next start.

A development-only check (the dev checkout on a spare port, not Mihai's window):
`.venv\Scripts\python -m armada serve --port 8799`.

## 6. Publish

Decided by Mihai 2026-09-24: every release is pushed to the public repo
([github.com/smikees/armada](https://github.com/smikees/armada)) as part of the routine, not on request.

```powershell
# Authenticated through the GitHub CLI's sign-in (gh auth login), without changing git's global
# credential helper. cmd /c keeps PowerShell from mangling the quotes.
cmd /c 'git -c credential.helper= -c "credential.helper=!\"C:/Program Files/GitHub CLI/gh.exe\" auth git-credential" push origin main'
```

Before pushing, the commit must not add anything personal: no realm data, no keys (the Resend key
lives in `MATCAP-private\resend.key`, outside the repo, and never in it), no personal figures.
Commits are authored with the GitHub no-reply address (repo-local `user.email`). Only `main` is
pushed; `archive/private-history` stays local.

### 6b. Publish an update release (once installed copies exist — from 5.2 / 5.10 on)

Installed copies update themselves from GitHub Releases (5.4, [ADR-011](../adr/ADR-011-updater.md)).
Every release is published (Mihai, 2026-09-24). After the push, from the same commit — or all of it
in one go with `.venv\Scripts\python tools\publish_release.py`:

```powershell
.venv\Scripts\python tools\build_release.py          # signs with ..\MATCAP-private\update-signing.key
gh release create v<version> dist\v<version>\* --title "ARMADA v<version>" --notes "<changelog lines>"
```

For a release that goes to testers as an installer, build it from the same commit (Windows, with
`uv` and Inno Setup 7; [ADR-009](../adr/ADR-009-installer.md)):

```powershell
.venv\Scripts\python tools\build_installer.py     # stage, smoke-test, compile → dist\ARMADA-Setup-<version>.exe
.venv\Scripts\python tools\sandbox_test.py        # 5.10: install/open/uninstall/reinstall in Windows Sandbox
```

Attach `ARMADA-Setup-<version>.exe` to the same GitHub release. It must be built after
`armada/support_key.txt` is in place, or Report an issue only saves reports locally.

A normal release, never a pre-release or draft (the updater follows `/releases/latest/download/`,
which skips both). A release whose `requirements.txt` changed ships the installer too: copies
won't take it in place. Never commit `dist/` or the key.

## 7. Record it

- Update "Where things stand" in `docs/LAUNCH_PLAN.md` with the version and validation evidence.
  Mihai alone signs off acceptance steps and phase checkboxes.
- Tick tickets in `docs/dev/UI_AUDIT.md` / `THREAT_MODEL.md` if the release closed any.

## Release boundaries

The installer is not Authenticode-signed in this beta. Update manifests are Ed25519-signed;
these are separate guarantees. Test clean-machine installation using the sandbox procedure
above when changing packaging, launcher or runtime dependencies. Do not restart a user's running
app merely to publish a release. Announcements and website deployment need their own authorization.
