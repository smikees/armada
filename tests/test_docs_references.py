"""Docs don't rot (launch plan 3.6).

Every doc in docs/ (except the launch plan and the historical ones, which describe the past) is
checked for the concrete things it points at: relative links resolve; a `file.py` or
`file.py:function` reference names a file that exists and a function, class or method in it; a
`/route` in backticks is a route the server answers; `armada <command>` is a real CLI command; the
generated module reference is current. A doc that names something that no longer exists is how an
agent — Alexander included — gets told to do something impossible, and nothing else catches it.
"""
import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
# The plan and the historical docs narrate what WAS true; the generated reference is checked below.
SKIP = {"LAUNCH_PLAN.md", "CODE_REVIEW_2026-09-07.md", "VOICE_SHELVED.md"}


def _docs():
    return sorted(p for p in DOCS.rglob("*.md")
                  if p.name not in SKIP and "reference" not in p.relative_to(DOCS).parts)


def _code(text: str) -> list[str]:
    return re.findall(r"`([^`\n]+)`", text)


_PY = [p for p in (ROOT / "armada").rglob("*.py") if "__pycache__" not in p.parts] + \
      list((ROOT / "tests").glob("*.py")) + list((ROOT / "tools").glob("*.py"))


def _py_file(ref: str):
    ref = ref.replace("\\", "/")
    hits = [p for p in _PY if p.as_posix().endswith("/" + ref) or p.name == ref]
    return hits[0] if hits else None


def _defines(path: Path, dotted: str) -> bool:
    """Is `dotted` (func, Class, Class.method, CONST, or a nested helper's name) defined in the file?
    Route handlers are methods on mixin classes and some helpers are nested, so a bare name is
    looked for anywhere in the file; a dotted one must match its parent too."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    parts = dotted.split(".")
    defs = {}
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defs.setdefault(n.name, []).append(n)
            for c in getattr(n, "body", []):
                if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    defs.setdefault(f"{n.name}.{c.name}", []).append(c)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    defs.setdefault(t.id, []).append(n)
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            defs.setdefault(n.target.id, []).append(n)
    return ".".join(parts[-2:]) in defs if len(parts) > 1 else parts[0] in defs


def _routes() -> tuple[set, list]:
    src = (ROOT / "armada" / "serve.py").read_text(encoding="utf-8")
    exact = set(re.findall(r'"(/[\w\-./]*)":\s*"_', src)) | set(re.findall(r'if path == "(/[\w\-./]*)"', src))
    prefixes = re.findall(r'\("(/[\w\-./]*)",\s*"_', src)
    return exact, prefixes


def _cli() -> set:
    return set(re.findall(r'add_parser\("([\w-]+)"', (ROOT / "armada" / "cli.py").read_text(encoding="utf-8")))


@pytest.mark.parametrize("doc", _docs(), ids=lambda p: p.relative_to(DOCS).as_posix())
def test_relative_links_resolve(doc):
    bad = []
    for m in re.finditer(r"\]\(([^)#\s]+)(#[^)]*)?\)", doc.read_text(encoding="utf-8")):
        t = m.group(1)
        if not t.startswith(("http://", "https://", "mailto:")) and not (doc.parent / t).resolve().exists():
            bad.append(t)
    assert not bad, bad


# ADRs record a decision at a point in time, including files the decision says will exist; the
# development log records files that existed then (and the owner's own scripts it ran against).
@pytest.mark.parametrize("doc", [d for d in _docs() if "adr" not in d.relative_to(DOCS).parts
                                 and d.name != "DEV_LOG.md"],
                         ids=lambda p: p.relative_to(DOCS).as_posix())
def test_code_references_exist(doc):
    exact, prefixes = _routes()
    cli = _cli()
    bad = []
    for c in _code(doc.read_text(encoding="utf-8")):
        m = re.fullmatch(r"([\w./\\-]+\.py)(?::([\w.]+))?(?:\(.*\))?", c.strip())
        if m and m.group(1) in ("file.py", "x.py"):          # the docs' own placeholder examples
            continue
        if m:
            f = _py_file(m.group(1))
            if f is None:
                bad.append(f"no file {m.group(1)}")
            elif m.group(2) and not _defines(f, m.group(2)):
                bad.append(f"{m.group(1)} has no {m.group(2)}")
            continue
        m = re.fullmatch(r"(/api/[\w\-/]+)", c.strip())
        if m:
            r = m.group(1)
            if r not in exact and not any(r.startswith(p) for p in prefixes):
                bad.append(f"no route {r}")
            continue
        m = re.fullmatch(r"armada ([\w-]+)(?: .*)?", c.strip())
        if m and m.group(1) not in cli:
            bad.append(f"no CLI command armada {m.group(1)}")
    assert not bad, bad


def test_the_generated_reference_is_current():
    import importlib.util
    spec = importlib.util.spec_from_file_location("gen_reference", ROOT / "tools" / "gen_reference.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    want = gen.generate()
    out = DOCS / "dev" / "reference"
    have = {p.name: p.read_text(encoding="utf-8") for p in out.glob("*.md")}
    stale = sorted(set(want) ^ set(have)) + sorted(k for k in want if k in have and want[k] != have[k])
    assert not stale, f"run `python tools/gen_reference.py` — stale: {stale[:10]}"


# ---- the in-app help (3.1) -----------------------------------------------------------------------

def test_every_user_page_is_in_the_index_and_renders(tmp_path):
    from armada.webui import pages
    toc = [s for s, _t, _b in pages._doc_toc()]
    on_disk = sorted(p.stem for p in (DOCS / "user").glob("*.md") if p.stem != "index")
    assert sorted(toc) == on_disk, "docs/user/index.md's table must list every page (and only those)"
    for s in toc:
        html = pages._doc_html((DOCS / "user" / f"{s}.md").read_text(encoding="utf-8"))
        for target, frag in re.findall(r'href="/docs/([a-z0-9-]+)(#[\w-]+)?"', html):
            assert target in toc, f"{s}.md links to missing page {target}"
            if frag:
                linked = pages._doc_html((DOCS / "user" / f"{target}.md").read_text(encoding="utf-8"))
                assert f'id="{frag[1:]}"' in linked, f"{s}.md links to missing heading {target}{frag}"
        assert not re.search(r'href="/docs/[^"]*" target="_blank"', html), "help links must stay in the app window"


def test_help_pages_are_served_and_a_bad_slug_is_not(tmp_path):
    from armada.webui import pages

    from golden_support import build_fixture
    from armada import reader
    realm_path = build_fixture(tmp_path / "realm")
    realm = reader.read(realm_path)
    ok = pages.render_docs(realm, realm_path, slug="jobs")
    assert "Paused jobs" in ok and 'id="paused-jobs"' in ok
    assert "No such help page" in pages.render_docs(realm, realm_path, slug="../../etc/passwd")
    assert "No such help page" in pages.render_docs(realm, realm_path, slug="nope")
    idx = pages.render_docs(realm, realm_path)
    assert idx.count('class="mc-docitem"') == len(pages._doc_toc())
