# `armada/updater.py`

Automatic updates for an installed ARMADA (launch plan 5.4, ADR-011).

The installed app (ADR-009) is a private Python plus this package in `<install>\armada\`. An update
replaces that one folder. Nothing else changes: the Python runtime and its packages only change with
a new installer, and the updater refuses a release that needs one (see `runtime_tag`).

**Where releases come from.** GitHub Releases on the public repo. Every release carries three assets:

    armada-update.json       the manifest: version, zip name, its size and SHA-256, the runtime tag
    armada-update.json.sig   an Ed25519 signature over the manifest's exact bytes (base64)
    armada-<version>.zip     the `armada/` folder

The manifest and signature are fetched from `…/releases/latest/download/<name>` (GitHub redirects
that to the newest release); the zip from that release's own tag, a URL the updater builds itself
rather than reads from anywhere.

**Why this is safe to do automatically (THREAT_MODEL T11).** Whoever can change what ARMADA runs can
act as the owner, with their files and accounts. So nothing downloaded is trusted until it checks
out against `PUBLIC_KEY`, compiled into the app: the manifest's signature must verify, the zip must
match the size and hash the signed manifest names, and the signed version must be newer than this
one (an old, validly signed release can't be replayed to roll someone back to a known bug). A
GitHub account compromise alone therefore can't push code to installed copies; that takes the
signing key too, which lives offline in MATCAP-private and never in the repository.

**When it's applied.** Downloading and checking happen in the background (a system job in the
scheduler, or Settings → Check for updates). The verified folder waits beside the live one as
`armada.staged\`. It replaces the live folder only when exactly one ARMADA process would be
running the old code, so no process ever runs half old, half new:

- at start-up (`boot()`), before anything else is imported — the window when the scheduler isn't
  running, the scheduler when the window isn't open;
- by the scheduler between passes, when the window isn't open and nothing is mid-reply;
- when the owner clicks *Restart to update* (the scheduler, if running, is asked to do it at its
  next quiet moment and to restart the window after; otherwise the window does it itself).

The old folder is kept as `armada.previous\` until the next update, so a bad release can be rolled
back by hand. The data folder and realms are never touched; the realm migration (2.8) runs on the
first start of the new code, as it does for any version.

**A development checkout never self-updates.** `installed()` is true only when the installer's marker
(`installed.json`) sits beside the package and there is no `.git` — so this repo keeps its git
Update & Restart and the updater does nothing at all in it.

### `installed()`

—

### `runtime_tag(requirements_text: str, python: str | None=None)`

What the runtime this code needs is: the Python minor version plus the pinned requirements. An update may only replace the package folder when the new code needs the same runtime as the installed one; otherwise it needs a new installer. Comments and blank lines don't count.

### `installed_runtime()`

—

### `auto_enabled()`

—

### `set_auto(on: bool)`

—

### `vtuple(v: str)`

—

### `newer(a: str, b: str)`

Is version a newer than version b?

### `_state_path()`

—

### `state()`

—

### `_save(**kw)`

—

### `_request_path()`

—

### `_scheduler_pid_path()`

—

### `note_scheduler(running: bool)`

The scheduler says it's up (or going down), so start-up can tell whether it's running without reading every realm's lock.

### `scheduler_running()`

—

### `window_open(port: int=8756)`

—

### `_fetch(url: str, limit: int)`

GET `url` over HTTPS, following GitHub's redirects, refusing anything larger than `limit`.

### `_latest_url(name: str)`

—

### `_asset_url(version: str, name: str)`

—

### class `UpdateError`

A release that failed a check. The message is what the owner is shown.


### `verified_manifest(raw: bytes, sig_b64: bytes)`

The manifest, if and only if it's signed by PUBLIC_KEY and well formed.

### `_safe_members(zf: zipfile.ZipFile)`

Every entry must sit inside `armada/`, with no absolute paths or `..` — a signed zip is ours, but the extraction shouldn't depend on that.

### `_version_in(folder: Path)`

—

### `staged_version()`

The version waiting in armada.staged, if a complete, checked one is there.

### `_stage(m: dict, blob: bytes)`

—

### `check(download: bool=True, fetch=None)`

Ask GitHub for the newest release; if it's newer and fits this runtime, download, verify and stage it. Returns what happened, for the Settings page and the Jobs list. Never raises.

### `check_due()`

—

### `apply_staged()`

Swap armada.staged in as the live package. Returns the version now installed, or "" when there was nothing to apply or the swap couldn't happen (tried again later; the live copy is untouched).

### `code_on_disk()`

The version of the package folder as it is on disk now — which differs from __version__ once another process has applied an update under this one.

### `request_apply()`

*Restart to update*, from the window. Returns {"applied": v} when this process swapped the folder itself (then the caller restarts), or {"waiting": True} when the scheduler will.

### `apply_requested()`

—

### `boot(mode: str)`

At process start, before the app is imported: apply a staged update if this is the only ARMADA process that could be running the old code. True when it applied (the caller re-execs).

### `scheduler_pass(telegram_busy: bool=False)`

Called by the scheduler after each pass. True means "restart this process now": either it just applied an update, or someone else did and this process is running code that's gone.

### `_restart_window(port: int=8756)`

After applying an update the owner asked for, restart the window's server onto the new code.

### `reexec()`

Start this command again on the (new) code on disk. On Windows os.execv starts a new process and ends this one, which is why the scheduler releases its locks before calling this.

### `status()`

For the window: what the updater knows, without touching the network.
