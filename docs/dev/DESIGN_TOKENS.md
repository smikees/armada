# ARMADA design tokens — the styling contract

This is the single reference for the design tokens the UI is built from, and the rule that
governs their use. Tokens are CSS custom properties defined in `armada/webui/static/`:

- **`industry.css`** — the base design system (source of truth for the ramps and scales).
- **`brand.css`** — the ARMADA skin: it overrides the base with the brand palette, adds the
  `--color-sand-*` scale and the text-alpha scale, defines `--r`, and carries the **dark**
  token set (`.armada-dark`).
- **`armada/vtheme.py`** — per-app *visual themes* (theme-as-data): the selected theme injects a
  `:root{…}` block after the stylesheets that overrides the accent scales. The default theme
  (`armada`) injects nothing, so it renders exactly as `brand.css` defines.

## The rule

**Components reference tokens; they never hardcode a theme value.** Use `var(--color-accent)`,
not `#0b3f86`; `var(--font-heading)`, not `"Barlow Condensed"`; `var(--r)`, not `4px`. This is
what lets dark mode and alternate themes reskin the whole app without touching a single
component, and it's what keeps the palette consistent.

Legitimate exceptions (not "leaks"): fixed non-theme values such as white text on a coloured
button (`#fff`), and categorical data-visualisation palettes (e.g. the ColorBrewer Paired-12
set used for charts), which are deliberately independent of the theme.

## Tokens

### Color — roles
| Token | Meaning |
| --- | --- |
| `--color-bg` | page background |
| `--color-surface` | raised surface fill |
| `--color-text` | primary text/ink |
| `--color-divider` | hairline borders and separators |

### Color — scales (each has `-100` lightest … `-900` darkest; base ≈ `-600`)
| Token family | Meaning |
| --- | --- |
| `--color-accent`, `--color-accent-100..900` | primary brand accent (navy in `armada`) |
| `--color-accent-2`, `--color-accent-2-100..900` | secondary accent (teal in `armada`) |
| `--color-neutral-100..900` | neutral grey ramp (shared lightness scale) |
| `--color-sand-100/200/300/500/700/900` | warm surface/fill ramp (brand-added) |

### Color — status
| Token | Use |
| --- | --- |
| `--status-ok` | success / healthy |
| `--status-warn` | warning |
| `--status-bad` | error / destructive |
| `--status-idle` | idle / unknown |

### Text alpha (opacity of `--color-text`, theme-aware)
`--text-strong` (70%) · `--text-dim` (60%) · `--text-muted` (55%) · `--text-soft` (50%) ·
`--text-faint` (45%) · `--text-ghost` (40%). Prefer these over ad-hoc `color-mix(... var(--color-text) …)`.

### Type
| Token | Value (default) |
| --- | --- |
| `--font-heading` | `"Barlow Condensed", system-ui, sans-serif` |
| `--font-heading-weight` | `600` |
| `--font-body` | `"Barlow", system-ui, sans-serif` |

The wordmark is a bitmap (`armada-wordmark.png`, see `brand.py`), so no display font ships. (`Heavitas`,
which drew the old SVG wordmark, was removed in v0.99.51: unused, and its licence unverified.)

### Spacing
`--space-1` 3.4px · `--space-2` 6.8px · `--space-3` 10.2px · `--space-4` 13.6px ·
`--space-6` 20.4px · `--space-8` 27.2px.

### Radius
`--radius-sm` 2px · `--radius-md` 4px · `--radius-lg` 7px. The brand default `--r` (4px) is the
one most components use.

### Elevation
`--shadow-sm` · `--shadow-md` · `--shadow-lg` (ink-tinted on light; ambient darkness on dark).

## Theming surfaces

- **Colour mode** (light/dark): `.armada-dark` on `<body>` swaps the token *values*; components
  are unchanged. Chosen in Settings → Appearance (per-device).
- **Colour theme** (visual theme): per-app, stored in `~/.armada/config.json`; the registry lives
  in `armada/vtheme.py`. A theme is two base colours from which the accent scales are generated.
  Add a theme by adding an entry to `vtheme.THEMES`.

## Known outstanding leaks (to migrate to tokens)

A handful of inline styles still hardcode brand-relevant values (e.g. `#0b3f86` / `#12a3b8`
instead of `var(--color-accent)` / `var(--color-accent-2)`). These should be routed through
tokens so alternate themes apply to them too. The white-on-accent `#fff` uses and the chart
palettes are intentional and stay as-is.
