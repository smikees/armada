"""Golden-HTML snapshot suite — the regression oracle for the layered refactor.

Renders every page against a deterministic fixture realm and compares the normalized HTML to
committed goldens in tests/golden/. Any byte-level drift (which a pure structural refactor must
never cause) fails here.

Regenerate goldens after an INTENTIONAL output change:
    ARMADA_REGOLD=1 python -m pytest tests/test_golden_pages.py
Review the git diff of tests/golden/ before committing — that diff IS the behavior change.
"""
from __future__ import annotations
import os
from pathlib import Path
import pytest

from tests import golden_support as g

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
REGOLD = bool(os.environ.get("ARMADA_REGOLD"))


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    realm = g.build_fixture(tmp_path_factory.mktemp("realm"))
    with g.ServedRealm(realm) as srv:
        yield srv


def _routes():
    # labels are stable regardless of realm path
    return g.routes_for("")


@pytest.mark.parametrize("label,path", _routes(), ids=[lbl for lbl, _ in _routes()])
def test_page_matches_golden(served, label, path):
    got = g.normalize(served.get(path), realm=served.realm)
    gold_file = GOLDEN_DIR / f"{label}.html"
    if REGOLD:
        GOLDEN_DIR.mkdir(exist_ok=True)
        gold_file.write_text(got, encoding="utf-8")
        pytest.skip(f"regold: wrote {gold_file.name}")
    assert gold_file.exists(), (
        f"no golden for '{label}'. Generate with: ARMADA_REGOLD=1 python -m pytest "
        f"tests/test_golden_pages.py")
    want = gold_file.read_text(encoding="utf-8")
    assert got == want, (
        f"rendered HTML for '{label}' ({path}) drifted from golden. If intentional, "
        f"regenerate with ARMADA_REGOLD=1 and review the diff.")
