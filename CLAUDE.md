# ARMADA — start here

**Read `docs/LAUNCH_PLAN.md` first.** It is the north star from 2026-09-21 to the beta launch and
beyond: phases in order, what's done, what's deferred, and which steps only Mihai can do
(marked **MIHAI** — ask, don't guess). Mihai marks steps complete; nothing is marked done
without his say-so. Update its "Where things stand" table as work lands.

**Which model to run on:** each phase in the plan names it (Opus 5.5 for specs and design,
Sonnet 5 for implementation, Haiku 4.5 for one-ticket polish under the golden suite). Switch per
phase, not per message. If you are a cheaper model than the phase names, say so and stop.

Provider update (Mihai, 2026-09-26): existing agents may choose Claude or OpenAI models via their
connected CLIs. This supersedes the Claude-only decision; see `docs/dev/CODEX_INTEGRATION.md`.
September 28 extends setup to either/both providers. Connections live in Settings → App;
Alexander's model and effort live in App → Advanced. Automatic uses Opus 5.5/Medium with Claude
connected, otherwise GPT-6 Sol/Medium. See `docs/dev/PROVIDER_ONBOARDING.md`.
October 3 release update: Gemini through Antigravity CLI is the third engine, supported in setup,
agent threads and scheduled jobs. Provider defaults resolve through `engine/selection.py`;
capability support differs by engine (see `armada/docs/user/gemini.md`).

Settled decisions (don't reopen): Alexander is a guide in v1,
a developer via extension points later · the Council ships in v1, plan-only · the first launch is
a labelled beta to an invited group · the Catalogue is search-plus-bring-a-link, not browse.

## Working conventions that already hold

- Every release: version bump in `armada/__init__.py`, a changelog entry in
  `armada/webui/changelog.py` that explains *why*, full suite green, goldens regolded only after
  reviewing the diff, commit, push and publish the signed update plus installer. Installed copies
  use the in-app updater. Development desktop launches must use `desktop_launch.spawn()` so they
  run independently of Codex/Claude processes; do not restart a user's app unnecessarily.
- Tests: `uvx pytest -q` with `PYTHONPATH` set to the repo. Goldens: `ARMADA_REGOLD=1` on
  `tests/test_golden_pages.py`; they render at a frozen clock (`tests/golden_support.py`).
- The realm folder is the truth. No realm write without `util.file_lock`; every JSON write
  through `util.write_json_atomic`. No network call on a page-render path.
- Commit messages and docstrings say why, not just what. Keep that.
- Live realms on this machine: `D:\Work\Work2\Cabinet-realm` (active), `D:\Work\Hand-realm`.
  Never edit them by hand as a shortcut; go through the app's own functions.

## Repo map

`armada/` app · `armada/webui/` server-rendered pages · `armada/webui/static/js/` client JS ·
`armada/engine/` the engine seam (`claude.py`, `codex.py`, `gemini.py`, `mock.py`, `selection.py`) · `armada/system_skills/` skills
bundled with the app · `tests/` (goldens in `tests/golden/`) · `docs/` plan, schema, tokens,
reviews.
