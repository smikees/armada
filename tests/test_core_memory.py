"""The default 'core' memory (owner + environment) seeded at setup."""
from armada import memory, goals


def test_merge_core_fields_preserves_machine_and_manual(tmp_path):
    (tmp_path / "memory").mkdir()
    memory.seed_core_memory(tmp_path, owner="Mihai",
                            env={"Timezone": "Europe/Madrid", "Machine": "HOST", "GPU": "AMD"})
    p = tmp_path / "memory" / "core-context.md"
    p.write_text(p.read_text(encoding="utf-8") + "- Note: likes hotels\n", encoding="utf-8")
    # change owner, add gender, clear timezone
    memory.merge_core_fields(tmp_path, {"Owner": "Alex", "Gender": "Male", "Timezone": ""})
    out = p.read_text(encoding="utf-8")
    assert "- Owner: Alex" in out and "- Gender: Male" in out
    assert "- Timezone:" not in out                       # cleared
    assert "- Machine: HOST" in out and "- GPU: AMD" in out  # machine facts preserved
    assert "- Note: likes hotels" in out                  # manual line preserved


def test_core_breakdown_matches_injected_core(tmp_path):
    (tmp_path / "objectives.md").write_text("Advance the mission.", encoding="utf-8")
    (tmp_path / "memory").mkdir()
    (tmp_path / "memory" / "m.md").write_text("---\ntitle: R\n---\nrealm fact", encoding="utf-8")
    aw = tmp_path / "agents" / "warren"
    (aw / "memory").mkdir(parents=True)
    (aw / "memory" / "a.md").write_text("---\ntitle: A\n---\nagent fact", encoding="utf-8")
    (aw / "mandate.md").write_text("You are Warren.", encoding="utf-8")
    goals.save_goal(tmp_path, title="Ship", body="do it", agents=["warren"])
    agent = {"mandate": "mandate.md"}
    bd = memory.core_breakdown(tmp_path, aw, agent)
    assert bd["mission"] > 0 and bd["goals"] > 0 and bd["realm_memory"] > 0 and bd["agent_memory"] > 0
    # the breakdown sizes the exact section text that assemble_core() injects
    sections = memory._core_sections(tmp_path, aw, agent)
    assert sum(len(t) for _, t in sections) == sum(bd.values())
    assert memory.assemble_core(tmp_path, aw, agent) == "\n\n".join(t for _, t in sections)


def test_build_core_memory_marks_kind_and_lists_fields():
    txt = memory.build_core_memory("Mihai", {"Timezone": "Europe/Madrid",
                                             "Operating system": "Windows 11"})
    assert "kind: core" in txt
    assert "- Owner: Mihai" in txt
    assert "- Timezone: Europe/Madrid" in txt
    assert "- Operating system: Windows 11" in txt


def test_seed_core_memory_writes_once(tmp_path):
    (tmp_path / "memory").mkdir()
    p = memory.seed_core_memory(tmp_path, owner="Mihai", env={"Machine": "HOST"})
    assert p.exists() and p.name == "core-context.md"
    first = p.read_text(encoding="utf-8")
    # does not overwrite an existing (possibly user-edited) core memory by default
    p.write_text("---\ntitle: Owner & environment\nkind: core\n---\nedited\n", encoding="utf-8")
    memory.seed_core_memory(tmp_path, owner="Mihai")
    assert "edited" in p.read_text(encoding="utf-8")
    # overwrite=True refreshes it
    memory.seed_core_memory(tmp_path, owner="Alex", env={"Machine": "HOST2"}, overwrite=True)
    assert "- Owner: Alex" in p.read_text(encoding="utf-8")


def test_core_memory_loads_into_agent_context(tmp_path):
    (tmp_path / "memory").mkdir()
    (tmp_path / "agents" / "warren" / "memory").mkdir(parents=True)
    memory.seed_core_memory(tmp_path, owner="Mihai", env={"Timezone": "Europe/Madrid"})
    core = memory.assemble_core(tmp_path, tmp_path / "agents" / "warren", {})
    assert "Mihai" in core and "Europe/Madrid" in core
