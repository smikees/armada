# ARMADA — start here

**Read `docs/LAUNCH_PLAN.md` first.** It is the north star from 2026-09-21 to the beta launch and
beyond: phases in order, what's done, what's deferred, and which steps only Mihai can do
(marked **MIHAI** — ask, don't guess). Mihai marks steps complete; nothing is marked done
without his say-so. Update its "Where things stand" table as work lands.

**Which model to run on:** each phase in the plan names it (Opus 5.5 for specs and design,
Sonnet 5 for implementation, Haiku 4.5 for one-ticket polish under the golden suite). Switch per
phase, not per message. If you are a cheaper model than the phase names, say so and stop.

Settled decisions (don't reopen): Claude is the only engine for v1 · Alexander is a guide in v1,
a developer via extension points later · the Council ships in v1, plan-only · the first launch is
a labelled beta to an invited group · the Catalogue is search-plus-bring-a-link, not browse.

## Working conventions that already hold

- Every release: version bump in `armada/__init__.py`, a changelog entry in
  `armada/webui/changelog.py` that explains *why*, full suite green, goldens regolded only after
  reviewing the diff, commit, restart via `ARMADA.vbs` + `SCHEDULER.vbs`.
- Tests: `uvx pytest -q` with `PYTHONPATH` set to the repo. Goldens: `ARMADA_REGOLD=1` on
  `tests/test_golden_pages.py`; they render at a frozen clock (`tests/golden_support.py`).
- The realm folder is the truth. No realm write without `util.file_lock`; every JSON write
  through `util.write_json_atomic`. No network call on a page-render path.
- Commit messages and docstrings say why, not just what. Keep that.
- Live realms on this machine: `D:\Work\Work2\Cabinet-realm` (active), `D:\Work\Hand-realm`.
  Never edit them by hand as a shortcut; go through the app's own functions.

## Repo map

`armada/` app · `armada/webui/` server-rendered pages · `armada/webui/static/js/` client JS ·
`armada/engine/` the engine seam (`claude.py`, `mock.py`) · `armada/system_skills/` skills
bundled with the app · `tests/` (goldens in `tests/golden/`) · `docs/` plan, schema, tokens,
reviews.
