"""safe_seg (traversal guard) + atomic writers."""
import json
import pytest
from armada import util


def test_safe_seg_allows_normal_ids():
    for ok in ["hand", "finance", "new-chat-2", "marcus_brief", "a1"]:
        assert util.safe_seg(ok) == ok


def test_safe_seg_blocks_traversal_and_separators():
    for bad in ["..", ".", "", "../x", "a/b", "a\\b", "/etc", "x/../y", None, "a b", ".hidden"]:
        with pytest.raises(util.UnsafeSegment):
            util.safe_seg(bad)
    assert util.is_safe_seg("ok") and not util.is_safe_seg("../x")


def test_write_text_atomic(tmp_path):
    p = tmp_path / "sub" / "f.txt"
    util.write_text_atomic(p, "héllo")          # also creates parent dir
    assert p.read_text(encoding="utf-8") == "héllo"
    util.write_text_atomic(p, "again")           # overwrite
    assert p.read_text(encoding="utf-8") == "again"
    # no stray temp files left behind
    assert list(p.parent.glob(".tmp-*")) == []


def test_write_json_atomic_roundtrip(tmp_path):
    p = tmp_path / "realm.json"
    util.write_json_atomic(p, {"name": "Test", "n": 3, "x": ["a", "b"]})
    assert json.loads(p.read_text(encoding="utf-8")) == {"name": "Test", "n": 3, "x": ["a", "b"]}
