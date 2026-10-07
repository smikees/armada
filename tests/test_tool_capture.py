"""Exact-byte, lifecycle and safety contracts for opt-in MCP result capture."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest
from armada import clock, job_history, runner, tool_capture as tc, util
from armada.engine.raw_results import loads_event, result_source, payload
from armada.engine.base import RunResult
from armada.engine.contracts import ProviderCapabilities
from armada.engine.mock import MockEngine

TOOL = "mcp__fixture_Interactive_Brokers__get_positions"
PATTERN = "mcp__*Interactive_Brokers*__get_*"
RAW = '{ "amount": 12345.6700, "id": 9007199254740993, "tiny": 1.234567890123456789e-30, "unicode": "caf\\u00e9" }'


@pytest.fixture
def realm(tmp_path):
    root = tmp_path / "realm"
    work = tmp_path / "workspace"
    root.mkdir()
    work.mkdir()
    util.write_json_atomic(root / "realm.json", {"name": "Test", "workspace": str(work)})
    return root


def capture(root, run="run1", **kw):
    job = {"capture_tools": [PATTERN], **kw}
    return tc.ToolCapture(root, job, "daily", run, "codex", True, "a")


def send(cap, tid="call1", tool=TOOL, raw=RAW, error=False):
    event = loads_event('{"result":' + raw + '}')
    cap.on_event({"kind": "tool", "id": tid, "name": tool, "input": {"account": "synthetic"}})
    cap.on_event({"kind": "tool_result", "id": tid, "raw_result": result_source(event, ("result",)), "is_error": error})


@pytest.mark.parametrize("tool,expected", [(TOOL, True), (TOOL.upper(), False),
    ("prefix" + TOOL, False), ("mcp__fixture_Interactive_Brokers__place_order", False),
    ("mcp__other__get_positions", False), ("Bash", False)])
def test_patterns_match_full_name_case_sensitively(tool, expected):
    assert tc.matches(tool, [PATTERN]) == expected


@pytest.mark.parametrize("raw,expected,kind", [(RAW, RAW, "json"),
    ('[0,1.000,{"a":2e-10}]', '[0,1.000,{"a":2e-10}]', "json"),
    ('"  hello\\r\\nworld\\n"', "  hello\r\nworld\n", "text"), ('""', "", "text"),
    ("false", "false", "json"), ("0", "0", "json"), ("null", "null", "json")])
def test_extract_never_reserializes_or_trims(raw, expected, kind):
    event = loads_event('{"unrelated":[1,2],"outer":[{},{"value":' + raw + '}]}')
    assert payload(result_source(event, ("outer", 1, "value"))) == (expected, kind)


def test_three_calls_atomic_manifest_and_same_run_script(realm, monkeypatch):
    cap = capture(realm)
    original = util._replace_retrying
    observed = []
    def replace(source, target, *args, **kw):
        source, target = Path(source), Path(target)
        if target.parent == cap.directory:
            assert source.parent == target.parent
            assert source.name.startswith(".tmp-")
            if target.suffix == ".json":
                assert source.read_bytes() == RAW.encode()
            if target.name == "manifest.jsonl":
                for row in map(json.loads, source.read_text().splitlines()):
                    assert (target.parent / row["file"]).is_file()
            observed.append(target.name)
        return original(source, target, *args, **kw)
    monkeypatch.setattr(util, "_replace_retrying", replace)
    for n in range(3):
        send(cap, str(n))
    send(cap, "ignored", "Bash")
    cap.finish()
    rows = [json.loads(line) for line in (cap.directory / "manifest.jsonl").read_text().splitlines()]
    assert len(rows) == cap.report()["count"] == 3
    assert [row["seq"] for row in rows] == [1, 2, 3]
    assert len(observed) == 6
    for row in rows:
        data = (cap.directory / row["file"]).read_bytes()
        assert data == RAW.encode()
        assert row["sha256"] == hashlib.sha256(data).hexdigest()
        assert row["byte_size"] == len(data)
        assert row["arguments"] == {"account": "synthetic"}
        assert row["run_id"] == "run1" and row["job_id"] == "daily"
        assert row["started"] <= row["finished"]
    assert not list(cap.directory.glob(".tmp-*"))
    script = "import os,json,pathlib; p=pathlib.Path(os.environ['ARMADA_RAW_DIR']); rows=list(map(json.loads,(p/'manifest.jsonl').read_text().splitlines())); assert len(rows)==3; assert all((p/r['file']).is_file() for r in rows)"
    subprocess.run([sys.executable, "-c", script], env={**os.environ, "ARMADA_RAW_DIR": str(cap.directory)}, check=True)


def test_shared_directory_concurrent_runs_do_not_overwrite(realm):
    caps = [capture(realm, f"run{i}", capture_dir="raw/shared") for i in range(4)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda cap: send(cap), caps))
    rows = [json.loads(line) for line in (caps[0].directory / "manifest.jsonl").read_text().splitlines()]
    assert len(rows) == len({r["seq"] for r in rows}) == len({r["run_id"] for r in rows}) == 4
    assert all(cap.report()["count"] == 1 for cap in caps)


def test_text_line_endings_errors_and_duplicate_completion(realm):
    cap = capture(realm)
    send(cap, raw=json.dumps(" text\r\n\n "), error=True)
    send(cap, raw='"duplicate"')
    cap.finish()
    assert cap.report()["count"] == 1
    row = json.loads((cap.directory / "manifest.jsonl").read_text())
    assert (cap.directory / row["file"]).read_bytes() == b" text\r\n\n "
    assert row["is_error"] is True and row["encoding"] == "text"


@pytest.mark.parametrize("unsafe", ["../escape", "raw/../../escape", "..\\escape", "/outside",
    "C:\\outside", "C:outside", "\\\\server\\share", "raw//child", "raw/./child",
    "raw/.. /escape", "raw/file:stream", "raw/NUL", "raw/name.", "raw/{unknown}"])
def test_unsafe_paths_refused(realm, unsafe):
    with pytest.raises(ValueError):
        tc.validate({"capture_dir": unsafe}, realm, "daily")


def test_placeholders_and_default(realm):
    job = {"capture_tools": [PATTERN], "capture_dir": r"Finance\{date}\{job}\{run}"}
    target = tc.validate(job, realm, "daily", run_id="r1", date="2026-10-07")
    assert target == realm.parent / "workspace/Finance/2026-10-07/daily/r1"
    assert tc.validate({}, realm, "daily", date="2026-10-07") == realm.parent / "workspace/Finance/data/raw/2026-10-07/daily"


def test_settings_save_refuses_traversal_atomically(realm):
    from armada.routes.jobs import JobRoutes
    path = realm / "agents/a/jobs/daily.json"
    util.write_json_atomic(path, {"id": "daily", "prompt": "unchanged"})
    handler = JobRoutes()
    handler.realm = realm
    original = path.read_bytes()
    response = handler._save_job({"agent": "a", "job": "daily", "prompt": "changed", "capture_dir": "../outside"})
    assert response["ok"] is False
    assert path.read_bytes() == original
    response = handler._save_job({"agent": "a", "job": "daily", "capture_tools": [PATTERN],
                                 "capture_dir": "raw/{run}", "capture_keep_days": 5, "require_capture": True})
    assert response["ok"]
    assert json.loads(path.read_text())["capture_tools"] == [PATTERN]


@pytest.mark.parametrize("change", [{"capture_keep_days":0}, {"capture_keep_days":True},
    {"capture_tools":"*"}, {"capture_tools":[None]}, {"require_capture":"true"}])
def test_invalid_setting_types(realm, change):
    with pytest.raises(ValueError):
        tc.validate(change, realm, "daily")


@pytest.mark.parametrize("required,status", [(False,"warn"),(True,"error")])
def test_manifest_write_failure_and_require_capture(realm, monkeypatch, required, status):
    from armada import job_results
    cap = capture(realm, require_capture=required)
    write = util.write_text_atomic
    def fail_manifest(path, *a, **kw):
        if Path(path).name == "manifest.jsonl":
            raise OSError("disk full")
        return write(path, *a, **kw)
    monkeypatch.setattr(util, "write_text_atomic", fail_manifest)
    send(cap)
    cap.finish()
    result = {"execution":"completed", "audit_outcome":"clear", "app_errors":[],
              "evidence":{}, "delivery":[]}
    cap.audit(result)
    assert job_results.status(result) == status
    assert "disk full" in result["app_errors"][0]
    assert cap.report()["count"] == 0
    assert cap.records[0]["payload"] == RAW
    assert not (cap.directory / "manifest.jsonl").exists()


def test_missing_source_and_missing_result_are_incomplete(realm):
    cap = capture(realm)
    cap.on_event({"kind":"tool","id":"one","name":TOOL})
    cap.on_event({"kind":"tool_result","id":"one","content":"lossy preview"})
    cap.on_event({"kind":"tool","id":"two","name":TOOL})
    cap.finish()
    assert cap.report()["status"] == "incomplete"
    assert cap.report()["matched"] == 2
    assert len(cap.errors) == 2


def test_unsupported_engine_and_invalid_runtime_path_are_audited(realm):
    cap = tc.ToolCapture(realm, {"capture_tools":[PATTERN]}, "daily", "unsupported", "old", False, "a")
    assert "unsupported" in cap.errors[0]
    cap = capture(realm, capture_dir="../escape", require_capture=True)
    assert cap.directory is None and cap.errors


def test_replaced_capture_directory_is_refused_at_write_time(realm, monkeypatch):
    cap = capture(realm)
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda p: p == cap.directory or original(p))
    send(cap)
    assert cap.report()["count"] == 0
    assert "symlink" in cap.errors[0]


def test_retention_only_prunes_expired_registered_results(realm):
    with clock.frozen("2026-01-01T12:00:00+00:00"):
        old = capture(realm, "old", capture_dir="raw/shared", capture_keep_days=2)
        send(old)
        old.finish()
    with clock.frozen("2026-01-02T12:00:00+00:00"):
        keep = capture(realm, "keep", capture_dir="raw/shared", capture_keep_days=30)
        send(keep)
        keep.finish()
    foreign = old.directory / "personal.json"
    foreign.write_text("leave alone")
    with clock.frozen("2026-01-04T12:00:00+00:00"):
        result = tc.prune(realm)
    assert result == {"removed":1, "errors":[]}
    assert foreign.read_text() == "leave alone"
    rows = [json.loads(line) for line in (old.directory / "manifest.jsonl").read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["run_id"] == "keep"
    assert not old.index.exists() and keep.index.exists()


def test_retention_preserves_active_and_changed_files(realm):
    with clock.frozen("2026-01-01T12:00:00+00:00"):
        active = capture(realm, "active", capture_keep_days=1)
        send(active)
        changed = capture(realm, "changed", capture_keep_days=1)
        send(changed)
        changed.finish()
        row = changed.records[0]
        (changed.directory / row["file"]).write_text("user edit")
    with clock.frozen("2026-02-01T12:00:00+00:00"):
        result = tc.prune(realm)
    assert result["removed"] == 0 and result["errors"]
    assert active.index.exists()
    assert (changed.directory / row["file"]).read_text() == "user edit"


@pytest.mark.parametrize("required,broken,expected", [(False,False,"ok"), (False,True,"warn"), (True,True,"error")])
def test_job_run_transcript_env_and_failure_policy(realm, monkeypatch, required, broken, expected):
    ad = realm / "agents/a"
    util.write_json_atomic(ad / "agent.json", {"id":"a"})
    job = {"id":"daily", "prompt":"Read data into {raw_dir}", "capture_tools":[PATTERN], "require_capture":required}
    util.write_json_atomic(ad / "jobs/daily.json", job)
    class Engine(MockEngine):
        capabilities = ProviderCapabilities(streaming=True, raw_tool_results=True, tool_denials=True)
        def run_stream(self, on_event, **kw):
            raw_dir = Path(kw["env"]["ARMADA_RAW_DIR"])
            assert str(raw_dir) in kw["prompt"] and "{raw_dir}" not in kw["prompt"]
            for n in range(3):
                on_event({"kind":"tool","id":str(n),"name":TOOL,"input":{}})
                source = result_source(loads_event('{"result":'+RAW+'}'), ("missing" if broken else "result",))
                on_event({"kind":"tool_result","id":str(n),"raw_result":source})
                if not broken:
                    rows = (raw_dir / "manifest.jsonl").read_text().splitlines()
                    assert len(rows) == n + 1  # visible before the next event, in the same turn
            return RunResult(ok=True, output="Finished")
    report = runner.run_job(realm, "a", "daily", engine=Engine())
    assert report["status"] == expected
    assert report["capture"]["count"] == (0 if broken else 3)
    transcript = job_history.transcript(ad, report)
    assert all("raw_result" not in e for e in transcript["events"])
    if not broken:
        assert len(transcript["tool_results"]) == 3
        for record in transcript["tool_results"]:
            data = (Path(report["capture"]["directory"]) / record["file"]).read_bytes()
            assert hashlib.sha256(data).hexdigest() == hashlib.sha256(record["payload"].encode()).hexdigest()
    from armada.webui.jobresults import result_html
    html = result_html(report, transcript)
    assert "manifest.jsonl" in html and ("Capture incomplete" in html) == broken


def test_no_patterns_leave_capture_off(realm):
    ad = realm / "agents/a"
    util.write_json_atomic(ad / "agent.json", {"id":"a"})
    util.write_json_atomic(ad / "jobs/daily.json", {"id":"daily","prompt":"hello"})
    report = runner.run_job(realm, "a", "daily", engine=MockEngine())
    assert "capture" not in report
    assert not (realm / "capture-index").exists()


def test_real_protocol_fixtures_roundtrip(realm, monkeypatch):
    from armada.engine.claude import _ClaudeStream
    from armada.engine.codex import _AppStream, _Stream
    fixtures = Path(__file__).parent / "fixtures/tool_capture"
    for name, parser in (("claude", _ClaudeStream), ("codex-app", _AppStream), ("codex-exec", _Stream)):
        cap = capture(realm, name, capture_dir=name)
        state = parser(cap.on_event, "")
        for line in (fixtures / (name + ".jsonl")).read_text(encoding="utf-8").splitlines():
            state.accept(loads_event(line))
        cap.finish()
        assert cap.report()["count"] == 3 and not cap.errors, cap.report()
        for record in cap.records:
            assert (cap.directory / record["file"]).read_bytes() == record["payload"].encode()


def test_gemini_fixture_uses_canonical_mcp_names_and_preserves_text(realm, monkeypatch):
    from armada.engine import gemini
    from armada.engine.process import ProcessResult
    engine = gemini.GeminiEngine()
    monkeypatch.setattr(engine, "_launcher", lambda: ["fixture"])
    monkeypatch.setattr(engine, "auth_status", lambda: {"logged_in":True})
    fixture = Path(__file__).parent / "fixtures/tool_capture/gemini.jsonl"
    def supervise(args, **kw):
        assert kw["env"]["ARMADA_RAW_DIR"] == "raw"
        for line in fixture.read_text().splitlines():
            kw["on_line"](line)
        kw["on_line"](json.dumps({"event":"result","result":{"status":"SUCCESS","response":"done"}}))
        return ProcessResult(returncode=0)
    monkeypatch.setattr(gemini, "supervise", supervise)
    cap = capture(realm)
    result = engine.run_stream("", "", cwd=str(realm), on_event=cap.on_event, env={"ARMADA_RAW_DIR":"raw"})
    cap.finish()
    assert result.ok and cap.report()["count"] == 3 and not cap.errors
    assert all(record["encoding"] == "text" for record in cap.records)
    assert all(record["payload"].endswith("\r\n") for record in cap.records)


def test_large_unicode_payload_is_not_the_ui_preview(realm):
    cap = capture(realm)
    text = " \u20ac caf\u00e9 \U0001f310 " * 2000 + "\r\n"
    send(cap, raw=json.dumps(text, ensure_ascii=False))
    cap.finish()
    record = cap.records[0]
    assert len(record["payload"]) > 4000
    assert (cap.directory / record["file"]).read_bytes() == text.encode("utf-8")


def test_uncorrelated_result_marks_capture_incomplete(realm):
    cap = capture(realm)
    cap.on_event({"kind":"tool_result","id":"unknown",
                  "raw_result":result_source(loads_event('{"result":0}'), ("result",))})
    cap.finish()
    assert "corresponding tool name" in cap.errors[0]


def test_settings_page_exposes_saved_capture_values(realm):
    from armada import reader, webui
    ad = realm / "agents/a"
    util.write_json_atomic(ad / "agent.json", {"id":"a","display":"Fixture"})
    util.write_json_atomic(ad / "jobs/daily.json", {"id":"daily","name":"Daily","prompt":"Read",
        "capture_tools":[PATTERN],"capture_dir":"raw/{run}","capture_keep_days":7,"require_capture":True})
    page = webui.render_job(reader.read(realm), realm, "a", "daily")
    assert PATTERN in page and 'id="j-capture-tools"' in page
    assert 'value="raw/{run}"' in page and 'id="j-capture-keep"' in page
    assert 'value="7"' in page and 'id="j-require-capture" type="checkbox" checked' in page
    assert "Command jobs are unsupported" in page and "{raw_dir}" in page


@pytest.mark.skipif(os.name != "nt", reason="Windows junction safety")
def test_real_windows_junction_is_rejected(realm):
    work = realm.parent / "workspace"
    outside = realm.parent / "outside"
    outside.mkdir()
    link = work / "linked"
    made = subprocess.run(["cmd.exe","/c","mklink","/J",str(link),str(outside)],
        capture_output=True, creationflags=0x08000000)
    if made.returncode:
        pytest.skip("Junction creation unavailable")
    try:
        with pytest.raises(ValueError, match="junction|reparse"):
            tc.validate({"capture_tools":[PATTERN],"capture_dir":"linked/raw"}, realm, "daily")
        assert not list(outside.iterdir())
    finally:
        os.rmdir(link)  # Remove only the junction itself; never recurse into its target.


def test_housekeeping_invokes_capture_retention(realm, monkeypatch):
    from armada import sysjobs, notify
    monkeypatch.setattr(notify, "prune", lambda root: 2)
    seen = []
    def prune(root):
        seen.append(root)
        return {"removed":3,"errors":[]}
    monkeypatch.setattr(tc, "prune", prune)
    result = sysjobs._job_prune_history(realm)
    assert seen == [realm] and result["ok"]
    assert "3 captured result(s)" in result["detail"]


def test_proposal_approval_rejects_traversal_before_saving(realm, monkeypatch):
    from armada import jobs
    src = realm / "proposal.json"
    src.write_text("{}")
    monkeypatch.setattr(jobs, "_find_pending", lambda *a: (
        {"name":"Daily","id":"daily","prompt":"read","capture_dir":"../escape"}, src))
    result = jobs.approve(realm, "a", "daily")
    assert result["ok"] is False and src.exists()
    assert not (realm / "agents/a/jobs/daily.json").exists()
