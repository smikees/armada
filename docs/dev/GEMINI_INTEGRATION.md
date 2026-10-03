# Gemini engine

The third provider is `gemini`; the installed adapter drives Antigravity CLI (`agy`).
`armada/engine/gemini.py` implements the shared execution contract for threads, jobs and support
turns. Provider detection, login, installation and catalogues live in `providers.py`,
`provider_login.py`, `provider_install.py` and `models.py`. Keep provider details behind this seam.

The model catalogue and effort choices come from the account's CLI listing. Actual model IDs
from terminal events take precedence for accounting. Parse saved-account status without exposing
credentials; reuse the CLI's OAuth session. Missing quota windows must stay unknown.

Each run creates a temporary scoped project configuration. It disables inherited MCP/customizations
and includes only the selected file tools, granted roots and configured connectors. Delete it in
cleanup, including exception and timeout paths. Never add an ancestor merely to make the CLI happy.
CapabilityPolicy recognizes the bundled filesystem extension by its metadata identity and maps
it to native file tools; arbitrary connectors named `filesystem` must still pass MCP admission.
Google connector authorization is separate from Claude and Codex. Refresh grants each invocation.

The current adapter supports streamed output, native scoped file tools and explicit network grants.
Shell execution, sealed review turns, dollar-budget enforcement and fallback models are unsupported
requirements, rejected by admission. Do not silently downgrade them.

`token_cost.py` estimates base-rate text API equivalents from uncached input, output, cache reads
and cache writes. Provider-reported cost wins. Unknown model IDs or incomplete breakdowns yield
None. Output already includes reasoning tokens; never add reasoning again. Google Flash's dated
2026 promotional rates use the run date, not the date the page is viewed. Aggregated run tokens
cannot prove a per-request long-context surcharge. Header partial-total metadata keeps unavailable
accounting visible without suppressing known totals or changing historical run evidence.

Regression coverage: `tests/test_gemini_engine.py`, `tests/test_cap_gating.py`,
`tests/test_execution_contracts.py`, and `tests/test_overview_polish.py`. Live checks should use an
isolated realm without financial jobs or external notifications. See the bundled
[Gemini user guide](../../armada/docs/user/gemini.md) for setup and limitations.
