# Third-party notices

ARMADA is licensed under PolyForm Noncommercial 1.0.0 (see `LICENSE`). It includes, or installs
alongside itself, the third-party work below, each under its own licence. Nothing here is
relicensed; these notices are how each licence asks to be credited.

## Not included — installed and signed in separately

| Software | Terms | Notes |
|---|---|---|
| Claude Code (Anthropic) | Anthropic's terms of service | ARMADA runs every agent through it. It isn't bundled; you install it and sign in with your own Claude account. "Claude" and the Claude mark are Anthropic's trademarks, used to show which service ARMADA works with. ARMADA isn't affiliated with or endorsed by Anthropic. |

## Python runtime and packages

The installer ships a Python runtime and these packages (Windows beta).

| Package | Version | Licence | Source |
|---|---|---|---|
| Python | 3.12 | PSF-2.0 | https://www.python.org |
| pywebview | 6.2.1 | BSD-3-Clause | https://pywebview.flowrl.com |
| pythonnet | 3.1.0 | MIT | https://pythonnet.github.io |
| clr-loader | 0.3.1 | MIT | https://github.com/pythonnet/clr-loader |
| bottle | 0.13.4 | MIT | https://bottlepy.org |
| proxy-tools | 0.1.0 | MIT | https://github.com/jtushman/proxy_tools |
| cffi | 2.1.1 | MIT-0 | https://cffi.readthedocs.io |
| pycparser | 3.0 | BSD-3-Clause | https://github.com/eliben/pycparser |
| typing-extensions | 4.16.0 | PSF-2.0 | https://github.com/python/typing_extensions |

The versions are the ones the beta is built and tested with. The installer (launch plan 5.2)
must regenerate this table from what it actually bundles, and include each package's own licence
file (every wheel carries one in its `*.dist-info` folder).

## Fonts

| Font | Licence | Source |
|---|---|---|
| Barlow, Barlow Condensed (Jeremy Tribby) | SIL Open Font License 1.1 | https://github.com/jpt/barlow |

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
| Fluent UI System Icons (Microsoft) | MIT |
| Carbon (IBM) | Apache-2.0 |
| Material Symbols (Google) | Apache-2.0 |
| Simple Icons (the Claude mark) | CC0-1.0 for the drawing; the mark itself is Anthropic's trademark (above) |

The ARMADA name, logo and icon are Mihai Stanculescu's and aren't covered by the licence above,
which licenses the software, not the brand.
