"""Preflight `doctor` (SPEC §17) — verifies the environment before a run.

v0.2 checks: Python, Git, the selected engine (installed + auth), and (if given) that
the realm folder is readable. Auto-resolve/bootstrap and per-skill checks land with the
provisioner (P5). It blocks only what's actually broken and prints an actionable report.
"""
from __future__ import annotations
import shutil, sys
from pathlib import Path
from .engine import get_engine


def run(realm: str | None = None, engine: str = "claude") -> int:
    checks: list[tuple[str, bool, str]] = []

    checks.append(("Python ≥ 3.10", sys.version_info >= (3, 10),
                   f"{sys.version.split()[0]}"))
    git = shutil.which("git")
    checks.append(("Git present", bool(git), git or "not found — needed for realm versioning/backup"))

    ok, detail = get_engine(engine).doctor()
    checks.append((f"Engine '{engine}'", ok, detail))

    if realm:
        p = Path(realm)
        has = (p / "cabinet" / "schedule.json").exists() or (p / "realm.json").exists() or (p / "agents").is_dir()
        checks.append(("Realm folder readable", has,
                       str(p) if has else f"{p} — no cabinet/schedule.json, realm.json, or agents/"))

    print("ARMADA doctor\n" + "─" * 60)
    all_ok = True
    for name, good, detail in checks:
        mark = "✓" if good else "✗"
        all_ok = all_ok and good
        print(f"  {mark} {name:22s} {detail}")
    print("─" * 60)
    print("All green — ready to run." if all_ok else
          "Fix the ✗ items above. (Engine gaps block only runs on that engine, not the app.)")
    return 0 if all_ok else 1
