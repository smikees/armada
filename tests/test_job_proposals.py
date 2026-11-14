"""Agent-authored job proposals: validation, isolation from the scheduler, approve/reject."""
import json
from pathlib import Path

from armada import jobs, scheduler, reader


def _mk_agent(root: Path, aid: str = "warren") -> Path:
    ad = root / "agents" / aid
    (ad / "jobs" / jobs.PENDING).mkdir(parents=True, exist_ok=True)
    (ad / "agent.json").write_text(json.dumps({"id": aid, "display": aid.title()}), encoding="utf-8")
    (root / "realm.json").write_text(json.dumps({"name": "T"}), encoding="utf-8")
    return ad


def _propose(ad: Path, slug: str, job: dict):
    (ad / "jobs" / jobs.PENDING / f"{slug}.json").write_text(json.dumps(job), encoding="utf-8")


# --- validation ---

def test_validate_good_agent_job():
    ok, errs, norm = jobs.validate({"name": "Test Job 910", "kind": "agent",
                                    "allow_tools": False, "prompt": "do the thing", "schedule": "daily 09:00"})
    assert ok and not errs
    assert norm["id"] == "test-job-910"       # slug derived from name
    assert norm["kind"] == "agent"


def test_validate_requires_name_and_prompt():
    ok, errs, _ = jobs.validate({"kind": "agent"})
    assert not ok
    assert any("name" in e for e in errs)
    assert any("prompt" in e for e in errs)


def test_validate_command_needs_run_and_cron_checked():
    ok, errs, _ = jobs.validate({"name": "c", "id": "c", "kind": "command"})
    assert not ok and any("run" in e for e in errs)
    bad, e2, _ = jobs.validate({"name": "c", "id": "c", "kind": "command",
                                "run": "python x.py", "cron": "not a cron"})
    assert not bad and any("cron" in e for e in e2)
    good, e3, _ = jobs.validate({"name": "c", "id": "c", "kind": "command",
                                 "run": "python x.py", "cron": "0 9 * * 1-5"})
    assert good and not e3


def test_validate_simple_schedule_and_manual():
    assert jobs.validate({"name": "a", "id": "a", "allow_tools": False, "prompt": "p", "schedule": "mon-fri 14:30"})[0]
    assert jobs.validate({"name": "a", "id": "a", "allow_tools": False, "prompt": "p", "schedule": "manual"})[0]
    assert not jobs.validate({"name": "a", "id": "a", "allow_tools": False, "prompt": "p", "schedule": "someday"})[0]


def test_bad_id_rejected():
    ok, errs, _ = jobs.validate({"name": "x", "id": "Bad ID!", "allow_tools": False, "prompt": "p"})
    assert not ok and any("kebab" in e for e in errs)


# --- isolation: pending proposals never reach the scheduler or reader ---

def test_pending_hidden_from_scheduler_and_reader(tmp_path):
    ad = _mk_agent(tmp_path)
    _propose(ad, "test-job-910", {"name": "T", "id": "test-job-910", "kind": "agent",
                                   "allow_tools": False, "prompt": "p", "cron": "0 9 * * *", "enabled": True})
    # even with enabled:true, a proposal in _pending is invisible to the scheduler…
    assert list(scheduler.iter_jobs(tmp_path)) == []
    # …and to the realm reader (no phantom job on the agent)
    realm = reader.read_native(tmp_path)
    assert sum(len(a.jobs) for a in realm.agents) == 0
    # but it IS discoverable as a proposal
    assert jobs.count_pending(tmp_path) == 1
    mine = jobs.list_for_agent(tmp_path, "warren")
    assert len(mine) == 1 and mine[0]["ok"]


# --- approve / reject ---

def test_approve_promotes_and_stamps(tmp_path):
    ad = _mk_agent(tmp_path)
    _propose(ad, "test-job-910", {"name": "Test Job 910", "id": "test-job-910",
                                  "kind": "agent", "allow_tools": False, "prompt": "p", "schedule": "daily 09:00"})
    res = jobs.approve(tmp_path, "warren", "test-job-910")
    assert res["ok"] and res["id"] == "test-job-910"
    live = ad / "jobs" / "test-job-910.json"
    assert live.exists()
    jc = json.loads(live.read_text(encoding="utf-8"))
    assert jc["enabled"] is True and jc["proposed_by"] == "warren"
    assert jc.get("approved_at") and jc.get("created")
    # pending file gone; scheduler now sees exactly one job
    assert not (ad / "jobs" / jobs.PENDING / "test-job-910.json").exists()
    assert [j for _a, _j, j in scheduler.iter_jobs(tmp_path)]


