"""Thread navigation state belongs to persistence, not to HTML renderers."""
from pathlib import Path
from . import util


def set_unread(agent_dir, slug: str, unread: bool = True):
    util.safe_seg(slug, "thread")
    return util.mutate_json(Path(agent_dir) / "threads" / "meta.json",
        lambda meta: meta.setdefault("unread", {}).update({slug: unread}), default=dict)


def set_last(agent_dir, slug: str):
    util.safe_seg(slug, "thread")
    return util.mutate_json(Path(agent_dir) / "threads" / "meta.json",
                            lambda meta: meta.update(last=slug), default=dict)
