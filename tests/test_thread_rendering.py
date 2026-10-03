"""Regression cases for Windows links, wide transcripts and complete working summaries."""
import html
from pathlib import Path
import shutil
import subprocess

import pytest

from armada.webui._base import _md
from armada.webui.threadsview import _working_turn
from armada.engine.codex import _AppStream
from armada.engine.claude import _ClaudeStream
from armada.threads import Thread


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is needed for browser script checks")
def test_file_links_use_the_guarded_opener_and_display_errors():
    result = subprocess.run(["node", str(Path(__file__).with_name("thread_file_link_harness.js"))],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("path", [
    "D:/Work/Example-realm/agents/research/daily-check-2026-10-01-retry.md",
    r"D:\Work\Work2\Cabinet-realm\Finance\A - Options trading\report (October).md",
    "D:/reports/_prior_/_current_/report.json",
])
def test_windows_report_links_are_clickable_and_preserve_destinations(path):
    rendered = _md(f"The [review report]({path}) and [`raw data`](<{path}>) are saved.")
    assert rendered.count('data-local-file="' + html.escape(path, quote=True) + '"') == 2
    assert "<code>raw data</code>" in rendered
    assert "[review report]" not in rendered


def test_link_destinations_are_not_changed_by_emphasis():
    rendered = _md("[**Details**](https://en.wikipedia.org/wiki/Foo_(bar)) and [API](https://a.test/_one_/_two_?a=1&b=2)")
    assert 'href="https://en.wikipedia.org/wiki/Foo_(bar)"' in rendered
    assert '<strong>Details</strong>' in rendered
    assert 'href="https://a.test/_one_/_two_?a=1&amp;b=2"' in rendered


@pytest.mark.parametrize("destination", ["javascript:alert(1)", "data:text/html,hello", "//evil.test", "vbscript:msgbox"])
def test_unsafe_links_stay_inert(destination):
    assert "<a " not in _md(f"[link]({destination})")


def test_code_and_link_attributes_remain_escaped():
    assert 'data-local-file=' not in _md('`[not a link](D:/report.md)`')
    rendered = _md('[<img src=x onerror=alert(1)>](D:/report"onclick="bad.md)')
    assert '<img' not in rendered
    assert '"onclick="' not in rendered
    assert '&quot;onclick=&quot;' in rendered


@pytest.mark.parametrize("provider", ["claude", "codex_delta", "codex_item"])
def test_full_thinking_summary_survives_provider_and_navigation(tmp_path, provider):
    summary = "First checks. " + "Evidence and reasoning. " * 500 + "Final conclusion."
    events = []
    if provider == "claude":
        stream = _ClaudeStream(events.append, "sonnet")
        stream.accept({"type": "assistant", "message": {"content": [{"type": "thinking", "thinking": summary}]}})
    else:
        stream = _AppStream(events.append)
        if provider == "codex_delta":
            for part in (summary[:3000], summary[3000:]):
                stream.accept({"method": "item/reasoning/summaryTextDelta", "params": {"itemId": "r", "delta": part}})
        stream.accept({"method": "item/completed", "params": {"item": {
            "id": "r", "type": "reasoning", "summary": [{"text": summary}]}}})
    assert events == [{"kind": "thinking", "text": summary}]
    thread = Thread(tmp_path, "main")
    thread.save_progress("test-turn", "Partial response", "Thinking…", events)
    rendered = _working_turn("", "Warren", thread.progress("test-turn"))
    assert summary in rendered
    assert "Final conclusion." in rendered
