"""Adding an Anthropic skill takes it from the repository zip in one download (catalogue.realm).

Found 2026-09-25 while curating the setup wizard's list: docx ships 61 files, one past the old
per-file cap of 60, so it could never be added; and the per-file path spends one GitHub API call per
directory against an unauthenticated limit of 60 an hour.
"""
import io
import zipfile

from armada.catalogue import realm


def _zip(members: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, body in members.items():
            z.writestr(name, body)
    return buf.getvalue()


def test_a_skill_with_many_files_comes_out_of_the_archive_whole(tmp_path, monkeypatch):
    members = {"skills-main/skills/docx/SKILL.md": "# docx"}
    members.update({f"skills-main/skills/docx/scripts/s{i}.py": "x" for i in range(70)})
    members["skills-main/skills/pdf/SKILL.md"] = "# other skill"
    monkeypatch.setattr(realm, "_skills_archive", lambda: _zip(members))
    dest = tmp_path / "skills" / "docx"
    r = realm.fetch_skill({"id": "docx", "install": {"path": "docx"}}, dest)
    assert r["ok"] and (dest / "SKILL.md").read_text() == "# docx"
    assert len(list((dest / "scripts").iterdir())) == 70
    assert not (dest.parent / "pdf").exists()


def test_a_member_that_could_escape_is_refused_and_nothing_is_left(tmp_path, monkeypatch):
    members = {"skills-main/skills/docx/SKILL.md": "# docx",
               "skills-main/skills/docx/../../evil.txt": "no"}
    monkeypatch.setattr(realm, "_skills_archive", lambda: _zip(members))
    dest = tmp_path / "skills" / "docx"
    r = realm.fetch_skill({"id": "docx", "install": {"path": "docx"}}, dest)
    assert not r["ok"] and not dest.exists()
    assert not (tmp_path / "evil.txt").exists()


def test_python_package_files_are_allowed_but_hidden_and_parent_names_are_not():
    assert realm._safe_name("__init__.py") == "__init__.py"
    for bad in ("..", ".", ".hidden", "a/b", "a\\b", ""):
        assert realm._safe_name(bad) == "", bad
