"""Opt-in live Codex verification in a temporary realm; never runs scheduled jobs.

Run from the checkout: python tools/smoke_codex.py
Uses the CLI's signed-in account and default model (real tokens). Keeps all artifacts under the
printed temporary realm. Notifications are muted before importing Armada.
"""
import json
import os
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from armada import notify
os.environ[notify.MUTE_ENV] = "1"
from armada import runner
from armada.util import write_json_atomic


def main():
    # Use ordinary directory inheritance, like a real realm. mkdtemp's private Windows ACL
    # grants OWNER RIGHTS, which changes meaning when Codex's sandbox account creates a file.
    root = Path(__file__).resolve().parents[1] / (".test-tmp-smoke-" + uuid.uuid4().hex)
    root.mkdir()
    agent = root / "agents" / "developer"
    agent.mkdir(parents=True)
    write_json_atomic(root / "realm.json", {"name": "Codex verification", "providers": ["codex"],
                                           "workspace": str(root), "default_model": "codex:default", "default_effort": "low"})
    write_json_atomic(agent / "agent.json", {"id": "developer", "display": "Developer", "model": "codex:default"})
    (agent / "soul.md").write_text("The verification word for this agent is sailboat.", encoding="utf-8")
    events = []
    result = runner.chat_stream(root, "developer", "main",
                               "Create a file named codex-smoke.txt in your current agent directory. "
                               "It must contain only the verification word from your agent context. "
                               "Do not touch any other file or use network services. Then reply ARMADA_CODEX_OK.",
                               events.append, allow_tools=True)
    artifact = agent / "codex-smoke.txt"
    content_ok = artifact.is_file() and artifact.read_text(encoding="utf-8-sig").strip() == "sailboat"
    summary = {"realm": str(root), "ok": result["ok"], "reply": result["output"],
               "artifact_ok": content_ok, "artifact_exists": artifact.is_file(),
               "event_kinds": sorted({e.get("kind", "") for e in events}), "tokens": result["tokens"]}
    print(json.dumps(summary, indent=2))
    return 0 if summary["ok"] and summary["artifact_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
