# `armada/doctor.py`

Preflight `doctor` (SPEC §17) — verifies the environment before a run.

v0.2 checks: Python, Git, the selected engine (installed + auth), and (if given) that
the realm folder is readable. Auto-resolve/bootstrap and per-skill checks land with the
provisioner (P5). It blocks only what's actually broken and prints an actionable report.

### `run(realm: str | None=None, engine: str='claude')`

—
