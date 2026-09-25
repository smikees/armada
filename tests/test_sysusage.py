"""System usage (armada/sysusage.py): ARMADA's own spend is a default line in every usage view.

Mihai, 2026-09-25: "System (any jobs + Alexander if any support conversations) should be a default
line in all cost reports/graphs."
"""
import datetime
import json
import types

from armada import sysjobs, sysusage, webui


def _realm(monkeypatch, agent_runs=()):
    warren = types.SimpleNamespace(id="warren", display="Warren")
    realm = types.SimpleNamespace(coordinator=None, members=[warren])
    monkeypatch.setattr(webui._core, "_runs", lambda root, aid: list(agent_runs) if aid == "warren" else [])
    monkeypatch.setattr(webui.models, "options", lambda root: [("claude-opus-5", "Claude Opus 5")])
    return realm


def _today_ts():
    return datetime.date.today().isoformat() + "T10:00:00"


def test_record_and_read_back(tmp_path):
    sysusage.record(tmp_path, "alexander", "claude-opus-5-5", {"total": 1200, "api_equiv_usd": 0.03})
    sysusage.record(tmp_path, "system:usage-keepalive", "claude-haiku-4-5", {"total": 40}, ok=False)
    rs = sysusage.runs(tmp_path)
    assert [r["task"] for r in rs] == ["alexander", "system:usage-keepalive"]
    assert rs[0]["tokens"]["total"] == 1200 and rs[1]["status"] == "failed"


def test_a_missing_or_corrupt_file_reads_as_nothing(tmp_path):
    assert sysusage.runs(tmp_path) == []
    (tmp_path / sysusage.FILE).write_text("not json\n{\"ts\": \"2026-09-25T10:00:00\"}\n", "utf-8")
    assert len(sysusage.runs(tmp_path)) == 1


def test_system_is_always_the_last_row_even_at_zero(monkeypatch, tmp_path):
    realm = _realm(monkeypatch, [{"ts": _today_ts(), "tokens": {"total": 100}, "model": "claude-opus-5"}])
    d = webui._usage_data(realm, tmp_path, "line", "7d")
    assert d["agents"][-1] == {"name": "System", "tok": 0, "color": sysusage.COLOR, "system": True}
    assert d["total"] == 100


def test_system_spend_counts_in_the_line_the_graph_and_the_30_day_totals(monkeypatch, tmp_path):
    realm = _realm(monkeypatch, [{"ts": _today_ts(), "tokens": {"total": 100, "api_equiv_usd": 1.0},
                                  "model": "claude-opus-5"}])
    (tmp_path / sysusage.FILE).write_text(json.dumps(
        {"ts": _today_ts(), "task": "alexander", "model": "claude-opus-5-5",
         "tokens": {"total": 50, "api_equiv_usd": 0.5}}) + "\n", "utf-8")
    line = webui._usage_data(realm, tmp_path, "line", "today")
    assert line["total"] == 150 and line["agents"][-1]["tok"] == 50
    assert line["total_30d"] == 150 and line["usd_30d"] == 1.5
    graph = webui._usage_data(realm, tmp_path, "graph", "daily")
    today_bar = graph["bars"][-1]
    assert {s["name"]: s["tok"] for s in today_bar["segments"]} == {"Warren": 100, "System": 50}
    assert next(s for s in today_bar["segments"] if s["name"] == "System")["color"] == sysusage.COLOR


def test_the_usage_epoch_applies_to_system_too(monkeypatch, tmp_path):
    realm = _realm(monkeypatch)
    old = (datetime.date.today() - datetime.timedelta(days=3)).isoformat() + "T10:00:00"
    (tmp_path / sysusage.FILE).write_text(json.dumps({"ts": old, "tokens": {"total": 70}}) + "\n", "utf-8")
    (tmp_path / "realm.json").write_text(json.dumps({"usage_epoch": datetime.date.today().isoformat()}), "utf-8")
    d = webui._usage_data(realm, tmp_path, "line", "7d")
    assert d["total"] == 0 and d["total_30d"] == 0


def test_the_keepalive_records_its_tokens_as_system(tmp_path):
    result = {"type": "result", "model": "claude-haiku-4-5-20251001",
              "usage": {"input_tokens": 12, "output_tokens": 3},
              "total_cost_usd": 0.0001}
    sysjobs._record_keepalive(tmp_path, json.dumps(result), True)
    (r,) = sysusage.runs(tmp_path)
    assert r["task"] == "system:usage-keepalive" and r["tokens"]["total"] >= 15
    sysjobs._record_keepalive(tmp_path, "garbage", True)          # never raises
    assert len(sysusage.runs(tmp_path)) == 1
