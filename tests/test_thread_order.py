"""New threads land at the TOP of the secondary (non-main) list.

_new_thread prepends the new slug to meta['order']; _ordered_threads then sorts it above the
other non-pinned threads (which, absent an order entry, fall back to name order).
"""
import json
from armada import webui


def _mk(agent_dir, *slugs):
    (agent_dir / "threads" / "main").mkdir(parents=True)
    for s in slugs:
        (agent_dir / "threads" / s).mkdir(parents=True)


def test_new_thread_sorts_to_top_of_secondary(tmp_path):
    ad = tmp_path / "agents" / "ray"
    _mk(ad, "alpha", "new-chat")
    # simulate what _new_thread writes: the fresh thread prepended to order
    (ad / "threads" / "meta.json").write_text(json.dumps({"order": ["new-chat"]}), encoding="utf-8")
    names, _ = webui._ordered_threads(ad / "" if False else ad)
    assert names[0] == "main"
    assert names[1] == "new-chat"            # newest at the top of the secondary list
    assert "alpha" in names[2:]


def test_pinned_still_above_new(tmp_path):
    ad = tmp_path / "agents" / "ray"
    _mk(ad, "pinned-one", "new-chat")
    (ad / "threads" / "meta.json").write_text(
        json.dumps({"order": ["new-chat"], "pinned": {"pinned-one": True}}), encoding="utf-8")
    names, _ = webui._ordered_threads(ad)
    # main first, then the pinned thread, then the new one
    assert names[0] == "main" and names[1] == "pinned-one" and names[2] == "new-chat"
