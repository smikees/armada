# System jobs column regression

13 November 2026, fixed in v0.99.146.

The shared Jobs filter sets a matching row's inline `display` to an empty string.
System rows declared `display:grid` inline, so the first filter application removed
their layout. Their metadata became inline text below the description while the
header retained its grid. This also occurred when the search was cleared or saved
filters were restored. Server HTML snapshots alone could not catch the browser's
post-filter layout.

System rows now own `display:grid` through their stylesheet class. Filtering can
hide and restore a row without erasing its layout. Header and rows keep the same
seven columns. Long descriptions/status strings wrap inside the first column.
Narrow views keep the existing horizontal list scrollbar and reachable controls.
User-job behavior, cadence, cost, scheduling and execution are unchanged.

## Regression evidence

`tests/system_jobs_layout_harness.js` measures actual native WebView rectangles.
It checks visible row display, seven direct columns, metadata/action alignment
against the header, row bounds, first-cell text overflow, week strips, buttons,
switches and document overflow. This measures rendered geometry, not just HTML
presence or matching class names.

`tools/owner_workflow_probe.py` runs it on the production Jobs page after searching,
clearing search, cost/status/cadence filters, sorting, User/System tab changes,
long feedback, switch-off/on refresh and synthetic Run now feedback. The fixture
never executes a real system job. Wide/standard/narrow native views cover Armada II,
the default theme, dark mode and 150% zoom. Narrow-view checks scroll to the action
columns. Fresh views avoid deferred shrink notifications in hidden WebView2 controls.

The new test failed before the fix: every one of the ten rows lost its grid.
After the fix its **32 checks** pass. Evidence: `build/system-jobs-before.json`
(expected failure) and `build/system-jobs-fixed.json` (pass), with wide light and
scaled dark captures. Captures preserve the native table's horizontal scroll.
These checks are also included in the existing full owner-workflow journey run by
the mandatory stabilization gate and the staged-runtime release check.

To repeat only this regression with synthetic data:

```powershell
.venv\Scripts\python tools/owner_workflow_probe.py --system-jobs-only --output build/system-jobs.json
```
