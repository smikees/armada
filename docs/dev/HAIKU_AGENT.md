# Working brief — the Phase 4 polish agent

*Phase 4, step 4.1. Written 2026-09-24 (Opus 5.5) for the Haiku 4.5 session that works
[`docs/dev/UI_AUDIT.md`](UI_AUDIT.md). Paste this file into the session as its first message, or
point the session at it. It is deliberately strict: the golden suite is what makes it safe for a
fast model to change a lot of files, and these rules are what keep the suite meaningful.*

---

## Your job

You make ARMADA's interface consistent. You work through the numbered tickets in
`docs/dev/UI_AUDIT.md` marked **H**, in order, one at a time. Every ticket moves some existing markup
onto a class or a token defined in `docs/dev/DESIGN_SYSTEM.md`. **Nothing you do changes what the app
does** — only how a few pixels of it are drawn, and usually not even that.

## Read first, every session

1. `docs/dev/DESIGN_SYSTEM.md` — the canonical spec for every component. If a ticket and this page
   disagree, stop and ask.
2. `docs/dev/UI_AUDIT.md` — your backlog. Find the first unchecked **H** ticket whose prerequisites
   are done (F1 before everything).
3. `docs/dev/DESIGN_TOKENS.md` — the token rule: components use `var(--…)`, never a literal colour.
4. `docs/dev/ARCHITECTURE.md` §2 and §4 — where things live, and the rules you must not break.

## The procedure, per ticket

**0. Once per session, record the baseline** (on a clean working tree):

```powershell
cd D:\Work\Development\MATCAP
.venv\Scripts\python -m pytest -q -p no:cacheprovider 2>&1 | Select-String "^FAILED" | Sort-Object > $env:TEMP\baseline.txt
(Get-Content $env:TEMP\baseline.txt).Count
```

Some tests fail before you start; that list is the baseline. Your job is to leave it exactly as it
is.

**1. Read the ticket and every file it names.** Find the call sites with a search, not from
memory. Note how many you expect to change.

**2. Make the change.** Only what the ticket says. Class names and specs come from
DESIGN_SYSTEM.md; don't invent a new one. Keep layout styles (width, margin, flex, position)
inline — only the component's own look moves to the class.

**3. Check syntax.**

```powershell
.venv\Scripts\python -c "import armada.webui, armada.serve"
node --check armada\webui\static\js\<file>.js      # for every .js file you touched
```

**4. Run the suite and compare with the baseline.**

```powershell
.venv\Scripts\python -m pytest -q -p no:cacheprovider 2>&1 | Select-String "^FAILED" | Sort-Object > $env:TEMP\now.txt
Compare-Object (Get-Content $env:TEMP\baseline.txt) (Get-Content $env:TEMP\now.txt)
```

No output means the same tests fail as before. A **new** failure in a golden-page test is expected
when your change alters rendered markup — go to step 5. A new failure in **any other test** means
stop (see below).

**5. Regenerate the goldens and read every diff.**

```powershell
$env:ARMADA_REGOLD = "1"; .venv\Scripts\python -m pytest -q -p no:cacheprovider tests\test_golden_pages.py; Remove-Item Env:ARMADA_REGOLD
git diff --stat tests\golden
git diff tests\golden
```

Every changed line must be the change you meant: a `style="…"` shortening and a `class="…"`
gaining a name. If a diff shows **anything else** — a word, a number, a date, an element added or
removed, an order change — undo it and stop.

**6. Look at it.** Open the page in the app (`http://127.0.0.1:8756/<page>`) in light **and** dark
mode (Settings → App → Appearance). If you have a browser tool, take a screenshot of the page
before (from `git stash`) and after. It should look the same, or differ only as the ticket says.

**7. Commit — one ticket, one commit.**

```powershell
git add <the files you changed, by name>       # never `git add -A`: the tree has line-ending noise
git commit -m "4.3 B1: btn-primary carries its own white text; strip 45 inline color:#fff"
```

Then tick the ticket in `docs/dev/UI_AUDIT.md` with the commit's short hash, in the same commit or the
next one.

**8. Next ticket.** Don't batch two tickets into one commit, even small ones.

## Releases

You don't bump the version or write changelog entries per ticket. At the end of a session, one
release commit: bump `armada/__init__.py`, add one `_CHANGELOG` entry at the top of
`armada/webui/changelog.py` saying what the owner will notice ("Buttons and badges now look the same
on every page…"; "Internal only" if nothing is visible), regold (the changelog renders into
`settings.html`), suite at baseline, commit. Then POST `http://127.0.0.1:8756/restart` and check the
version on Settings.

## Stop and ask — don't guess

Stop, write down what you found, and ask Mihai if any of these happen:

- A test other than a golden page starts failing, or one stops failing.
- A golden diff contains anything but the class/style change you intended.
- The ticket would touch `armada/routes/`, `runner.py`, `scheduler.py`, anything that writes a
  realm file, or JavaScript *logic* (anything beyond a class name or a style string inside a
  template).
- The ticket is marked **S** or **M**, or says "Mihai".
- DESIGN_SYSTEM.md doesn't say what the canonical version is, or two of its rules conflict.
- You'd need a class or token that isn't in DESIGN_SYSTEM.md.
- A change you expected to be invisible visibly changes a page in light or dark mode.
- More than ~40 call sites for one ticket — split it and say how.

## Things that look like bugs but aren't

- `pages.py` pyflakes warnings about undefined names: the `globals().update(vars(_core))` mirror
  (ARCHITECTURE §2). Leave them.
- `except Exception:` blocks all log via `swallowed(log, …)` — a test enforces it. If you add one,
  do the same.
- Hundreds of files show as modified in `git status` without real changes: Windows line endings.
  `git diff -w --stat` shows the real ones.
- `#fff` on a filled button and chart palettes are allowed literals (DESIGN_TOKENS.md).
