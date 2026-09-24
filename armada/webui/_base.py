"""Base layer — shared low-level UI primitives (carved from _core.py in Phase 3).

The foundation every renderer builds on: HTML escaping, form-field style constants, the safe
Markdown renderer, and small label formatters. Depends ONLY on stdlib, so any module (including
future component modules) can import from here without touching _core — this is what lets the
mid-DAG renderers be carved out later without import cycles.
"""
from __future__ import annotations
import html
import json
import re


E = html.escape


def _J(value) -> str:
    """A value as a JavaScript string literal, safe inside an HTML event attribute (onclick="…").

    `onclick="f('{E(x)}')"` is NOT safe: the browser decodes the attribute's entities before the
    JavaScript parser sees it, so E()'s `&#x27;` turns back into a quote and a value like
    `x');fetch('/api/…` breaks out of the string. JSON-encode first (quotes, backslashes and
    control characters escaped for JS), then HTML-escape (for the attribute). Use it WITHOUT
    surrounding quotes: `onclick="f({_J(x)})"`. Found writing the 5.8 threat model; a test keeps
    `'{E(` out of event attributes.
    """
    return E(json.dumps("" if value is None else str(value)))
# The field/label/textarea looks are classes now: .mc-field, .mc-label, .mc-textarea (brand.css; UI audit FI1).
_STAR = '<span class="mc-star" style="color:var(--status-bad)">*</span>'


