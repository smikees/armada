"""Synthetic regressions for provider startup, retry grouping and realm lock release."""
import copy
import json
import threading
import time
from pathlib import Path

import pytest

from armada import job_history, job_results, job_retries, realmops, scheduler, scheduler_state, util
from armada.engine.base import EngineAdapter, RunResult
from armada.engine.codex import CodexEngine
from armada.engine.contracts import RunRequest
from armada.engine.process import ProcessResult
from armada.engine.claude import ClaudeEngine
from tests.test_job_results import contract, evaluate
from tests.test_jobcal import _mk_realm, PAST


def realm(path):
    path.mkdir()
    (path / "realm.json").write_text('{"name":"Synthetic"}')
    return path


def test_codex_probe_uses_real_rpc_fields_and_preserves_policy(tmp_path, monkeypatch):
    import armada.engine.codex as module
    engine = CodexEngine()
    engine.writable_roots = [str(tmp_path)]
    engine.network_access = False
    monkeypatch.setattr(engine, "_launcher", lambda: ["cli.exe"])
    monkeypatch.setattr(engine, "_mcp_args", lambda *a, **k: ["-c", "mcp_servers.denied.enabled=false"])
    sent = []
    def rpc(args, *, start, on_message, **kwargs):
        start(sent.append)
        assert on_message({"id":1,"result":{}}, sent.append) is False
        assert on_message({"id":2,"result":{"exitCode":0,"stdout":"ARMADA_SANDBOX_READY\r\n","stderr":""}}, sent.append)
        assert kwargs["env"] is None
        assert "mcp_servers.denied.enabled=false" in args
        return ProcessResult()
    monkeypatch.setattr(module, "supervise_rpc", rpc)
    assert engine._execution_probe(RunRequest("", "", cwd=str(tmp_path), allow_tools=True))["ok"]
    cmd = sent[-1]["params"]
    assert sent[-1]["method"] == "command/exec"
    assert cmd["sandboxPolicy"] == {"type":"workspaceWrite","writableRoots":[str(tmp_path)],"networkAccess":False}
    assert "outputBytesCap" not in cmd
    assert cmd["command"][-1] == "Write-Output ARMADA_SANDBOX_READY"


@pytest.mark.skipif(__import__("os").name != "nt", reason="Windows sandbox readiness")
def test_codex_fallback_verified_before_model_turn(monkeypatch):
    engine = CodexEngine()
    calls = []
    monkeypatch.setattr(engine, "_launcher", lambda: engine._runtime_launcher or ["desktop.exe"])
    monkeypatch.setattr(engine, "_standalone_launcher", lambda: ["standalone.exe"])
    def probe(*args):
        calls.append(engine._launcher())
        return {"ok":False,"reason":"windows sandbox: helper_unknown_error"} if len(calls)==1 else {"ok":True,"reason":""}
    monkeypatch.setattr(engine, "_execution_probe", probe)
    monkeypatch.setattr(EngineAdapter, "execute", lambda *a, **k: RunResult(True, "Ready"))
    result = engine.execute(RunRequest("", "", allow_tools=True))
    assert calls == [["desktop.exe"], ["standalone.exe"]]
    assert result.ok and result.raw["runtime_readiness"]["fallback"]
    assert "helper_unknown_error" in result.raw["runtime_readiness"]["primary_error"]


@pytest.mark.skipif(__import__("os").name != "nt", reason="Windows sandbox readiness")
@pytest.mark.parametrize("binary,error,cancelled", [
    ("custom.exe", "windows sandbox: helper_unknown_error", False),
    ("codex", "Invalid MCP inventory", False),
    ("codex", "Run stopped by the owner.", True)])
def test_startup_failure_never_runs_model_or_changes_explicit_runtime(monkeypatch, binary, error, cancelled):
    engine = CodexEngine(binary)
    monkeypatch.setattr(engine, "_launcher", lambda: ["primary.exe"])
    monkeypatch.setattr(engine, "_execution_probe", lambda *a: {"ok":False,"reason":error,"cancelled":cancelled})
    monkeypatch.setattr(engine, "_standalone_launcher", lambda: pytest.fail("Unexpected fallback"))
    monkeypatch.setattr(EngineAdapter, "execute", lambda *a, **k: pytest.fail("Model must not start"))
    result = engine.execute(RunRequest("", "", allow_tools=True))
    assert not result.ok and result.cancelled == cancelled
    assert result.raw["startup_failure"]["code"] == "execution_environment"


