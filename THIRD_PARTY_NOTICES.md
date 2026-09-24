# Third-party notices

ARMADA is licensed under PolyForm Noncommercial 1.0.0 (see `LICENSE`). It includes, or installs
alongside itself, the third-party work below, each under its own licence. Nothing here is
relicensed; these notices are how each licence asks to be credited.

## Not included — installed and signed in separately

| Software | Terms | Notes |
|---|---|---|
| Claude Code (Anthropic) | Anthropic's terms of service | ARMADA runs every agent through it. It isn't bundled; you install it and sign in with your own Claude account. "Claude" and the Claude mark are Anthropic's trademarks, used to show which service ARMADA works with. ARMADA isn't affiliated with or endorsed by Anthropic. |
| Microsoft Edge WebView2 Runtime | Microsoft's terms | ARMADA's window is drawn by it. It's part of Windows 11 and most Windows 10 machines. When it's missing, the installer runs Microsoft's own WebView2 bootstrapper (carried inside the installer, as Microsoft's distribution guide describes, and checked at build time for Microsoft's signature), which downloads and installs the runtime from Microsoft. |

## Python runtime and packages

The installer ships a Python runtime and these packages (Windows beta).

| Package | Version | Licence | Source |
|---|---|---|---|
| Python | 3.12 | PSF-2.0 | https://www.python.org |
| pywebview | 6.2.1 | BSD-3-Clause | https://pywebview.flowrl.com |
| pythonnet | 3.1.0 | MIT | https://pythonnet.github.io |
| clr-loader | 0.3.1 | MIT | https://github.com/pythonnet/clr-loader |
| bottle | 0.13.4 | MIT | https://bottlepy.org |
| proxy-tools | 0.1.0 | BSD-2-Clause | https://github.com/jtushman/proxy_tools |
| cffi | 2.1.1 | MIT-0 | https://cffi.readthedocs.io |
| pycparser | 3.0 | BSD-3-Clause | https://github.com/eliben/pycparser |
| typing-extensions | 4.16.0 | PSF-2.0 | https://github.com/python/typing_extensions |

The versions are the ones the beta is built and tested with. The installer build
(`tools/build_installer.py`) refuses to build if what it bundles differs from this table, and copies
each package's own licence file into `licenses\` in the install folder, along with Python's.
proxy-tools ships no licence file of its own, and its package metadata says MIT, but its repository's
`LICENSE.txt` is a two-clause BSD licence; that text is kept in `installer/licenses/` and ships instead.

## Fonts

| Font | Licence | Source |
|---|---|---|
| Barlow, Barlow Condensed (Jeremy Tribby) | SIL Open Font License 1.1 | https://github.com/jpt/barlow |
| Montserrat (Julieta Ulanovsky et al.) | SIL Open Font License 1.1 | https://github.com/JulietaUla/Montserrat |
| Nunito Sans (Vernon Adams, Jacques Le Bailly et al.) | SIL Open Font License 1.1 | https://github.com/googlefonts/NunitoSans |
| Quicksand (Andrew Paglinawan et al.) | SIL Open Font License 1.1 | https://github.com/andrew-paglinawan/QuicksandFamily |
| Roboto (Google) | SIL Open Font License 1.1 | https://github.com/googlefonts/roboto-3-classic |

Each font's licence ships beside it in `armada/webui/static/fonts/` (`OFL-<family>.txt`). The four
added in v0.99.62 are selectable under Settings → App → Appearance → Fonts.

## Icons

The app's icons are SVG paths inlined from these sets (via Iconify), each unchanged apart from
size and colour.

| Set | Licence |
|---|---|
| Lucide | ISC |
| Tabler Icons | MIT |
| Phosphor Icons | MIT |
| Ant Design Icons | MIT |
| Healthicons | MIT |
| Hugeicons | MIT |
| Siemens iX Icons (the Report an issue icon) | MIT |
| Material Design Icons, Pictogrammers (agent memories) | Apache-2.0 |
| Fluent UI System Icons (Microsoft) | MIT |
| Carbon (IBM) | Apache-2.0 |
| Material Symbols (Google) | Apache-2.0 |
| Simple Icons (the Claude mark) | CC0-1.0 for the drawing; the mark itself is Anthropic's trademark (above) |

The ARMADA name, logo and icon are Mihai Stanculescu's and aren't covered by the licence above,
which licenses the software, not the brand.
