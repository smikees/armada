# Source simplification, November 2026

Implementation plan for 0.99.157, following the audit of `2ff5f05`.
Preserve execution, permission checks, saved data and rendered desktop pages.
The one intentional presentation correction is the legacy static cockpit's
realm-default engine label; it must follow model selection rather than assume Claude.

## Ordered changes

1. Remove nine unreferenced UI helpers, their private model seed list, the unused
   fail-fast connector checker, and unreachable turn creation in the admission
   callback. Retain connector withholding, durable input and permission rechecks.
2. Share the identical restricted frontmatter parser, retaining both existing
   private import names and each reader's file-error semantics. Consolidate the
   section document wrapper and Claude's tool-mode arguments, preserving branch
   precedence, flags, event delivery, transports and prompt-file cleanup.
3. Replace the page module's implicit namespace copy with explicit imports.
   Preserve the package compatibility exports. Correct add-on documentation to
   name its real dashboard and Alexander consumers. Correct only the static
   cockpit's default-engine display, with no saved configuration migration.
4. Verify focused behavior and unchanged golden pages before the version bump.
   Add regression coverage for parser edge cases, both Claude transports and
   static default-engine selection. Regenerate references, then review the
   intentional changelog-only desktop golden changes. Run the full pinned suite,
   exact-source Windows CI and stabilization gate on the release source.
5. Publish with the enforced maintenance publisher, including native packaged
   recovery/session checks and signed previous-release upgrade rehearsal.
   Repeat owner workflows with the staged runtime; publish and verify the website,
   public signatures, package files and installer hash. Do not restart the owner app.

## Compatibility boundaries

Legacy persisted-data readers, instance/update recovery, adapter compatibility,
post-wait authorization and add-on execution are active functionality. They are
outside the deletion list. JSON and streaming Claude result handling remain
separate. Existing `webui` compatibility exports remain available except the
specifically audited unused private helpers.

## Evidence

The audit's initial focused baseline passed 105 tests. Implementation and release
results are recorded in `RELEASE_0_99_157.md` when verified; this plan does not
claim any pending gate has passed.
