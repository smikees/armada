# ADR-009 — Installer: a private Python runtime in a per-user Inno Setup installer

**Status:** Accepted · 2026-09-24 · written by Opus 5.5, accepted by Mihai: option B, unsigned for
the beta, Inno Setup (launch plan 5.2)

## Context

Today ARMADA runs from a git checkout: `.venv` + `MATCAP.vbs` + `SCHEDULER.vbs`, with hard-coded
`D:\Work\...` paths, and Update & Restart is a `git pull`. That works on one machine. The beta
goes to about five invited Windows users (ADR-005, ADR-006) who don't have Python, git, or any
reason to learn either.

What the installer has to deliver, from 5.2 and what 5.3–5.5 built on:

- the app and a Python runtime to run it, with no admin rights and no Python pre-installed;
- the WebView2 runtime (pywebview's window) — built into Windows 11, nearly always present on
  Windows 10 via Edge; check and point to Microsoft's installer if missing;
- a check for Claude Code (not bundled — Anthropic's software, the user's own account), with a
  link to install it when it's missing;
- Start menu + desktop entries for the window, and a **logon entry for the scheduler** (moved here
  from 5.5) so jobs run after a reboot without opening the window;
- the licence and third-party notices (5.9, done);
- a shape the auto-updater (5.4, ADR-005: automatic by default) can update in place.

The code already cooperates: the window starts the scheduler (`schedsvc`), a first run lands on
the welcome page (5.3), and the scheduler is found by its lock, not by how it was started.

## Options

**A. PyInstaller one-folder `.exe`, wrapped in Inno Setup.** The standard answer. But PyInstaller
bootloaders are a well-known source of antivirus false positives, and an unsigned one more so.
Every update is a full rebuild and a full reinstall. The scheduler spawn (`python -m matcap
schedule`) has to become `ARMADA.exe schedule`, a second code path that the dev setup never runs.

**B. The python.org *embeddable* Python + the app source + pre-installed wheels, wrapped in
Inno Setup (recommended).** The installer copies a private Python 3.12 (a zip python.org
publishes for exactly this), the `matcap` package, and site-packages built at release time, to
`%LOCALAPPDATA%\Programs\ARMADA`. The launchers are `pythonw.exe -m matcap app` / `schedule`,
which is what runs today, so there's no second code path. An update replaces one folder
(`matcap\`) from a signed release zip, with no reinstall and no UAC prompt. Nothing is compiled,
so there's no bootloader for antivirus to flag.

**C. MSIX.** It needs a signing certificate before it will install at all. Its container
virtualises writes to `%USERPROFILE%` (where `~/.matcap` lives), and it's awkward about
long-lived background processes like the scheduler. Wrong fit.

**D. Bootstrap with `uv`** (the installer installs uv, then `uv tool install armada`). This makes
for a tiny installer and easy updates, but it needs the network at install time, puts a
third-party tool in the path of every install and update, and gives the least control over
what's on the machine. Good for developers, not for five invited non-developers.

## Decision

**B.** Concretely:

1. **Per-user, no admin:** install to `%LOCALAPPDATA%\Programs\ARMADA`; Start menu and desktop
   shortcuts to `pythonw.exe -m matcap app`; the scheduler at logon via
   `HKCU\...\Run` → `pythonw.exe -m matcap schedule`. Uninstall removes the program folder and
   those entries, **never** `~/.matcap` or any realm (the user's data; the uninstaller says so).
2. **Build:** a `tools/build_installer.py` that downloads the pinned embeddable Python, installs
   the pinned wheels into it, copies `matcap/`, `LICENSE`, `THIRD_PARTY_NOTICES.md` (with the
   package table regenerated from what was bundled), and runs Inno Setup's compiler. The output
   is `ARMADA-Setup-<version>.exe`.
3. **Checks at the end of install:** WebView2 present, `claude` found. Each missing piece gets a
   plain sentence and a link, not a failure: the app's own sign-in bar and welcome page take over
   from there.
4. **Updates (5.4):** the release is the installer *and* an app zip plus its signature. The
   updater downloads the zip, verifies it (THREAT_MODEL T11), swaps `matcap\` beside the running
   one, and restarts. A dependency change ships as a full installer instead, which is rare.
5. **Signing:** unsigned for the invited beta. Windows SmartScreen will say "unrecognised app"
   once per user, and the beta invite tells them what to click. A code-signing certificate (a
   yearly cost) is a public-release decision.

## Consequences

- **Prerequisite:** the embeddable Python has **no tkinter**, and `routes/realm._pick_folder` uses
  it. Replace it with pywebview's native folder dialog (`window.create_file_dialog(FOLDER_DIALOG)`),
  which is better anyway (the real Windows picker, parented to the app window). It needs a small
  bridge, because the picker is asked for over HTTP. This is a Sonnet task, done before the first
  build.
- `SCHEDULER.vbs`, `MATCAP.vbs` and `cabinet-up.ps1` become dev-only conveniences, and so does
  Update & Restart's `git pull`: the installed app updates through 5.4 instead.
- The installed layout gives `schedsvc._REPO` a new meaning (the install folder), but the same
  code, because it's computed from the package location.
- Nothing here blocks macOS later (ADR-006): the source-plus-private-runtime shape carries over
  to a `.app` bundle.

## Decided by Mihai (2026-09-24)

B; unsigned for the beta; Inno Setup. The folder-picker prerequisite shipped in v0.99.53. The
internal names became `armada` before the first build ([ADR-010](ADR-010-internal-rename.md)):
read `matcap` above as `armada`, and `~/.matcap` as `~/.armada`.
