# Testing

## Running

```powershell
cd D:\Work\Development\MATCAP
.venv\Scripts\python -m pytest -q -p no:cacheprovider                 # everything (~2–4 min)
.venv\Scripts\python -m pytest -q tests\test_realm_format.py           # one file
.venv\Scripts\python -m pytest -q -k "golden and settings"             # by name
```

Python 3.12+. `-p no:cacheprovider` keeps `.pytest_cache` out of the tree.

**Know your baseline before you change anything.** A handful of tests fail for reasons that have
nothing to do with your change — path handling that is Windows- or Linux-specific, and two golden
pages that drift (below). Record the failing set on a clean tree, then compare:

```powershell
.venv\Scripts\python -m pytest -q -p no:cacheprovider 2>&1 | Select-String "^FAILED" | Sort-Object > $env:TEMP\baseline.txt
# … make the change …
.venv\Scripts\python -m pytest -q -p no:cacheprovider 2>&1 | Select-String "^FAILED" | Sort-Object > $env:TEMP\now.txt
Compare-Object (Get-Content $env:TEMP\baseline.txt) (Get-Content $env:TEMP\now.txt)
```

No output means nothing moved. In the Linux build sandbox the baseline is 31 failures, all
OS-specific (`WindowsPath` can't be instantiated on Linux; backslash paths): 2.5's logging made the
reasons visible. On Windows most of those pass.

## Golden pages

`tests/test_golden_pages.py` serves a deterministic fixture realm (`golden_support.build_fixture`)
through a real server (`golden_support.ServedRealm`) and compares every page byte-for-byte with
`tests/golden/<page>.html`.

- **Time is frozen** at `golden_support.GOLDEN_NOW` (a Saturday evening) through `clock.freeze`,
  so weekday strips, "next run" and dates don't change with the calendar. Code that needs "now"
  must ask `clock.now()` / `clock.today()` — `datetime.now()` breaks the goldens.
- **Normalised before comparing:** the fixture's temp path becomes `REALM`, asset cache-busters
  become `?v=V` (`golden_support._SUBS`).
- **Regenerate only for an intended change**, and only after the version bump and changelog entry
  (the changelog renders into `settings.html` — regold before them and that page is stale, as
  happened in 2.1):

  ```powershell
  $env:ARMADA_REGOLD = "1"; .venv\Scripts\python -m pytest -q tests\test_golden_pages.py; Remove-Item Env:ARMADA_REGOLD
  git diff tests\golden
  ```

  **Read the diff.** It *is* the behaviour change. For a mechanical change, prove it: normalise the
  expected transformation out of both sides and check they're equal (the 2.2 and v0.99.44 commits
  did exactly this) — a character-level diff of a whole page misaligns and hides things.
- A golden that changes when nothing you touched could change it is nondeterminism, not a
  regold: find the time, order or environment it depends on. L7 (v0.99.54) was a system job
  stamping its last run with real `datetime.now()` while the page read a frozen clock — the Jobs
  page said "next run: tomorrow" relative to whatever day the suite ran.

## Guard tests — the invariants, enforced

| Test | Keeps true |
|---|---|
| `test_exception_logging.py` | no broad `except` swallows silently (2.5) |
| `test_realm_format.py` | realm format versioning and its migrations (2.8) |
| `test_realm_write_locking.py`, `test_agent_and_thread_locking.py` | shared files are written under `util.file_lock` |
| `test_dark_tokens.py` | every colour token resolves in dark mode |
| `test_js_attr_escaping.py` | no HTML-escaped value is quoted into an `onclick` (use `_J`) |
| `test_host_guard.py` | the server refuses non-local Host headers (DNS rebinding) |
| `test_threat_model_fixes.py` | the THREAT_MODEL fixes stay fixed |
| `test_addons.py` | the add-on contract, and that it matches the lists it mirrors |
| `test_docs_references.py` | docs don't reference routes, commands, files or functions that don't exist |

When one of these fails, the fix is almost never to change the test.

## Writing tests — patterns that already exist

- **A route handler without a server:** subclass `serve.Handler` with an `__init__` that sets
  `self.realm` and call the method (`_H(realm)._save_agent({...})`). See `test_realm_format.py`.
- **Over real HTTP:** `golden_support.ServedRealm(build_fixture(tmp))` — needed when the behaviour
  lives in headers or dispatch (`test_host_guard.py`).
- **"Does this write take the lock?"** Spy on `util.file_lock` and assert the path was locked
  (`test_realm_write_locking.py`) rather than re-creating the race.
- **Anything that reads the clock:** `clock.freeze(...)`, never monkeypatching `datetime`.
- **Anything that would call Claude:** pass `engine="mock"` or a fake engine; no test spends tokens.
- **Static JS:** `node --check` for syntax; assert on the file's text for patterns (see
  `test_threat_model_fixes.py`) — there is no JS test runner.