def test_infrastructure_failures_do_not_consume_business_retries(tmp_path, monkeypatch):
    (tmp_path/"agents/a/jobs").mkdir(parents=True)
    job = {"id":"j","retries":3,"prompt":"Same authorized work"}
    util.write_json_atomic(tmp_path/"agents/a/jobs/j.json", job)
    failure = {"run_id":"r","status":"error","result":{"execution":"failed","delivery":[],
        "startup_failure":{"code":"execution_environment","reason":"broken helper"}}}
    calls = []
    job_retries.execute(tmp_path,"a","j",job,lambda j:calls.append(j) or failure)
    assert len(calls)==1
    assert calls[0]["prompt"]==job["prompt"]
    assert calls[0]["_retry_series"]["attempt"]==1
    assert util.read_json_state(job_retries.state_path(tmp_path,"a","j"))["state"]=="finished"


def test_claude_health_inventory_gets_bounded_90_seconds(monkeypatch):
    import armada.engine.claude as module
    from types import SimpleNamespace
    engine = ClaudeEngine()
    monkeypatch.setattr(engine,"_direct",lambda:True)
    monkeypatch.setattr(engine,"_launcher",lambda:["claude.exe"])
    timeouts = []
    def run(args, **kwargs):
        timeouts.append(kwargs["timeout"])
        return SimpleNamespace(returncode=0, stdout="2.1.263" if "--version" in args else "", stderr="")
    monkeypatch.setattr(module.subprocess,"run",run)
    monkeypatch.setattr(module,"_mcp_inventory",lambda output:[])
    engine._mcp_args([])
    assert timeouts == [25,90]


def test_claude_timeout_is_actionable_startup_failure(monkeypatch):
    import subprocess
    engine = ClaudeEngine()
    monkeypatch.setattr(engine,"_launcher",lambda:["claude.exe"])
    monkeypatch.setattr(engine,"_mcp_args",lambda *a,**k:(_ for _ in ()).throw(subprocess.TimeoutExpired("inventory",90)))
    result = engine.run_stream("", "", allow_tools=True)
    assert result.raw["startup_failure"]["code"] == "connector_discovery"


@pytest.mark.parametrize("audit", ["clear","not_applicable"])
def test_research_notes_and_future_announcements_are_not_audit_breaches(tmp_path, audit):
    data = contract(tmp_path,audit=audit)
    data["evidence"].update(observations=["Calendar event discovered"],
                            expected_unknowns=["Official date has not been announced"])
    result = evaluate(tmp_path,data)
    assert result["audit_outcome"] == audit and job_results.status(result)=="ok"
    data["evidence"]["missing_inputs"]=["Required data unavailable"]
    assert evaluate(tmp_path,data)["audit_outcome"]=="incomplete"


def test_optional_research_fields_are_validated(tmp_path):
    data = contract(tmp_path)
    data["evidence"]["observations"] = "not a list"
    assert evaluate(tmp_path,data)["validation_errors"]


def test_calendar_groups_proven_retries_and_keeps_manual_runs(tmp_path):
    from armada import webui
    attempts=[{"run_id":str(i),"ts":PAST.isoformat()+f"T09:0{i}:00","task":"hand-brief",
               "status":"ok" if i==3 else "error","retry":{"series_id":"scheduled","attempt":i+1}}
              for i in range(4)]
    manual={"run_id":"manual","ts":PAST.isoformat()+"T10:00:00","task":"hand-brief","status":"ok",
            "retry":{"series_id":"manual","attempt":1}}
    r=_mk_realm(tmp_path,attempts+[manual])
    events=webui._jobcal_events(r,tmp_path,PAST,PAST)
    assert len(events)==2
    scheduled=next(e for e in events if e["attempt_count"]==4)
    assert scheduled["status"]=="success" and scheduled["run_id"]=="3"
    assert scheduled["ts"].endswith("09:00")
    assert next(e for e in events if e["run_id"]=="manual")["ts"].endswith("10:00")


def test_legacy_journal_correlates_exact_run_ids_without_rewriting(tmp_path):
    events=[{"run_id":str(i),"task":"j","ts":f"2026-10-08T09:0{i}:00","status":"error"} for i in range(4)]
    original=copy.deepcopy(events)
    util.write_json_atomic(tmp_path/"runs/retries/j.json",{"schema_version":1,"series_id":"old",
                           "attempts":[{"run_id":str(i)} for i in range(4)]})
    groups=job_history.logical_runs(tmp_path,events)
    assert len(groups)==1 and groups[0]["attempt_count"]==4
    assert events==original


@pytest.mark.parametrize("change", ["archived","removed","pause"])
def test_scheduler_releases_kernel_lease_on_lifecycle_change(tmp_path, change):
    root=realm(tmp_path/"r")
    lease=scheduler_state.acquire(root)
    owned={root:lease};others=[root];stop=threading.Event()
    if change=="archived": util.mutate_json(root/"realm.json",lambda x:x.update(archived=True))
    rescan=(lambda:[]) if change=="removed" else None
    pause=scheduler_state._pause_path(root)
    if change=="pause": util.write_json_atomic(pause,{"schema_version":1,"pid":__import__("os").getpid(),
                                                        "expires":time.time()+60,"token":"synthetic"})
    try:
        scheduler._reconcile_leases(rescan,owned,others,primary=root,listener_stop=stop)
        assert not owned and not others and stop.is_set() and scheduler_state.holder(root) is None
    finally:
        lease.close()
        pause.unlink(missing_ok=True)