def test_approve_conflict_with_existing_job(tmp_path):
    ad = _mk_agent(tmp_path)
    (ad / "jobs" / "dup.json").write_text(json.dumps({"id": "dup", "name": "Dup", "kind": "agent",
                                                      "allow_tools": False, "prompt": "p"}), encoding="utf-8")
    _propose(ad, "dup", {"name": "Dup", "id": "dup", "kind": "agent", "allow_tools": False, "prompt": "p"})
    res = jobs.approve(tmp_path, "warren", "dup")
    assert not res["ok"] and "review" in res["error"].lower()


def test_approve_rejects_invalid(tmp_path):
    ad = _mk_agent(tmp_path)
    _propose(ad, "broken", {"name": "", "kind": "agent"})   # no name, no prompt
    res = jobs.approve(tmp_path, "warren", "broken")
    assert not res["ok"]
    # still sitting in _pending, not promoted
    assert (ad / "jobs" / jobs.PENDING / "broken.json").exists()


def test_reject_deletes_proposal(tmp_path):
    ad = _mk_agent(tmp_path)
    _propose(ad, "test-job-910", {"name": "T", "id": "test-job-910", "kind": "agent", "allow_tools": False, "prompt": "p"})
    assert jobs.reject(tmp_path, "warren", "test-job-910")["ok"]
    assert not (ad / "jobs" / jobs.PENDING / "test-job-910.json").exists()
    assert jobs.count_pending(tmp_path) == 0


def test_approve_missing_proposal(tmp_path):
    _mk_agent(tmp_path)
    assert not jobs.approve(tmp_path, "warren", "nope")["ok"]


def test_status_and_ledger(tmp_path):
    ad = _mk_agent(tmp_path)
    # one pending, one approved-live, one to be rejected
    _propose(ad, "p1", {"name": "P1", "id": "p1", "kind": "agent", "allow_tools": False, "prompt": "x"})
    _propose(ad, "will-approve", {"name": "Appr", "id": "will-approve", "kind": "agent", "allow_tools": False, "prompt": "x"})
    _propose(ad, "will-reject", {"name": "Rej", "id": "will-reject", "kind": "agent", "allow_tools": False, "prompt": "x"})
    jobs.sync_proposals(tmp_path, "warren")          # record 'proposed' events (as the runner does)
    jobs.approve(tmp_path, "warren", "will-approve")
    jobs.reject(tmp_path, "warren", "will-reject")
    st = jobs.status_for_agent(tmp_path, "warren")
    assert [x["id"] for x in st["pending"]] == ["p1"]
    assert [x["id"] for x in st["approved"]] == ["will-approve"]
    assert [x["id"] for x in st["rejected"]] == ["will-reject"]
    # the durable ledger records every event (proposed/approved/rejected)
    evs = jobs.ledger_events(tmp_path, "warren")
    kinds = {(e["id"], e["event"]) for e in evs}
    assert ("p1", "proposed") in kinds
    assert ("will-approve", "approved") in kinds
    assert ("will-reject", "rejected") in kinds
    # full history is exposed for the agent
    assert any(h["id"] == "will-reject" and h["event"] == "rejected" for h in st["history"])
    assert not (ad / "jobs" / jobs.PENDING / "will-reject.json").exists()


def test_sync_proposals_idempotent(tmp_path):
    _mk_agent(tmp_path)
    ad = tmp_path / "agents" / "warren"
    _propose(ad, "p1", {"name": "P1", "id": "p1", "kind": "agent", "allow_tools": False, "prompt": "x"})
    jobs.sync_proposals(tmp_path, "warren")
    jobs.sync_proposals(tmp_path, "warren")          # second call must not double-log
    proposed = [e for e in jobs.ledger_events(tmp_path, "warren") if e["event"] == "proposed" and e["id"] == "p1"]
    assert len(proposed) == 1


