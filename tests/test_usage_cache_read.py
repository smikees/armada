"""Token accounting: count the whole run, not the part that happened to be uncached.

A real turn reporting 23 tokens beside $0.50 of api-equivalent cost is what exposed this — at list
prices nothing costs dollars for tens of tokens, so one of the two numbers had to be wrong. Dumping
an actual CLI `result` event (rather than trusting the field names) showed two omissions:

  * a run uses more than one model — Claude Code calls a background Haiku alongside the one asked
    for, and the `usage` block describes only the main one (897 of 2,954 tokens invisible);
  * a fresh context is WRITTEN to cache, not read from it, so the whole prompt of a new thread
    lands in cache_creation_input_tokens and nowhere else (2,043 of those 2,954).

`modelUsage` carries all four counters per model, so it is the run.
"""
import inspect

from armada.engine.base import Usage
from armada.engine.claude import ClaudeEngine, _usage_from_event

# Copied from a real `result` event emitted by the CLI (claude 2.1.263).
_REAL = {
    "type": "result", "result": "ok", "is_error": False, "total_cost_usd": 0.042017,
    "usage": {"input_tokens": 2, "output_tokens": 4,
              "cache_read_input_tokens": 0, "cache_creation_input_tokens": 2043},
    "modelUsage": {
        "claude-haiku-4-5-20251001": {"inputTokens": 897, "outputTokens": 8,
                                      "cacheReadInputTokens": 0, "cacheCreationInputTokens": 0,
                                      "costUSD": 0.000937},
        "claude-fable-5-1": {"inputTokens": 2, "outputTokens": 4,
                             "cacheReadInputTokens": 0, "cacheCreationInputTokens": 2043,
                             "costUSD": 0.04108},
    },
}


def test_it_counts_the_whole_run():
    u = _usage_from_event(_REAL)
    assert u.total == 2954, "the run really used 2,954 tokens across both models"


def test_the_background_model_is_counted():
    """897 tokens the `usage` block never mentions."""
    u = _usage_from_event(_REAL)
    assert u.input == 899          # 897 haiku + 2 fable


def test_cache_creation_is_counted():
    """The first turn of a thread writes its context to cache; that is most of the run."""
    u = _usage_from_event(_REAL)
    assert u.cache_write == 2043


def test_tokens_and_cost_now_agree_on_the_same_run():
    """The symptom: a plausible cost beside an implausible token count."""
    u = _usage_from_event(_REAL)
    per_1k = u.cost_usd / (u.total / 1000)
    assert per_1k < 0.10, f"${per_1k:.2f}/1k tokens is not a real price — a counter is missing"


def test_cache_read_still_counted_for_a_warm_thread():
    """Once a thread has history the same tokens arrive as cache READS instead."""
    warm = {"total_cost_usd": 2.2, "modelUsage": {
        "claude-opus-4-8": {"inputTokens": 32, "outputTokens": 14478,
                            "cacheReadInputTokens": 1007532, "cacheCreationInputTokens": 0}}}
    u = _usage_from_event(warm)
    assert u.cache_read == 1007532 and u.total == 1022042


def test_it_falls_back_to_the_usage_block():
    u = _usage_from_event({"total_cost_usd": 0.5, "usage": {
        "input_tokens": 10, "output_tokens": 20,
        "cache_read_input_tokens": 30, "cache_creation_input_tokens": 40}})
    assert (u.input, u.output, u.cache_read, u.cache_write) == (10, 20, 30, 40)
    assert u.total == 100


def test_an_empty_event_is_not_an_error():
    u = _usage_from_event({})
    assert u.total == 0 and u.cost_usd == 0.0


def test_malformed_modelusage_entries_are_skipped():
    u = _usage_from_event({"modelUsage": {"a": None, "b": "nope",
                                          "c": {"inputTokens": 5}}, "total_cost_usd": 0.0})
    assert u.input == 5


def test_both_engine_paths_use_one_accounting():
    """run() and run_stream() drifted apart once before; a single helper is the point."""
    for fn in (ClaudeEngine.run, ClaudeEngine.run_stream):
        assert "_usage_from_event" in inspect.getsource(fn), fn.__name__


def test_total_includes_every_term():
    assert Usage(input=1, output=2, cache_read=3, cache_write=4).total == 10


def test_the_stored_shape_carries_cache_write():
    d = Usage(input=1, output=2, cache_read=3, cache_write=4, cost_usd=0.5).as_dict()
    assert d["cache_write"] == 4 and d["total"] == 10