def test_delete_waits_for_cooperative_release_and_blocks_reacquisition(tmp_path, monkeypatch):
    root=realm(tmp_path/"r")
    lease=scheduler_state.acquire(root)
    owned={root:lease};stop=threading.Event()
    def watch():
        while not stop.wait(.01):
            scheduler._reconcile_leases(None,owned,[])
    worker=threading.Thread(target=watch);worker.start()
    def recycle(path):
        assert scheduler_state.holder(path) is None
        assert scheduler_state.acquire(path) is None
        return {"ok":True}
    monkeypatch.setattr(realmops,"_recycle",recycle)
    try:
        result=realmops.delete(root)
        assert result["ok"] and result["recycled"]
        assert not scheduler_state.lifecycle_paused(root)
    finally:
        stop.set();worker.join(2);lease.close()


def test_unresponsive_old_scheduler_preserves_folder_and_reports_reason(tmp_path, monkeypatch):
    root=realm(tmp_path/"r")
    lease=scheduler_state.acquire(root)
    original=scheduler_state.pause_for_lifecycle
    monkeypatch.setattr(scheduler_state,"pause_for_lifecycle",lambda r:original(r,timeout=.03))
    monkeypatch.setattr(realmops,"_recycle",lambda r:pytest.fail("Must not recycle a locked realm"))
    try:
        result=realmops.delete(root)
        assert not result["ok"] and "scheduler has not released" in result["error"]
        assert (root/"realm.json").exists()
        assert not scheduler_state.lifecycle_paused(root)
    finally: lease.close()


def test_stopped_listener_cannot_recreate_deleted_realm(tmp_path):
    from armada import telegram
    root=tmp_path/"deleted"
    stop=threading.Event();stop.set()
    telegram._save_state(root,{"listener":time.time()},stop=stop)
    assert not root.exists()

@pytest.mark.parametrize("advertised,ok", [(["gpt-6.1-sol"],True),(["gpt-6-sol"],False)])
def test_readiness_checks_selected_model_without_silently_switching(tmp_path,monkeypatch,advertised,ok):
    import armada.engine.codex as module
    engine=CodexEngine()
    monkeypatch.setattr(engine,"_launcher",lambda:["cli.exe"])
    monkeypatch.setattr(engine,"_mcp_args",lambda *a,**k:[])
    sent=[]
    def rpc(args,*,start,on_message,**kwargs):
        start(sent.append)
        on_message({"id":1,"result":{}},sent.append)
        assert not on_message({"id":2,"result":{"exitCode":0,"stdout":"ARMADA_SANDBOX_READY"}},sent.append)
        assert sent[-1]["method"]=="model/list"
        assert on_message({"id":3,"result":{"data":[{"model":m} for m in advertised],"nextCursor":None}},sent.append)
        return ProcessResult()
    monkeypatch.setattr(module,"supervise_rpc",rpc)
    result=engine._execution_probe(RunRequest("","",model="gpt-6.1-sol",cwd=str(tmp_path),allow_tools=True))
    assert result["ok"]==ok
    if not ok: assert "gpt-6.1-sol is unavailable" in result["reason"]

@pytest.mark.skipif(__import__("os").name != "nt", reason="Windows readiness")
def test_startup_failure_and_retry_identity_reach_saved_job_report(tmp_path,monkeypatch):
    from armada import runner
    ad=tmp_path/"agents/a"
    util.write_json_atomic(tmp_path/"realm.json",{"name":"Synthetic"})
    util.write_json_atomic(ad/"agent.json",{"id":"a"})
    util.write_json_atomic(ad/"jobs/work.json",{"id":"work","prompt":"Synthetic",
        "allow_tools":True,"retries":3,"model":"gpt-6-sol"})
    engine=CodexEngine()
    monkeypatch.setattr(engine,"_launcher",lambda:["fixture.exe"])
    monkeypatch.setattr(engine,"_standalone_launcher",lambda:None)
    monkeypatch.setattr(engine,"_execution_probe",lambda *a:{"ok":False,"reason":"windows sandbox: helper_unknown_error"})
    monkeypatch.setattr(engine,"run_stream",lambda **k:pytest.fail("Job must not start"))
    report=runner.run_job(tmp_path,"a","work",engine=engine)
    assert report["result"]["startup_failure"]["code"]=="execution_environment"
    assert report["status"]=="error" and report["retry"]["attempt"]==1
    assert report["tokens"]["total"]==0
    stored=job_history.reports(ad,"work")
    assert len(stored)==1 and stored[0]["runtime_readiness"]["ok"] is False
    assert stored[0]["retry"]["series_id"]==report["retry"]["series_id"]
