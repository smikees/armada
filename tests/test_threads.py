"""Thread append / render / list round-trip."""
from armada.threads import Thread


def test_append_and_messages(tmp_path):
    th = Thread(tmp_path, "main")
    th.append("hello", "hi there")
    msgs = th._messages()
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[0]["content"] == "hello"
    assert msgs[1]["content"] == "hi there"
    assert all("ts" in m for m in msgs)


def test_render_includes_turns(tmp_path):
    th = Thread(tmp_path, "main")
    th.append("what is 2+2", "4")
    r = th.render()
    assert "Owner: what is 2+2" in r
    assert "You: 4" in r


def test_list_threads(tmp_path):
    Thread(tmp_path, "main").append("a", "b")
    Thread(tmp_path, "taxes").append("c", "d")
    assert set(Thread.list_threads(tmp_path)) == {"main", "taxes"}


def test_empty_thread_is_blank(tmp_path):
    th = Thread(tmp_path, "main")
    assert th._messages() == []
    assert th.render() == ""
    assert th.summary() == ""


def test_events_are_stored_but_skipped_in_context(tmp_path):
    th = Thread(tmp_path, "main")
    th.append("set up an AMZN watch", "done")
    ev = th.append_event("scheduled_task", title="AMZN cover watch — post-intraday check it",
                         subtitle="Weekdays at 4:25 PM", href="/jobs")
    assert ev["role"] == "event" and ev["kind"] == "event" and ev["type"] == "scheduled_task"
    msgs = th._messages()
    # the event is persisted in the log …
    assert any(m.get("role") == "event" for m in msgs)
    # … but never leaks into the model-facing context
    r = th.render()
    assert "AMZN cover watch" not in r
    assert "Owner: set up an AMZN watch" in r and "You: done" in r


def test_md_renders_common_markdown():
    from armada import webui
    h = webui._md("# Title\n\nSome **bold**, `code`, *it*.\n\n- one\n- two\n\n1. a\n2. b")
    assert "<h3>Title</h3>" in h
    assert "<strong>bold</strong>" in h and "<code>code</code>" in h and "<em>it</em>" in h
    assert "<ul><li>one</li><li>two</li></ul>" in h
    assert "<ol><li>a</li><li>b</li></ol>" in h


def test_md_escapes_html():
    from armada import webui
    h = webui._md("<script>alert(1)</script> **x**")
    assert "<script>" not in h and "&lt;script&gt;" in h and "<strong>x</strong>" in h


def test_md_table():
    from armada import webui
    h = webui._md("| A | B |\n|---|---|\n| 1 | 2 |")
    assert "mc-md-tbl" in h and "<th>A</th>" in h and "<td>1</td>" in h


def test_ordered_threads_excludes_archived(tmp_path):
    import json
    from armada import webui
    for t in ("main", "taxes", "old"):
        (tmp_path / "threads" / t).mkdir(parents=True)
    (tmp_path / "threads" / "meta.json").write_text(
        json.dumps({"archived": {"old": "2026-09-01"}}), encoding="utf-8")
    names, meta = webui._ordered_threads(tmp_path)
    assert names[0] == "main" and "taxes" in names
    assert "old" not in names                       # archived threads are hidden
    assert meta["archived"]["old"] == "2026-09-01"


def test_compaction_preserves_events(tmp_path):
    class _Eng:
        def run(self, system, prompt, allow_tools=False):
            return type("R", (), {"output": "- summary bullet"})()
    th = Thread(tmp_path, "main")
    th.append_event("scheduled_task", title="AMZN cover watch")
    for i in range(8):
        th.append(f"q{i} " + "x" * 400, f"a{i} " + "y" * 400)
    assert th.compact_if_needed(_Eng(), threshold_chars=1000, keep_recent_pairs=2) is True
    msgs = th._messages()
    # the event survived compaction; only older conversational turns were dropped
    assert any(m.get("role") == "event" and m.get("title") == "AMZN cover watch" for m in msgs)
    convo = [m for m in msgs if m.get("role") in ("user", "assistant")]
    assert len(convo) == 4  # keep_recent_pairs=2 → 2 pairs