def test_change_proposal_preserves_saved_job_until_reviewed_approval(tmp_path):
    from armada import run_policy
    ad = _mk_agent(tmp_path)
    original = {'id':'daily','name':'Daily','kind':'agent','allow_tools':False,'prompt':'Original', 'schedule':'daily 09:00', 'timeout':600}
    path = ad/'jobs/daily.json'
    path.write_text(json.dumps(original), encoding='utf-8')
    run_policy.seal_job(tmp_path, 'warren', original)
    changed = {**original, 'prompt':'Changed', 'critical':True}
    _propose(ad, 'daily', changed)
    assert json.loads(path.read_text()) == original
    assert run_policy.verify_job(tmp_path, 'warren', original)
    reviewed = jobs.review(tmp_path, 'warren', jobs.validate(changed)[2])
    assert {c['field'] for c in reviewed['changes']} == {'prompt', 'critical', 'enabled'}
    assert jobs.approve(tmp_path, 'warren', 'daily', review_token=reviewed['token'])['ok']
    saved = json.loads(path.read_text())
    assert saved['prompt'] == 'Changed' and saved['timeout'] == 600
    assert run_policy.verify_job(tmp_path, 'warren', saved)
    assert not (ad/'jobs/_pending/daily.json').exists()


def test_changed_review_cannot_overwrite_new_owner_edit(tmp_path):
    ad = _mk_agent(tmp_path)
    original = {'id':'daily','name':'Daily','kind':'agent','allow_tools':False,'prompt':'Original'}
    path = ad/'jobs/daily.json';path.write_text(json.dumps(original))
    _propose(ad, 'daily', {**original, 'prompt':'Proposed'})
    proposal = jobs.validate(json.loads((ad/'jobs/_pending/daily.json').read_text()))[2]
    token = jobs.review(tmp_path, 'warren', proposal)['token']
    path.write_text(json.dumps({**original, 'prompt':'New owner edit'}))
    assert not jobs.approve(tmp_path, 'warren', 'daily', review_token=token)['ok']
    assert json.loads(path.read_text())['prompt'] == 'New owner edit'
    assert jobs.reject(tmp_path, 'warren', 'daily')['ok']
    assert json.loads(path.read_text())['prompt'] == 'New owner edit'


def test_cross_agent_proposal_requires_owner_opt_in_and_coordinator(tmp_path):
    from armada import run_policy, util
    ad = _mk_agent(tmp_path)
    util.write_json_atomic(tmp_path/'agents/other/agent.json', {'id':'other'})
    job = {'id':'daily','name':'Daily','kind':'agent','allow_tools':False,'prompt':'Original'}
    util.write_json_atomic(tmp_path/'agents/other/jobs/daily.json', job)
    proposal = {**job, 'target_agent':'other', 'prompt':'Proposed'}
    _propose(ad, 'daily', proposal)
    assert not jobs.approve(tmp_path, 'warren', 'daily')['ok']
    util.write_json_atomic(ad/'agent.json', {'id':'warren','coordinator':True})
    assert not jobs.approve(tmp_path, 'warren', 'daily')['ok']
    run_policy.save(tmp_path, {'coordinator_may_propose_changes':True})
    reviewed = jobs.review(tmp_path, 'warren', jobs.validate(proposal)[2])
    assert jobs.approve(tmp_path, 'warren', 'daily', review_token=reviewed['token'])['ok']
    assert json.loads((tmp_path/'agents/other/jobs/daily.json').read_text())['prompt'] == 'Proposed'


def test_held_job_notifies_once_before_due_time(tmp_path, monkeypatch):
    from armada import run_policy,util
    ad = _mk_agent(tmp_path)
    job = {'id':'daily','kind':'agent','allow_tools':False,'prompt':'Approved','schedule':'daily 23:59'}
    run_policy.seal_job(tmp_path, 'warren', job)
    changed = {**job, 'prompt':'Changed without approval'}
    notices = []
    monkeypatch.setattr('armada.notify.emit',lambda *a:notices.append(a))
    assert run_policy.held_reason(tmp_path,'warren',changed)
    assert run_policy.held_reason(tmp_path,'warren',changed)
    assert len(notices)==1
    run_policy.seal_job(tmp_path,'warren',changed)
    assert not run_policy.held_reason(tmp_path,'warren',changed)


def test_coordinator_cannot_self_promote_after_owner_opt_in(tmp_path):
    from armada import run_policy,util
    ad = _mk_agent(tmp_path)
    util.write_json_atomic(tmp_path/'agents/other/agent.json', {'id':'other'})
    job={'id':'daily','name':'Daily','kind':'agent','allow_tools':False,'prompt':'Original'}
    util.write_json_atomic(tmp_path/'agents/other/jobs/daily.json',job)
    run_policy.save(tmp_path,{'coordinator_may_propose_changes':True})
    util.write_json_atomic(ad/'agent.json',{'id':'warren','coordinator':True})
    _propose(ad,'daily',{**job,'target_agent':'other'})
    assert not jobs.approve(tmp_path,'warren','daily')['ok']
