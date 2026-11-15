# UI refinement, 0.99.154

Remaining API remains an estimate: the optional owner-entered monthly display budget
minus reported Armada Claude API costs. Unknown completed-run costs suppress the
estimate. This is not Console credit or a spending control. The amount opens the
existing engine fallback modal on Overview, focuses the budget, restores focus on
close, and refreshes after Save. No provider credentials or limits were changed.

Composer bullets use a bundled font face restricted to U+2022 and U+25E6, enlarged
160 percent. Ordinary text and four-space nested indentation are unchanged. Overview
headlines are two typographic points smaller. Save has a stronger blue pulse and
halo, with a static reduced-motion highlight. Worker controls have a 12px action gap.

Theme cards explicitly use palette surfaces. Four alternate themes now generate
separate dark accent ramps on both the root and body so nested dark-mode token scopes
cannot reset them to blue. Primary button foregrounds adapt to dark accents. Native
checks cover selected and unselected cards in all twelve theme/mode combinations.

Alexander and detached threads share companion geometry, alpha perimeter capture,
owned shadow windows and disposal. Alexander refreshes the perimeter on palette
changes and avatar load; resize follows the existing native event handlers. Its
header uses the detached-thread type scale. Native checks exercise opening, resizing,
dark mode, closing and disposal; synthetic composite screenshots show the frame
against an opaque desktop background.

Impeccable's detector found seven pre-existing accent-border patterns elsewhere in
the shared stylesheet; these are incumbent design, outside this requested refinement.
Native owner journeys and the detached-thread probe provide regression coverage.
Final release evidence is recorded in RELEASE_0_99_154.md after publication.
