"""Immutable request/run destinations; the selected realm is only an admission-time default.

IDs identify canonical local folders, not permissions. Moving a folder changes its ID so stale
links fail closed. Explicit content destinations resolve only to known or registered realms.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import html
from html.parser import HTMLParser
import os
from pathlib import Path
import re
import threading
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import uuid

from .util import StateError, safe_seg

SELECTION_LOCK = threading.RLock()
_known = {}


class RealmMismatch(StateError):
    """A page/request no longer names the realm selected by the owner."""


@dataclass(frozen=True)
class RealmContext:
    root: str
    realm_id: str

    @classmethod
    def capture(cls, root):
        if not root:
            return cls("", "none")
        path = str(Path(root).resolve())
        identity = hashlib.sha256(os.path.normcase(path).encode("utf-8")).hexdigest()[:32]
        context = cls(path, identity)
        with SELECTION_LOCK:
            _known[identity] = context
        return context

    @classmethod
    def resolve(cls, identity, current):
        if current.realm_id == identity:
            return current
        with SELECTION_LOCK:
            known = _known.get(identity)
        if known and (Path(known.root) / "realm.json").is_file():
            return known
        from .realm_registry import load as _reg_load
        for record in _reg_load():
            if record.get("path") and (Path(record["path"]) / "realm.json").is_file():
                candidate = cls.capture(record["path"])
                if candidate.realm_id == identity:
                    return candidate
        raise RealmMismatch("This realm is no longer available. Open it again from the realm selector.")


@dataclass(frozen=True)
class RunContext:
    realm: RealmContext
    agent: str
    thread: str
    run_id: str

    @classmethod
    def capture(cls, root, agent, thread="main", run_id=None):
        if run_id is not None and len(str(run_id)) > 80:
            raise StateError("Run ID is too long.")
        return cls(RealmContext.capture(root), safe_seg(agent, "agent"), safe_seg(thread, "thread"),
                   safe_seg(run_id or uuid.uuid4().hex, "run"))

    @property
    def key(self):
        return self.realm.realm_id, self.run_id

    @property
    def marker(self):
        return Path(self.realm.root) / "agents" / self.agent / "runs" / ".running" / f"_chat-{self.run_id}.json"


@dataclass
class ActiveRun:
    context: RunContext
    process: object = None
    cancelled: bool = False


def content_path(path):
    return path.startswith(("/section-raw/", "/section-asset/", "/avatar/")) or path in (
        "/thread-file", "/realm-icon", "/user-avatar", "/embed/thread")


def bound_url(url, context, *, content=False):
    """Bind local URLs without double-binding or accepting an arbitrary file-system path."""
    parts = urlsplit(url)
    if not parts.path.startswith("/") or parts.path.startswith(("//", "/r/")):
        return url
    if content:
        return urlunsplit(parts._replace(path=f"/r/{context.realm_id}{parts.path}"))
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["_realm"] = context.realm_id
    return urlunsplit(parts._replace(query=urlencode(query)))


def navigation_url(url, root):
    """Notification navigation selects its original realm before opening the destination."""
    if not url.startswith("/") or url.startswith(("//", "/switch")):
        return url
    context = RealmContext.capture(root)
    return "/switch?" + urlencode({"path": context.root, "to": bound_url(url, context)})


def bind_content_html(body, context):
    """Bind real markup attributes without rewriting script text or untrusted documents."""
    class Parser(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.out = []

        def handle_starttag(self, tag, attrs):
            text = self.get_starttag_text()
            def replace(match):
                value = html.unescape(match[3])
                parsed = urlsplit(value)
                if not parsed.netloc and content_path(parsed.path):
                    value = bound_url(value, context, content=parsed.path.startswith(("/section-raw/", "/section-asset/")))
                    return match[1] + match[2] + html.escape(value, quote=True) + match[2]
                return match[0]
            self.out.append(re.sub(r'''((?:src|href|data-lightbox)\s*=\s*)(["'])(.*?)\2''', replace, text, flags=re.I))

        handle_startendtag = handle_starttag
        def handle_endtag(self, tag): self.out.append(f"</{tag}>")
        def handle_data(self, data): self.out.append(data)
        def handle_entityref(self, name): self.out.append(f"&{name};")
        def handle_charref(self, name): self.out.append(f"&#{name};")
        def handle_comment(self, data): self.out.append(f"<!--{data}-->")
        def handle_decl(self, decl): self.out.append(f"<!{decl}>")
    parser = Parser()
    parser.feed(body)
    parser.close()
    return "".join(parser.out)
