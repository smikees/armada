---
name: ARMADA website
description: A plain, professional introduction and download page for ARMADA.
colors:
  ink: "#1d1f20"
  muted: "#596369"
  blue: "#004081"
  teal: "#02a0af"
  line: "#dbe1e3"
  surface: "#f5f7f8"
  white: "#fff"
  link-hover: "#002e5e"
  button-hover: "#002f60"
  beta-bg: "#edf1f5"
  beta-text: "#34536c"
typography:
  display:
    fontFamily: "Barlow Condensed, Arial, sans-serif"
    fontSize: "64px"
    fontWeight: 600
    lineHeight: 1.12
    letterSpacing: "-.015em"
  headline:
    fontFamily: "Barlow Condensed, Arial, sans-serif"
    fontSize: "25px"
    fontWeight: 600
    lineHeight: 1.12
  body:
    fontFamily: "Barlow, Arial, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.6
  lead:
    fontFamily: "Barlow, Arial, sans-serif"
    fontSize: "22px"
    fontWeight: 400
    lineHeight: 1.4
rounded:
  focus: "2px"
  badge: "3px"
  control: "4px"
spacing:
  page-desktop: "48px"
  page-tablet: "32px"
  page-mobile: "24px"
  page-small: "20px"
components:
  button-primary:
    backgroundColor: "{colors.blue}"
    textColor: "{colors.white}"
    rounded: "{rounded.control}"
    padding: "10px 16px"
  button-primary-hover:
    backgroundColor: "{colors.button-hover}"
    textColor: "{colors.white}"
  beta-badge:
    backgroundColor: "{colors.beta-bg}"
    textColor: "{colors.beta-text}"
    rounded: "{rounded.badge}"
    padding: "0 7px"
  getting-started:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.muted}"
    rounded: "{rounded.control}"
    padding: "27px 30px"
---

# Design System: ARMADA website

## Overview

The current implementation is a simple, professional software introduction with clear download,
repository and documentation links. This documents the HTML/CSS approved by the maintainer and published on 2026-10-03.

The user rejected generated compositions and invented application UI. The current page uses
text and the exact supplied ARMADA brand artwork. Any future product imagery must be real
application screenshots, with permission to expose their content. Do not invent demonstration
data, dashboards, application windows or substitute brand marks.

**Key Characteristics:**

- White surfaces, charcoal copy, navy links and a teal focus indicator.
- Barlow body text and compact Barlow Condensed headings.
- Fine dividers, restrained corner rounding and no decorative effects.
- Exact supplied SVG branding, with no product imagery in the current page.

## Colors

### Primary

ARMADA blue identifies links and the installer action. The darker link and button hover colors
provide their respective interaction states. Teal is reserved for the visible keyboard focus ring.

### Neutral

Ink carries headings and body text; muted gray carries supporting copy. White is the page
background, line gray separates sections, and the pale surface distinguishes setup guidance.
The beta badge uses its own pale background and muted blue text.

## Typography

Self-hosted Barlow regular and medium support body copy and controls; Barlow Condensed semibold
supports headings. Arial and sans-serif are fallbacks. Preserve the supplied SIL OFL notices.

The frontmatter records desktop base roles. The main heading decreases to 52px at 1000px and
46px at 680px. It has a 680px maximum width on desktop and 520px on mobile. The lead becomes
21px on mobile. Descriptive introduction text is 18px with a 1.65 line height and a 580px maximum
width, becoming 17px on mobile. Section headings use local 24–27px variants. Supporting labels
and links range from 12–15px. Body text remains sentence case; no promotional all-caps treatment.

## Layout

The centered page has a maximum width of 1248px including horizontal padding. Desktop padding
is 48px per side. The header uses a horizontal wordmark/navigation row, a 108px minimum height
and a bottom divider. The wordmark is 174px wide.

The introduction uses a flexible copy column and 285px download column with an 86px gap and
80px/72px vertical padding. The download column has a left divider. The engine section has two
columns and horizontal dividers; its provider list stays in three columns. Three explanatory
columns follow with 48px gaps. Setup guidance pairs a 180px heading column with flexible copy.

At widths up to 1000px, page padding becomes 32px, the introduction uses a 265px download column,
34px gap and 56px vertical padding, and the engine section stacks. Explanatory gaps become 26px;
the setup heading column becomes 150px.

At widths up to 680px, page padding becomes 24px, the header has an 88px minimum height and the
wordmark becomes 135px wide. The introduction and explanatory sections stack. The download
divider moves above the panel; its button has a 320px maximum width. Provider labels remain
three across with smaller text and gaps. Setup guidance becomes one column with 24px padding.
The footer wraps, and its issue link moves below with a 49px left offset.

At widths up to 380px, page padding becomes 20px, the wordmark becomes 110px wide, navigation
uses a 12px gap and 12px nonwrapping labels, the header gap becomes 12px, and the footer text
minimum width becomes 180px. This narrow-screen rule supports the 320px viewport.

## Elevation & Depth

The implementation uses no shadows. White space, thin borders and the pale setup surface provide
structure. No glass, gradients, floating panels or simulated application windows are present.

## Shapes

Controls and the setup surface have subtle rounding. The badge has a slightly smaller radius.
Section divisions are single-pixel rules. Preserve the exact supplied SVG artwork and its aspect
ratio; the HTML SVG viewports omit the original files' page whitespace without modifying the files.

## Components

### Navigation and text links

Navigation is a simple horizontal pair of links. Muted default navigation text becomes dark blue
and underlined on hover. General text links are blue with a 4px underline offset. Every anchor
receives a 3px teal outline with a 5px offset on keyboard focus. The skip link appears on focus.

### Installer action

The installer is a full-width blue anchor with centered white text, a decorative download icon,
medium font weight, a 10px internal gap and a 48px minimum height. Hover darkens its background;
keyboard focus uses the shared anchor outline. Its text does not wrap.

### Beta badge

A compact noninteractive status label sits beside the current version. It uses 12px text and a
23px line height; it is not a selectable chip or action.

### Setup guidance

A single pale panel contains a heading, explanatory copy and a setup-guide link. Its grid changes
to one column on mobile. It has no shadow, animation or clickable container behavior.

### Branding and footer

The header uses `assets/armada-logo.svg`; the footer uses `assets/armada-symbol.svg` at 37px wide.
Both files are byte-identical to the supplied originals; provenance and viewport dimensions are
recorded in ASSETS.md. Footer copy states the source-available license and provider independence.

Smooth scrolling is the only motion behavior. Reduced-motion preference disables it.

## Do's and Don'ts

### Do:

- **Do** use the exact supplied ARMADA SVG logo and symbol.
- **Do** keep copy factual, professional and easy to scan.
- **Do** preserve visible focus, the skip link and responsive reading order.
- **Do** use real application screenshots if product imagery is added in a future revision.
- **Do** obtain the maintainer's UI approval before FTPS publication.

### Don't:

- **Don't** create invented app UI, synthetic demonstration data or replacement brand artwork.
- **Don't** ship the rejected generated compositions as product imagery.
- **Don't** add sales claims, testimonials, pricing plans or decorative effects without direction.
- **Don't** claim approval or publication for future changes until confirmed.
