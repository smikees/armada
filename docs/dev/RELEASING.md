# Releasing

The procedure every v0.99.x release has followed. Phase 5 adds the installer, the release
endpoint and the clean-machine test (8.1 folds them in); until then a release is a commit on
`master` and a restart of the running app.

## 1. Before

- The change is committed or ready, one concern per release where you can.
- The failing-test baseline is recorded (TESTING.md).

## 2. Version and changelog

1. Bump `__version__` in `armada/__init__.py` (patch: `0.99.46` → `0.99.47`).
2. Add one entry at the **top** of `_CHANGELOG` in `armada/webui/changelog.py`:
   `("0.99.47", ["…", "…"])` — one string per thing the owner will notice.
   - Written for the owner, not for a developer: what changed for *them*, and why.
   - Nothing visible changed? Start with **"Internal only — nothing in the app looks or behaves
     differently."** and then say what and why anyway.
   - Security fixes say what could have happened, plainly, without drama.
   - Insert it with a small Python script that `repr()`s the string — hand-editing the file
     through tools that "smart-quote" corrupts it.

## 3. Verify

1. Syntax: `python -c "import armada.webui, armada.serve"`; `node --check` each touched `.js`.
2. Regenerate the module reference: `python tools/gen_reference.py` (a test fails if it's stale).
3. Regold **after** step 2 and review every diff (TESTING.md). Editing a help page changes `docs.html` (the help index carries every page's
   text for search) — expected.
4. Full suite; compare with the baseline. Same set, or explain the difference in the commit.

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

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8756/restart
Start-Sleep 6
(Invoke-WebRequest http://127.0.0.1:8756/settings -UseBasicParsing).Content -match 'ARMADA <b>v([0-9.]+)</b>'; $Matches[1]
```

Then open the pages the change touched, in light and dark mode, and check the browser console for
errors. The scheduler is a separate process: a change to `scheduler.py`, `runner.py`,
`sysjobs.py` or `telegram.py` takes effect when it restarts (SCHEDULER.vbs), not on `/restart`.

## 6. Record it

- Tick the step in `docs/LAUNCH_PLAN.md` with the version and a short "done" note in the style of
  the ones above it (what, the non-obvious decisions, what tests guard it). Mihai signs off phases.
- Tick tickets in `docs/dev/UI_AUDIT.md` / `THREAT_MODEL.md` if the release closed any.

## Later (Phase 5 / 8.1)

Build the installer from the tagged commit; the clean-machine test (5.10) on a VM that has never
seen ARMADA; tag `v0.99.47`; publish to the release endpoint with a signature the updater checks
(THREAT_MODEL T11); announce to the beta group.
