"""Approximate standard-text API equivalents; subscription charges are never inferred.

Rates checked 2026-10-01 at developers.openai.com/api/docs/pricing and model pages,
ai.google.dev/gemini-api/docs/pricing, and platform.claude.com/docs/en/about-claude/pricing.
Run aggregates cannot establish per-request long-context or tool fees, so these are base-rate
estimates. Cached tokens are separate from uncached input in Armada's usage contract.
"""
import datetime
import math
import re

# USD per million: uncached input, output, cache read, cache write.
_OPENAI = {
    'gpt-6-astra': (10, 50, 1, 12.5),
    'gpt-6.1-sol': (2, 10, .1, 2.5),
    'gpt-6-sol': (2, 10, .2, 2.5),
    'gpt-6-luna': (.1, .5, .01, .125),
    'gpt-5.6-sol': (4, 20, .4, 5),
    'gpt-5.6-terra': (2, 12, .2, 2.5),
    'gpt-5.6-luna': (.2, 1.2, .02, .25),
    'gpt-5.5': (5, 30, .5, 6.25),
}


def estimate(model, tokens, at=None):
    """Return None for unknown models or missing accounting, never substitute another model."""
    mid = str(model or '').lower().removeprefix('codex:').removeprefix('gemini:')
    mid = re.sub(r'-\d{4}-\d{2}-\d{2}$', '', mid)
    if mid == 'gpt-5.6':
        mid = 'gpt-5.6-sol'
    rates = _OPENAI.get(mid)
    if mid in ('gemini-3.8-flash', 'gemini-3.7-flash', 'gemini-3.6-flash'):
        day = str(at or datetime.date.today())[:10]
        rates = (.75, 3.75, .075, None) if day < '2027-01-01' else (1.5, 7.5, .15, None)
    elif mid in ('gemini-3.1-pro', 'gemini-3.1-pro-preview'):
        rates = (2, 12, .2, None)
    elif mid.startswith('claude-'):
        if mid.startswith(('claude-fable-5', 'claude-mythos-5')):
            rates = (10, 50, .25 if mid.startswith(('claude-fable-5-1', 'claude-mythos-5-1')) else 1, 12.5)
        elif mid.startswith('claude-opus-5-5'):
            rates = (4, 20, .2, 5)
        elif mid.startswith(('claude-opus-5', 'claude-opus-4-8', 'claude-opus-4-7', 'claude-opus-4-6', 'claude-opus-4-5')):
            rates = (5, 25, .5, 6.25)
        elif mid.startswith('claude-sonnet-5'):
            rates = (2, 10, .2, 2.5)
        elif mid.startswith(('claude-sonnet-4-6', 'claude-sonnet-4-5')):
            rates = (3, 15, .3, 3.75)
        elif mid.startswith('claude-haiku-4-5'):
            rates = (1, 5, .1, 1.25)
    if rates is None or not isinstance(tokens, dict):
        return None
    amounts = [tokens.get('input'), tokens.get('output'), tokens.get('cache_read', 0), tokens.get('cache_write', 0)]
    if any(not isinstance(n, (int, float)) or isinstance(n, bool) or not math.isfinite(n) or n < 0 for n in amounts):
        return None
    if any(rate is None and n for rate, n in zip(rates, amounts)):
        return None
    return round(sum((rate or 0) * n for rate, n in zip(rates, amounts)) / 1_000_000, 6)


def for_run(record):
    """Read historical costs without changing stored results or receipts."""
    tokens = record.get('tokens') or {}
    if not isinstance(tokens, dict):
        return None
    value = tokens.get('api_equiv_usd')
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0:
        return float(value)
    return estimate(record.get('model'), tokens, record.get('ts'))
