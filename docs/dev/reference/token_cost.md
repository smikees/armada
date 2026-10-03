# `armada/token_cost.py`

Approximate standard-text API equivalents; subscription charges are never inferred.

Rates checked 2026-10-01 at developers.openai.com/api/docs/pricing and model pages,
ai.google.dev/gemini-api/docs/pricing, and platform.claude.com/docs/en/about-claude/pricing.
Run aggregates cannot establish per-request long-context or tool fees, so these are base-rate
estimates. Cached tokens are separate from uncached input in Armada's usage contract.

### `estimate(model, tokens, at=None)`

Return None for unknown models or missing accounting, never substitute another model.

### `for_run(record)`

Read historical costs without changing stored results or receipts.
