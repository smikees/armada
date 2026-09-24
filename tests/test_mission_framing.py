"""Realm objectives are injected as FRAMING only — the per-goal enumeration is stripped so each
agent carries just the goals mapped to it (via goals_for_agent), not all of them.
"""
from armada import memory

_DOC = """# Mihai's Goals — the North Star
> Every minister reads this. No agent moves money; propose, the owner disposes.
## Meta
Make Mihai wealthy, healthy, and happy.
---
## FINANCIAL  (lead: Warren)
### G1 — Net wealth
double the net worth
### G8 — Play guitar
left-handed acoustic
## Ownership map
| G1 | Warren |
| G8 | Aristotle |
"""


def test_framing_strips_goal_enumeration():
    f = memory._mission_framing(_DOC)
    assert "wealthy, healthy, and happy" in f      # meta-objective kept
    assert "propose, the owner disposes" in f      # guardrails kept
    assert "guitar" not in f.lower()               # other agents' goals gone
    assert "Net wealth" not in f
    assert "Ownership map" not in f
    assert not f.rstrip().endswith("-")            # no dangling '---'


def test_framing_keeps_unstructured_doc_whole():
    doc = "# Mission\nJust prose with no goal sections."
    assert memory._mission_framing(doc).strip() == doc.strip()
