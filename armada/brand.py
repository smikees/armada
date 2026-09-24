"""ARMADA brand surface — the single place that defines the app's visible identity.

Everything user-visible that *names or pictures* the product lives here: the name, the logo/mark
markup, the about blurb, the logo/icon asset filenames, and the window/page title format. A future
rebrand (or a white-label) should be a one-file edit — change the constants here and the titlebar,
window title, About panel, and OS icon all follow.

Out of scope on purpose: the COLOUR palette (CSS custom properties in webui/static/*.css) and prose
inside docstrings/CLI logs — those aren't part of the app's visual chrome. The realm's own icon
(uploaded per realm) is separate too; this is the ARMADA product brand.
"""
from __future__ import annotations
from pathlib import Path

NAME = "ARMADA"
TAGLINE = "your standing team of minds"
ABOUT = (f"{NAME} is a local, single-user app for building and running your own standing team of AI "
         "agents — a realm you direct, each agent with its own personality, memory, skills, scheduled "
         "jobs and level of autonomy. Your realm is a folder you own (portable, versionable); the app "
         "is a stateless engine over it, running on your own machine and your own AI subscription. "
         "Nothing is hosted in the cloud and the app phones home to nothing.")
# Shown under About (ADR-007): source-available, never "open source".
LICENCE = ("Source-available under the PolyForm Noncommercial License 1.0.0: free for personal and "
           "other noncommercial use; commercial use by agreement. Copyright © 2026 Mihai Stanculescu.")
LICENCE_URL = "https://polyformproject.org/licenses/noncommercial/1.0.0"

# Brand assets served from webui/static/. Swap these to re-skin without touching any other file.
LOGO_ASSET = "armada-logo.png"         # the mark shown in the titlebar (transparent PNG, 47x30 —
                                        # exported from "Armada - logo - symbol.svg" at 30px tall)
WORDMARK_ASSET = "armada-wordmark.png"  # full lockup (mark + "ARMADA"), used where there's room for
                                         # it — exported from "Armada - logo - standard.svg", 208x36
ICON_FILE = "armada.ico"           # OS window/taskbar icon (multi-size, from the 256px emblem)

_STATIC = Path(__file__).resolve().parent / "webui" / "static"


def _asset_v(asset: str) -> int:
    """Cache-buster so a new logo shows at once instead of waiting out the browser's cache."""
    try:
        return int((_STATIC / asset).stat().st_mtime)
    except OSError:
        return 0


_LOGO_V = _asset_v(LOGO_ASSET)
_WORDMARK_V = _asset_v(WORDMARK_ASSET)

# The titlebar logo and a small square-ish mark, both drawing the exact brand SVG (fixed brand colours).
# max-width:none overrides the global `img{max-width:100%}` reset (industry.css) so the logo keeps
# its fixed natural size and never shrinks/jumps when the window or header layout changes width.
# 26px since v0.99.62 (was 30 — Mihai: "a bit smaller" in the app).
LOGO = (f'<img src="/static/{LOGO_ASSET}?v={_LOGO_V}" alt="{NAME}" class="wordmark" '
        f'height="26" style="display:block;flex:none;width:auto;max-width:none">')
MARK = (f'<img src="/static/{LOGO_ASSET}?v={_LOGO_V}" alt="{NAME}" '
        f'height="16" style="display:block;flex:none;width:auto;max-width:none">')
# The full lockup — mark + wordmark — for spots with room to spare, like the About/version box.
WORDMARK = (f'<img src="/static/{WORDMARK_ASSET}?v={_WORDMARK_V}" alt="{NAME}" '
            f'height="36" style="display:block;flex:none;width:auto;max-width:none">')
# Settings → App → version: the lockup at ~70% (Mihai, v0.99.62), the version beside it without the name.
WORDMARK_SMALL = (f'<img src="/static/{WORDMARK_ASSET}?v={_WORDMARK_V}" alt="{NAME}" '
                  f'height="25" style="display:block;flex:none;width:auto;max-width:none">')


# Release channel (launch plan 5.7). While it's set, the window title, the nav, the welcome page and
# Settings → App say so — people using a beta should never have to wonder whether they are. Set to
# "" for 1.0; everything that shows it keys off this one value.
CHANNEL = "beta"
BETA_PILL = (f'<span class="mc-pill is-accent mc-channel" title="{NAME} is in beta — '
             f'expect rough edges, and please report them">{CHANNEL}</span>') if CHANNEL else ""


def window_title() -> str:
    """The OS window title: 'ARMADA beta' during the beta, 'ARMADA' after."""
    return f"{NAME} {CHANNEL}" if CHANNEL else NAME


def page_title(sub: str = "") -> str:
    """Browser-tab / OS-window title: 'ARMADA — <sub>' (or just the name)."""
    return f"{NAME} — {sub}" if sub else NAME


def icon_path() -> Path:
    """Absolute path to the OS window/taskbar icon file."""
    return _STATIC / ICON_FILE
