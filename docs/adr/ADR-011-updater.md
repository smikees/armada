# ADR-011 — Updates: signed releases on GitHub, verified in the app, swapped in at a quiet moment

**Status:** Built · 2026-09-24 · designed and built by Opus 5.5 (launch plan 5.4) within decisions
Mihai already made: automatic by default with an off switch (ADR-005), GitHub Releases as the
channel, updates swap the package folder from a signed zip (ADR-009). Open for Mihai's review.

## Context

Installed copies (ADR-009) are a private Python plus the `armada\` package folder. Until now the
only update path was Update & Restart's `git pull`, which only works in a git checkout and trusts
whoever controls the remote. THREAT_MODEL T11: ARMADA acts as its owner, with their files and
accounts, so whoever can change the code it runs can act as the owner. Automatic updates make
that a standing channel into five people's machines, so they have to be verified, not just
fetched over HTTPS.

## Decision

**1. What a release is.** Three assets on a normal (non-pre-release) GitHub release, tag `v<version>`:
`armada-<version>.zip` (the committed `armada/` folder only), `armada-update.json` (version, zip
name, size, SHA-256, runtime tag, commit) and `armada-update.json.sig` (Ed25519 over the manifest's
exact bytes). `tools/build_release.py` builds them from a clean commit and refuses to sign with a
key the app doesn't trust.

**2. Trust.** One Ed25519 key. The public half is compiled into `armada/updater.py`; the private half
lives in `MATCAP-private/update-signing.key`, never in the repo. The updater installs nothing unless:
the manifest's signature verifies; the manifest is well formed (the zip name is derived from the
version, not free text); the zip matches the signed size and hash; every zip entry sits under
`armada/`; the code's own `__version__` equals the signed version; and that version is **newer** than
the running one (so an old, validly signed release can't be replayed to roll a copy back). A
GitHub account compromise alone can't reach installed copies: that takes the offline key too.

**3. Verification in plain Python.** `armada/ed25519.py` is RFC 8032's reference algorithm (~150
lines), checked against the RFC's test vectors and against the `cryptography` library on random
keys. No compiled dependency (which the in-place updater couldn't itself update), no new package in
the installer. A verify costs about 3 ms. Not constant-time, which only matters for signing, and
signing happens on Mihai's machine.

**4. Runtime changes need the installer.** The manifest carries a runtime tag (Python minor + a hash of
the pinned `requirements.txt`); the installer writes the same tag into `installed.json`. A release
whose runtime differs isn't downloaded. The window says a new installer is out and links to it.

**5. When it happens.** A system job (`app-update`, every 12 hours, free) checks and, if there's a
newer compatible release, downloads, verifies and stages it as `armada.staged\`. The swap (two
renames, the second undone if it fails; the old folder kept as `armada.previous\`) happens only
when a single ARMADA process could be running the old code, so none ever runs half old, half new:

- at start-up, before the app is imported (`__main__` → `updater.boot`): the window when the
  scheduler isn't running; the scheduler when the window isn't open;
- by the scheduler between passes, when the window is closed and no Telegram reply is in flight;
  it then releases its realm locks and restarts itself;
- when the owner clicks **Restart to update** (a bar under the nav, or Settings): the window swaps
  it itself, or, if the scheduler is running, asks the scheduler to do it at its next quiet moment
  and restart the window afterwards.

Any process that finds the code on disk newer than what it loaded restarts itself when idle.

**6. The switch.** Settings → App → Advanced → *Update automatically* (appconfig `auto_update`,
default on). The Jobs page's switch for the system job is the same setting. Off means nothing is
checked or downloaded until the owner uses Check for updates.

**7. A development checkout never self-updates.** `installed()` requires the installer's
`installed.json` beside the package and no `.git`. The repo keeps its git Update & Restart.

## Consequences

- **The signing key is now critical.** If it's lost, installed copies can't be updated
  automatically any more (each would need a reinstall carrying a new key). If it leaks, whoever
  holds it (and can publish to the repo) can push code to every copy. Keep a second, offline copy.
  Rotating it means a new installer.
- The installer (5.2) must write `installed.json` with `runtime = updater.runtime_tag(requirements,
  "3.12")` and must ship `support_key.txt` (the updater carries it across updates, since release
  zips only contain committed files).
- Releases must be published as normal releases; `/releases/latest/download/` skips pre-releases.
- Realm migrations (2.8) already run on the first start of new code, so nothing extra is needed.
- A release can't change the updater's own trust rules for copies that don't have it yet. A
  broken updater in a release needs a new installer to fix.
- The first real end-to-end run is the clean-machine test (5.10), once the installer exists.
  Before then it's covered by `tests/test_updater.py` (34 tests, including the release builder's
  output going through the updater) and a Windows run of the folder swap on a temporary install.
