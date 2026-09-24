"""System skills: bundled with the app, discoverable, and not reachable from the realm folder."""
from pathlib import Path

from armada import sysskills


def test_capability_review_is_bundled():
    ids = [s["id"] for s in sysskills.list_system_skills()]
    assert "capability-review" in ids


def test_entries_carry_display_metadata():
    it = sysskills.get_system_skill("capability-review")
    assert it and it["name"] and it["description"]
    assert it["locked"] is True and it["system"] is True
    assert it["version"]            # defaults to the app version — they ship together
    assert it["body"].strip()       # frontmatter stripped, body preserved


def test_skill_lives_inside_the_package_not_the_realm():
    """'Locked' is structural: there is nothing in the user's realm to edit or delete."""
    it = sysskills.get_system_skill("capability-review")
    pkg = Path(sysskills.__file__).resolve().parent
    assert Path(it["path"]).resolve().is_relative_to(pkg)


def test_unknown_and_traversal_ids_are_rejected():
    assert sysskills.get_system_skill("nope") is None
    assert sysskills.get_system_skill("../../secrets") is None
    assert sysskills.get_system_skill("a/b") is None
    assert sysskills.get_system_skill("") is None


def test_reveal_route_is_wired_and_resolves_by_id_only():
    """'Go to file' must resolve a skill id server-side — a caller can't hand it a raw path."""
    import inspect
    from armada import serve
    routes = {v for d in vars(serve.Handler).values() if isinstance(d, dict) for v in d.values()}
    assert "_reveal_skill" in routes
    src = inspect.getsource(serve.Handler._reveal_skill)
    assert 'body.get("path"' not in src          # never takes a path from the request
    assert "get_system_skill" in src and "_skill_md_path" in src


def test_frontmatter_parser():
    meta, body = sysskills._parse_front('---\nname: X\ndescription: "d"\n---\nhello\n')
    assert meta["name"] == "X" and meta["description"] == "d" and body.startswith("hello")


def test_body_returned_when_no_frontmatter():
    meta, body = sysskills._parse_front("just text")
    assert meta == {} and body == "just text"


def test_review_skill_states_its_safety_rules():
    """The skill's whole point is auditing untrusted third-party code — the injection warning and
    the no-'safe'-verdict rule are load-bearing, not decoration."""
    import re
    # collapse markdown line-wrapping and emphasis so the assertions test content, not layout
    body = re.sub(r"[\s*_]+", " ", sysskills.get_system_skill("capability-review")["body"].lower())
    assert "untrusted data" in body
    assert 'never write "safe"' in body
    assert "do not execute" in body