def _md_inline(s: str) -> str:
    """Inline Markdown on already-HTML-escaped text: code, bold, italic, links."""
    codes: list[str] = []

    def _stash(m):
        codes.append(m.group(1))
        return f"\x00{len(codes)-1}\x00"
    s = re.sub(r"`([^`]+)`", _stash, s)                                   # inline code (protected)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)               # **bold**
    s = re.sub(r"(?<![\w*])\*(?!\s)([^*\n]+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)   # *italic*
    s = re.sub(r"(?<![\w_])_(?!\s)([^_\n]+?)(?<!\s)_(?![\w_])", r"<em>\1</em>", s)     # _italic_

    def _link(m):
        txt, url = m.group(1), m.group(2)
        if not re.match(r"(https?:|/|mailto:)", url, re.I):
            return m.group(0)
        return f'<a href="{url}" target="_blank" rel="noopener noreferrer">{txt}</a>'
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", _link, s)                    # [text](url)
    return re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{codes[int(m.group(1))]}</code>", s)


# Scrolling a just-opened <details> into view, inside .mc-appscroll (the element that actually
# scrolls — the window does not). Prefer showing the whole thing: scroll only as far as it takes to
# bring its bottom edge to the bottom of the viewport. If the section is taller than the viewport
# that is impossible, so fall back to putting its heading at the top, which is the next best answer
# and the one that still works when the section grows. Wire it up with ontoggle="mcRevealSection(this)".
# Body lives in webui/static/js/reveal.js (Phase 2, 2.1).
from ..assets import REVEAL_JS as _REVEAL_JS  # noqa: E402

_BULLET = r"^\s*[-*+]\s+"
_NUMBER = r"^\s*(\d+)\.\s+"


def _list_items(lines: list[str], i: int, n: int, pat: str) -> tuple[list[str], int]:
    """Collect one list's items, folding hard-wrapped continuation lines back into their item.

    Documents written by hand wrap at column 95, so a list item routinely spans three source lines
    with the rest indented under it. Taking only the marker line meant the remainder fell through to
    the paragraph branch: the bullet showed half a sentence, the rest appeared below it as loose
    prose, and — because the stray paragraph ended the run — every numbered item started a fresh
    <ol> and so was numbered 1. A continuation line is any non-blank line that isn't itself a new
    block: another item, a heading, a fence or a table.
    """
    items: list[str] = []
    while i < n:
        ln = lines[i]
        if re.match(pat, ln):
            items.append(re.sub(pat, "", ln).strip()); i += 1
            continue
        s = ln.strip()
        if (not items or s == "" or s.startswith("```") or s.startswith("|")
                or re.match(r"^#{1,6}\s", s) or re.match(_BULLET, ln) or re.match(_NUMBER, ln)):
            break
        items[-1] += " " + s
        i += 1
    return items, i


def _md(text: str) -> str:
    """Render a safe subset of Markdown to HTML. The input is untrusted, so it is HTML-escaped
    first — only the whitelisted tags emitted below can appear. Supports headings, bullet/number
    lists, tables, code fences, inline code/bold/italic/links, and paragraphs."""
    src = E(str(text or "")).replace("\r\n", "\n")
    lines = src.split("\n")
    out: list[str] = []
    i, n = 0, len(lines)
    while i < n:
        ln = lines[i]
        s = ln.strip()
        if s.startswith("```"):                                          # code fence
            j = i + 1; buf = []
            while j < n and not lines[j].strip().startswith("```"):
                buf.append(lines[j]); j += 1
            out.append(f'<pre class="mc-md-pre"><code>{chr(10).join(buf)}</code></pre>')
            i = j + 1; continue
        if s.startswith("|") and i + 1 < n and re.match(r"^\s*\|?[\s:\-|]+\|?\s*$", lines[i + 1]):  # table
            hdr = [c.strip() for c in s.strip("|").split("|")]
            i += 2; rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")]); i += 1
            th = "".join(f"<th>{_md_inline(c)}</th>" for c in hdr)
            tb = "".join("<tr>" + "".join(f"<td>{_md_inline(c)}</td>" for c in r) + "</tr>" for r in rows)
            out.append(f'<table class="mc-md-tbl"><thead><tr>{th}</tr></thead><tbody>{tb}</tbody></table>')
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", ln)                            # heading
        if m:
            lvl = min(len(m.group(1)) + 2, 6)
            out.append(f"<h{lvl}>{_md_inline(m.group(2).strip())}</h{lvl}>")
            i += 1; continue
        if re.match(_BULLET, ln):                                         # unordered list
            items, i = _list_items(lines, i, n, _BULLET)
            out.append("<ul>" + "".join(f"<li>{_md_inline(x)}</li>" for x in items) + "</ul>"); continue
        if re.match(_NUMBER, ln):                                         # ordered list
            first = int(re.match(_NUMBER, ln).group(1))
            items, i = _list_items(lines, i, n, _NUMBER)
            start = f' start="{first}"' if first != 1 else ""
            out.append(f"<ol{start}>" + "".join(f"<li>{_md_inline(x)}</li>" for x in items) + "</ol>")
            continue
        if s == "":
            i += 1; continue
        para = [ln]; i += 1                                               # paragraph
        while i < n and lines[i].strip() != "" and not re.match(r"^\s*([-*+]\s+|\d+\.\s+|#{1,6}\s|\|)", lines[i]) \
                and not lines[i].strip().startswith("```"):
            para.append(lines[i]); i += 1
        out.append(f"<p>{_md_inline(' '.join(x.strip() for x in para))}</p>")
    return "".join(out)


def _page_title(t: str, sub: str = "", right: str = "", right_html: str = "") -> str:
    """`right` is muted text set alongside the heading; `right_html` is markup (a button, say) and
    is NOT escaped — pass only markup this code built, never anything user-supplied."""
    s = f'<span class="mc-eyebrow" style="margin-left:6px">· {E(sub)}</span>' if sub else ""
    if not right and not right_html:
        return f'<h2 class="mc-h-page">{E(t)}{s}</h2>'
    tail = (right_html if right_html else
            f'<span style="font-size:11.5px;color:var(--text-soft);white-space:nowrap">{E(right)}</span>')
    return (f'<div style="display:flex;align-items:baseline;gap:10px;margin:0 0 14px">'
            f'<h2 class="mc-h-page" style="margin:0">{E(t)}{s}</h2>'
            f'<span style="margin-left:auto">{tail}</span></div>')




def _chip(text: str, variant: str = "plain", title: str = "") -> str:
    """A chip (DESIGN_SYSTEM §7): the model-pill look — grey fill, --r radius — for a label that
    names something (a model, a kind), where a pill states a status. `.mc-chip`, UI audit P3."""
    cls = "mc-chip is-accent" if variant == "accent" else "mc-chip"
    tt = f' title="{E(title)}"' if title else ""
    return f'<span class="{cls}"{tt} style="margin-left:6px">{E(text)}</span>'


# One status pill (DESIGN_SYSTEM §7, UI audit P1/P2): the tint is always 16%, drawn by `.mc-pill.is-*`.
_TONES = {"--status-ok": "ok", "--status-warn": "warn", "--status-bad": "bad",
          "--color-accent": "accent", "--color-accent-2": "accent2"}


def _tone(col: str) -> str:
    """The pill tone for a status colour: 'var(--status-ok)' or '--status-ok' → 'ok'. Anything else
    (idle, muted) is 'neutral'."""
    c = (col or "").strip()
    if c.startswith("var(") and c.endswith(")"):
        c = c[4:-1].strip()
    return _TONES.get(c, "neutral")


def _pill(inner: str, tone: str = "neutral", title: str = "", style: str = "") -> str:
    """A status pill. `inner` is HTML (escape text before passing it)."""
    t = f' title="{E(title)}"' if title else ""
    st = f' style="{style}"' if style else ""
    return f'<span class="mc-pill is-{tone}"{t}{st}>{inner}</span>'


def _poss(name: str) -> str:
    """Possessive form (raw — caller should E() it): 'Marcus' → \"Marcus’\", 'Warren' → \"Warren’s\"."""
    return name + ("’" if name.rstrip().endswith(("s", "S")) else "’s")
